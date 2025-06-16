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
    
    # def fetch_recent_recordings(self):
    #     """Fetch recent call recordings from RingCentral with duration >= 1 minute and time in EST"""
    #     try:
    #         # Get recordings from the last 7 days
    #         date_from = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    #         date_to = datetime.utcnow().isoformat() + "Z"

    #         base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    #         headers = {"Authorization": f"Bearer {self.token}"}
    #         params = {
    #             "withRecording": "true",
    #             "perPage": 100,
    #             "dateFrom": date_from,
    #             "dateTo": date_to,
    #             "view": "Detailed"
    #         }

    #         all_records = []
    #         call_log_url = base_url

    #         while call_log_url:
    #             response = self._make_authorized_request("GET", call_log_url, params=params)
    #             time.sleep(5)

    #             if response.status_code != 200:
    #                 logger.error(f"Failed to fetch recordings: {response.json()}")
    #                 break

    #             response_json = response.json()
    #             records = response_json.get("records", [])
    #             all_records.extend(records)

    #             # Prepare for next page
    #             next_page_uri = response_json.get("navigation", {}).get("nextPage", {}).get("uri")
    #             if next_page_uri:
    #                 if next_page_uri.startswith("http"):
    #                     call_log_url = next_page_uri
    #                 else:
    #                     call_log_url = f"https://platform.ringcentral.com{next_page_uri}"
    #                 params = None  # Only needed on the first call
    #             else:
    #                 break

    #         filtered_records = []
    #         for record in all_records:
    #             if record.get("duration", 0) >= 60 and record.get("direction") != "Inbound":
    #                 filtered_records.append(record)
 

    #         logger.info(f"Found {len(filtered_records)} recordings from last one week with duration >= 1 minute")
    #         return filtered_records

    #     except Exception as e:
    #         logger.error(f"Error fetching recordings: {str(e)}")
    #         return []

    # def fetch_recent_recordings(self):
    #     """Fetch recent call recordings from RingCentral with duration >= 1 minute and time in EST"""
    #     try:
    #         # Get recordings from the last 7 days
    #         date_from = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
    #         date_to = datetime.utcnow().isoformat() + "Z"
 
    #         base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    #         headers = {"Authorization": f"Bearer {self.token}"}
    #         params = {
    #             "withRecording": "true",
    #             "perPage": 100,
    #             "dateFrom": date_from,
    #             "dateTo": date_to,
    #             "view": "Detailed"
    #         }
 
    #         all_records = []
    #         call_log_url = base_url
 
    #         while call_log_url:
    #             response = self._make_authorized_request("GET", call_log_url, params=params)
    #             time.sleep(5)
 
    #             if response.status_code != 200:
    #                 logger.error(f"Failed to fetch recordings: {response.json()}")
    #                 break
 
    #             response_json = response.json()
    #             records = response_json.get("records", [])
    #             all_records.extend(records)
 
    #             # Prepare for next page
    #             next_page_uri = response_json.get("navigation", {}).get("nextPage", {}).get("uri")
    #             if next_page_uri:
    #                 if next_page_uri.startswith("http"):
    #                     call_log_url = next_page_uri
    #                 else:
    #                     call_log_url = f"https://platform.ringcentral.com{next_page_uri}"
    #                 params = None  # Only needed on the first call
    #             else:
    #                 break
 
    #         filtered_records = []
 
    #         rep_call_counts = {}
 
    #         for record in all_records:
    #             if record.get("duration", 0) >= 60 and record.get("direction") != "Inbound":
    #                 filtered_records.append(record)
    #                 rep_name = record.get("from", {}).get("name", "Unknown")
    #                 rep_call_counts[rep_name] = rep_call_counts.get(rep_name, 0) + 1
   
 
    #         logger.info(f"Found {len(filtered_records)} recordings from last one week with duration >= 1 minute")
    #         return filtered_records
 
    #     except Exception as e:
    #         logger.error(f"Error fetching recordings: {str(e)}")
    #         return []


        #fetching the call recordings and adding the total counts of the call in sheet 2
    def fetch_recent_recordings(self , days=2):
            """Fetch recent call recordings from RingCentral (filtered + total counts)"""
            try:
                # Get recordings from the last 7 days
                date_from = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"
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
                logger.info(f"Filtered recordings (duration ≥ 1 min & outbound): {len(filtered_records)}")
 
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
            # start_time = datetime.fromisoformat(start_time_utc)

            # # Normalize to America/New_York zone
            # start_time_est = start_time.astimezone(ZoneInfo("America/New_York"))
            # print("est",start_time_est)

           

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
            # response = self._make_authorized_request(
            #         "POST",
            #         "http://127.0.0.1:8004/audio/upload",
            #         json={"contentUri": content_uri, "contentType": "audio/mpeg"},
                    
            # )

            
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
            # analysis_response = requests.post(
            #     "http://127.0.0.1:8004/call-analysis/",
            #     headers={"audio_id": audio_id}
            # )
            
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
    
    # def run_daily_analysis(self):
    #     """Main function to run daily call analysis"""
    #     logger.info("Starting daily call analysis")
        
    #     try:
    #         # Fetch recent recordings
    #         recordings = self.fetch_recent_recordings()
            
    #         # Process each recording
    #         processed_count = 0
    #         for recording in recordings:
    #             if self.process_recording(recording):
    #                 processed_count += 1
    #                 # Small delay to avoid overwhelming the server
    #                 time.sleep(1)
            
    #         logger.info(f"Daily analysis complete. Processed {processed_count} recordings.")
            
    #     except Exception as e:
    #         logger.error(f"Error in daily analysis: {str(e)}")
    #     finally:
    #         self.db.close()



    # def run_daily_analysis(self):
    #         """Main function to run daily call analysis"""
    #         logger.info("=== Starting daily call analysis ===")

    #         try:
    #             recordings = self.fetch_recent_recordings()
    #             logger.info(f"Fetched {len(recordings)} recordings.")

    #             # Track rep-wise call data
    #             rep_call_counts = defaultdict(int)
    #             processed_recordings = []

    #             for recording in recordings:
    #                 recording_id = recording.get("id") or recording.get("recording_id")
    #                 logger.debug(f"Processing recording ID: {recording_id}")
                    
    #                 if self.process_recording(recording):
    #                     processed_recordings.append(recording)
    #                     rep_name = recording.get("from", {}).get("name")
    #                     logger.debug(f"Recording processed successfully for rep: {rep_name}")
                        
    #                     if rep_name:
    #                         rep_call_counts[rep_name] += 1
    #                 else:
    #                     logger.warning(f"Recording processing failed/skipped: {recording_id}")
    #                 time.sleep(1)

    #             logger.info(f"Total processed recordings: {len(processed_recordings)}")
    #             logger.debug(f"Rep call counts: {dict(rep_call_counts)}")

    #             # Compute audited calls from Audio table
    #             rep_audited_counts = defaultdict(int)
    #             for rep_name in rep_call_counts:
    #                 try:
    #                     rep_audio_count = (
    #                         self.db.query(Audio)
    #                         .join(RecordingDetail, Audio.recording_id == RecordingDetail.recording_id)
    #                         .filter(RecordingDetail.username == rep_name)
    #                         .count()
    #                     )
    #                     rep_audited_counts[rep_name] = rep_audio_count
    #                     logger.debug(f"Audited count for {rep_name}: {rep_audio_count}")
    #                 except Exception as db_err:
    #                     logger.error(f"DB error for rep {rep_name}: {str(db_err)}")

    #             # Append to Google Sheet "Sheet2"
    #             today = datetime.now().strftime("%Y-%m-%d")
    #             for rep in rep_call_counts:
    #                 row = {
    #                     "IS Rep Name": rep,
    #                     "Total Outbound Calls": rep_call_counts[rep],
    #                     "Audited Calls": rep_audited_counts.get(rep, 0)
    #                 }

    #                 try:
    #                     logger.debug(f"Appending row to Sheet2: {row}")
    #                     append_dict_to_sheet(row, sheet_name="Sheet2")
    #                     logger.info(f"Appended to Sheet2: {row}")
    #                 except Exception as sheet_err:
    #                     logger.error(f"Failed to append to Google Sheet for {rep}: {str(sheet_err)}")

    #         except Exception as e:
    #             logger.exception(f"Error in daily analysis: {str(e)}")  # This logs stack trace too

    #         finally:
    #             logger.info("Closing database connection.")
    #             self.db.close()
    #             logger.info("=== Daily call analysis complete ===")

    def run_daily_analysis(self, days=2):
        """Main function to run daily call analysis for a given number of days"""
        logger.info("Starting daily call analysis")
 
        try:
            recordings = self.fetch_recent_recordings(days=days)
            rep_call_counts_total = self.rep_call_counts_total
            processed_recordings = []
 
            # Collect all start times from the recordings
            start_times = []
            for recording in recordings:
                start_str = recording.get("startTime")
                if start_str:
                    try:
                        start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                        start_times.append(start_dt)
                    except Exception as e:
                        logger.warning(f"Invalid date format in recording: {start_str}")
 
            if not start_times:
                logger.warning("No valid start times found in recordings.")
                return
 
            start_range = min(start_times)
            end_range = max(start_times)
 
            # Process recordings
            for recording in recordings:
                if self.process_recording(recording):
                    processed_recordings.append(recording)
                    time.sleep(1)
 
            # Calculate audited calls within that date range
            rep_audited_counts = defaultdict(int)
            for rep_name in rep_call_counts_total:
                rep_audio_count = (
                    self.db.query(Audio)
                    .join(RecordingDetail, Audio.recording_id == RecordingDetail.recording_id)
                    .filter(
                        RecordingDetail.username == rep_name,
                        RecordingDetail.start_time >= start_range,
                        RecordingDetail.start_time <= end_range
                    )
                    .count()
                )
                rep_audited_counts[rep_name] = rep_audio_count
 
            logger.info(f"Processed {len(processed_recordings)} recordings.")
 
            # Format date range
            date_range_str = f"{start_range.strftime('%m/%d/%Y')} - {end_range.strftime('%m/%d/%Y')}"
 
            # Append to Sheet2
            for rep in rep_call_counts_total:
                row = {
                    "Date Range": date_range_str,
                    "IS Rep Name": rep,
                    "Total Calls": rep_call_counts_total[rep],
                    "Audited Calls": rep_audited_counts.get(rep, 0)
                }
                append_dict_to_sheet(row, sheet_name="Sheet2")
                logger.info(f"Appended to Sheet2: {row}")
 
        except Exception as e:
            logger.error(f"Error in daily analysis: {str(e)}")
        finally:
            self.db.close()
 


if __name__ == "__main__":
    # scheduler = CallAnalysisScheduler()
    # # scheduler.run_daily_analysis()
    scheduler_instance = CallAnalysisScheduler()
    
    # Set up APScheduler
    apscheduler = BackgroundScheduler()

    # Schedule the job daily at 2 AM (change time as needed)
    # trigger = CronTrigger(hour=2, minute=0)
    run_time = datetime.now() + timedelta(minutes=3)
    trigger = DateTrigger(run_date=run_time)
    apscheduler.add_job(scheduler_instance.run_daily_analysis, trigger)

   
    apscheduler.start()
    logger.info("APScheduler started. Daily analysis job scheduled.")

    try:
        while True:
            time.sleep(60) 
    except (KeyboardInterrupt, SystemExit):
        apscheduler.shutdown()
        logger.info("Scheduler shut down successfully.")

