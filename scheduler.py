import os
import sys
import logging
import requests
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import base64
from sqlalchemy.orm import Session
import time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import signal
from apscheduler.triggers.date import DateTrigger
from collections import defaultdict
from datetime import datetime
from google_sheets_helper import append_dict_to_sheet
from google_sheets_reader import fetch_sheet1_data
from dateutil import parser
from dateutil import tz
from src.routes.call_analysis import query_ollama_mistral
 
# Add the project root to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
 
# Import our modules
from src.database.database import get_db, SessionLocal
from src.models.model import RecordingDetail, Audio, TokenStore
from src.routes.audio import upload_audio
 
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
 
logger = logging.getLogger("call_analyzer_scheduler")
 
class CallAnalysisScheduler:
    def __init__(self):
        self.db = SessionLocal()
        self.token = self._get_valid_token()
       
    def _get_valid_token(self):
        """Get a valid access token, refreshing if necessary"""
        token_record = self.db.query(TokenStore).first()
       
        if not token_record:
            logger.error("No token found in database. Please authenticate first.")
            sys.exit(1)
           
        # Check if token is expired
        now = datetime.utcnow()
        if token_record.expires_at and token_record.expires_at <= now:
            logger.info("Token expired, refreshing...")
            self._refresh_token(token_record)
           
        return token_record.access_token
   
    def _refresh_token(self, token_record):
        """Refresh the RingCentral access token"""
        try:
            # RingCentral token refresh endpoint
            token_url = "https://platform.ringcentral.com/restapi/oauth/token"
           
            auth_header = f"{token_record.client_id}:{token_record.client_secret}"
            auth_header_encoded = auth_header.encode('ascii')
            auth_header_base64 = base64.b64encode(auth_header_encoded).decode('ascii')
           
            headers = {
                "Authorization": f"Basic {auth_header_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
           
            data = {
                "grant_type": "refresh_token",
                "refresh_token": token_record.refresh_token
            }
           
            response = requests.post(token_url, headers=headers, data=data)
           
            if response.status_code != 200:
                logger.error(f"Failed to refresh token: {response.json()}")
                return False
               
            # Update token in database
            token_data = response.json()
            token_record.access_token = token_data["access_token"]
            token_record.refresh_token = token_data["refresh_token"]
            token_record.expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
           
            self.db.commit()
            self.token = token_record.access_token
            logger.info("Token refreshed successfully")
            return True
           
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return False
       
    def _make_authorized_request(self, method, url, headers=None, **kwargs):
            """Make authorized requests and refresh token if expired"""
            if headers is None:
                headers = {}
            headers["Authorization"] = f"Bearer {self.token}"
           
            response = requests.request(method, url, headers=headers, **kwargs)
 
            # Check for token expiration (RingCentral returns 401 or 400 with TokenExpired)
            if response.status_code in [400, 401] and "token" in response.text.lower():
                logger.warning("Access token expired during request. Refreshing and retrying...")
                token_record = self.db.query(TokenStore).first()
                if self._refresh_token(token_record):
                    headers["Authorization"] = f"Bearer {self.token}"
                    response = requests.request(method, url, headers=headers, **kwargs)
           
            return response
 
 
 
        #fetching the call recordings and adding the total counts of the call in sheet 2
    def fetch_recent_recordings(self , hours=15):
            """Fetch recent call recordings from RingCentral (filtered + total counts)"""
            try:
                # Get recordings from the last 7 days
                date_from = (datetime.utcnow() - timedelta(hours=hours)).isoformat() + "Z"
                date_to = datetime.utcnow().isoformat() + "Z"
 
                base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
                headers = {"Authorization": f"Bearer {self.token}"}
                params = {
                    "withRecording": "true",
                    "perPage": 100,
                    "dateFrom": date_from,
                    "dateTo": date_to,
                    "view": "Detailed"
                }
 
                all_records = []
                call_log_url = base_url
 
                while call_log_url:
                    response = self._make_authorized_request("GET", call_log_url, params=params)
                    time.sleep(5)
 
                    if response.status_code != 200:
                        logger.error(f"Failed to fetch recordings: {response.json()}")
                        break
 
                    response_json = response.json()
                    records = response_json.get("records", [])
                    all_records.extend(records)
 
                    # Prepare for next page
                    next_page_uri = response_json.get("navigation", {}).get("nextPage", {}).get("uri")
                    if next_page_uri:
                        if next_page_uri.startswith("http"):
                            call_log_url = next_page_uri
                        else:
                            call_log_url = f"https://platform.ringcentral.com{next_page_uri}"
                        params = None
                    else:
                        break
 
                # Initialize rep call counters
                rep_call_counts_total = {}
                rep_call_counts_filtered = {}
                filtered_records = []
 
                for record in all_records:
                    rep_name = record.get("from", {}).get("name", "Unknown")
 
                    # Count all calls (unfiltered)
                    rep_call_counts_total[rep_name] = rep_call_counts_total.get(rep_name, 0) + 1
 
                    # Filtered: duration ≥ 60 and not inbound
                    if record.get("duration", 0) >= 60 and record.get("direction") != "Inbound":
                        filtered_records.append(record)
                        rep_call_counts_filtered[rep_name] = rep_call_counts_filtered.get(rep_name, 0) + 1
 
                logger.info(f"Total recordings (all): {len(all_records)}")
                logger.info(f"Filtered recordings (duration >= 1 min & outbound): {len(filtered_records)}")
 
                # Store both counts in each recording for downstream use (optional)
                self.rep_call_counts_total = rep_call_counts_total
                self.rep_call_counts_filtered = rep_call_counts_filtered
 
                return filtered_records
 
            except Exception as e:
                logger.error(f"Error fetching recordings: {str(e)}")
                return []
 
 
 
   
 
   
    def get_extension_number_from_id(self, extension_id):
        try:
            url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/extension/{extension_id}"
            response = self._make_authorized_request("GET", url)
           
            if response.status_code == 200:
                return response.json().get("extensionNumber")
            else:
                logger.warning(f"Unexpected status code {response.status_code} while fetching extension number for ID {extension_id}")
                return None
 
        except Exception as e:
            logger.warning(f"Failed to fetch extension number for ID {extension_id}: {e}")
            return None
       
    def process_recording(self, recording_data):
        """Process a single recording: save details, upload audio, trigger analysis"""
        try:
            recording_info = recording_data.get("recording")
            if not recording_info:
                return False
               
            recording_id = recording_info.get("id")
           
            # Check if this recording has been processed before
            existing_audio = self.db.query(Audio).filter_by(recording_id=recording_id).first()
            if existing_audio:
                logger.info(f"Recording {recording_id} already processed, skipping")
                return False
       
            start_time_utc = recording_data.get("startTime")
            print("utc",start_time_utc)
 
 
           
 
            # To fetch the extension number from the call log
            extension_id = recording_data.get("from", {}).get("extensionId")
            extension_number = None
            if extension_id:
                extension_number = self.get_extension_number_from_id(extension_id)  
            # Save recording details
            recording_detail = RecordingDetail(
                recording_id=recording_id,
                phone_number=recording_data.get("to", {}).get("phoneNumber"),
                username=recording_data.get("from", {}).get("name"),
                start_time=start_time_utc,
                duration=recording_data.get("duration", 0),
                extension_number=extension_number
 
            )
            self.db.add(recording_detail)
            self.db.commit()
           
            # Get the content URI
            content_uri = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}/content"
           
            # Upload and process audio
           
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(
                "http://127.0.0.1:8004/audio/upload",  # Adjust to your actual API endpoint
                json={"contentUri": content_uri, "contentType": "audio/mpeg"},
                headers=headers
            )
 
 
           
            if response.status_code != 200:
                logger.error(f"Failed to upload recording {recording_id}: {response.text}")
                return False
               
            audio_id = response.json().get("audio_id")
           
            # Trigger diarization
            diarize_response = requests.get(
                f"http://127.0.0.1:8004/audio/diarize/{audio_id}",
                headers=headers
            )
           
            if diarize_response.status_code != 200:
                logger.error(f"Failed to diarize recording {recording_id}: {diarize_response.text}")
                return False
               
     
            # Trigger analysis
            analysis_response = requests.post(
                "http://127.0.0.1:8004/call-analysis/",
                headers={
                    "audio-id": audio_id  
                }
            )
 
            if analysis_response.status_code != 200:
                logger.error(f"Failed to analyze recording {recording_id}: {analysis_response.text}")
                return False
               
            logger.info(f"Successfully processed recording {recording_id}")
            return True
           
        except Exception as e:
            logger.error(f"Error processing recording: {str(e)}")
            return False


    def run_daily_analysis(self, hours=15):
        logger.info("Starting daily call analysis")

        try:
            recordings = self.fetch_recent_recordings(hours=hours)
            rep_call_counts_total = self.rep_call_counts_total
            processed_recordings = []
            recording_ids_by_rep = defaultdict(set)  # 🆕 Track recording IDs by rep

            # Process recordings
            for recording in recordings:
                rep_name = recording.get("from", {}).get("name", "Unknown")
                recording_id = recording.get("recording", {}).get("id")
                if recording_id:
                    recording_ids_by_rep[rep_name].add(recording_id)

                if self.process_recording(recording):
                    processed_recordings.append(recording)
                    time.sleep(1)

            logger.info(f"Processed {len(processed_recordings)} recordings.")

            #  Date range for display only (not used for filtering)
            local_tz = tz.tzlocal()
            now = datetime.now(local_tz)
            date_range_str = f"{now.strftime('%m/%d/%Y')} - {now.strftime('%m/%d/%Y')}"

            # Fetch data from Sheet1
            analysis_data = fetch_sheet1_data()
            logger.info(f"Fetched {len(analysis_data)} rows from Sheet1")

            for rep in rep_call_counts_total:
                total_calls = rep_call_counts_total[rep]
                #  Count audited calls by querying DB (no time filtering)
                audited_calls = (
                    self.db.query(Audio)
                    .join(RecordingDetail, Audio.recording_id == RecordingDetail.recording_id)
                    .filter(RecordingDetail.username == rep)
                    .count()
                )

                filtered_scores = []
                reason_counts = defaultdict(int)

                for row in analysis_data:
                    try:
                        username = (row.get("Username") or row.get("username") or row.get("IS Rep Name") or row.get("Rep Name") or "").strip()
                        score_str = (row.get("Overall Score") or row.get("Score") or row.get("Overall Weightage") or "").strip()
                        reason = (row.get("Reason") or row.get("Remarks") or row.get("Feedback") or "").strip()

                        if not username or not score_str:
                            continue

                        if username.lower() != rep.lower():
                            continue

                        # Parse score
                        try:
                            score_clean = score_str.replace('%', '').replace(',', '').strip()
                            score = float(score_clean)
                            if score <= 1:
                                score *= 100
                            filtered_scores.append(score)
                            reason_counts[reason] += 1
                        except ValueError:
                            continue
                    except Exception as e:
                        logger.warning(f"Skipping row due to error: {e} | row = {row}")

                #  Weightage
                if filtered_scores:
                    weightage_score = round(sum(filtered_scores) / len(filtered_scores), 2)
                    weightage = f"{weightage_score}%"
                else:
                    weightage = "0%"

                #  Remarks
                categories = [
                    "Agreed for the meeting", "Not interested", "Call back requested",
                    "Out of scope", "Disconnected the call", "Prospect will reach out"
                ]
                feedback_parts = []
                for cat in categories:
                    count = reason_counts.get(cat, 0)
                    if count:
                        feedback_parts.append(f"{count} were '{cat}'")

                if feedback_parts:
                    remarks = f"Out of {audited_calls}/{total_calls} calls, " + "; ".join(feedback_parts)
                else:
                    remarks = f"Out of {audited_calls}/{total_calls} calls, no actionable outcomes recorded."

                #  Add sample recording IDs
                sample_ids = ", ".join(list(recording_ids_by_rep[rep])[:3])
                if sample_ids:
                    remarks += f" | Sample Recording IDs: {sample_ids}"

                # Append row to Sheet2
                row = {
                    "Date Range": date_range_str,
                    "IS Rep Name": rep,
                    "Total Calls": total_calls,
                    "Audited Calls": audited_calls,
                    "Overall Weightage": weightage,
                    "Remarks/Feedback": remarks
                }

                if processed_recordings:
                    try:
                        append_dict_to_sheet(row, sheet_name="Sheet2")
                        logger.info(f"Successfully appended to Sheet2: {row}")
                    except Exception as e:
                        logger.error(f"Failed to append to Sheet2: {e}")
                else:
                    logger.warning(f"Skipping append to Sheet2 for {rep} since no recordings were processed.")

        except Exception as e:
            logger.error(f"Error in daily analysis: {str(e)}", exc_info=True)
        finally:
            if hasattr(self, 'db') and self.db:
                self.db.close()

if __name__ == "__main__":
 
    scheduler_instance = CallAnalysisScheduler()
   
    # Set up APScheduler
    apscheduler = BackgroundScheduler()
 
 
    run_time = datetime.now() + timedelta(minutes=3)
    trigger = DateTrigger(run_date=run_time)
    # trigger = CronTrigger(hour=5, minute=0)
    apscheduler.add_job(scheduler_instance.run_daily_analysis, trigger)
    
 
   
    apscheduler.start()
    logger.info("APScheduler started. Daily analysis job scheduled.")
 
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        apscheduler.shutdown()
        logger.info("Scheduler shut down successfully.")
 
