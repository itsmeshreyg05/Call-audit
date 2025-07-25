from fastapi import  Depends, HTTPException
from fastapi.security import  HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import requests
from src.schemas.schema import  CallLogQueryParams
from fastapi import APIRouter
from src.schemas.schema import RecordingDetail
from src.database.database import get_db
from datetime import datetime
from src.models.model import RecordingDetail
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from src.config.log_config import logger
security = HTTPBearer()

router = APIRouter(
    prefix="/call_details",
    tags=["call_details"]
)
 
@router.get("/ringcentral/call-log")
def get_call_log(
    params: CallLogQueryParams = Depends(),
    token: HTTPAuthorizationCredentials = Depends(security)
):
    base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    
    query_params = {
        "showBlocked": str(params.showBlocked).lower(),
        "view": params.view,
        "withRecording": str(params.withRecording).lower(),
        "recordingType": params.recordingType,
        "dateFrom": params.dateFrom.isoformat(),
        "dateTo": params.dateTo.isoformat(),
        "page": params.page,
        "perPage": params.perPage,
        "showDeleted": str(params.showDeleted).lower()
    }

    headers = {
        "Authorization": f"Bearer {token.credentials}"
    }

    response = requests.get(base_url, headers=headers, params=query_params)

    if response.status_code != 200:
        logger.error(f"Call log API error {response.status_code}: {response.text}")
        raise HTTPException(status_code=response.status_code, detail=response.json())

    response_json = response.json()
    filtered_records = []

    for record in response_json.get("records", []):
        if record.get("duration", 0) >= 60:
            utc_time = datetime.fromisoformat(record.get("startTime").replace("Z", "+00:00"))
            est_time = utc_time.astimezone(ZoneInfo("America/New_York"))
            record["startTime"] = est_time.isoformat()
            filtered_records.append(record)

    response_json["records"] = filtered_records
    return response_json
 
@router.get("/ringcentral/recording/{recording_id}")
async def get_recording(
    recording_id: str,
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    headers = {
        "Authorization": f"Bearer {token.credentials}"
    }
    recording_url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}"
    recording_response = requests.get(recording_url, headers=headers)

    if recording_response.status_code != 200:
        logger.error(f"Recording fetch error {recording_response.status_code}: {recording_response.text}")
        raise HTTPException(status_code=recording_response.status_code, detail=recording_response.json())

    recording_data = recording_response.json()
    recording_data["name"] = ""
    recording_data["phoneNumber"] = ""
    recording_data["startTime"] = ""

    call_log_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    

    date_from = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"
    params = {
        "withRecording": "true",
        "perPage": 100,
        "dateFrom": date_from,
        "view": "Detailed"
    }

    found = False

    while not found and call_log_url:
        call_log_response = requests.get(call_log_url, headers=headers, params=params)
        
        if call_log_response.status_code != 200:
            logger.error(f"Call log (recording match) error {call_log_response.status_code}: {call_log_response.text}")
            raise HTTPException(status_code=call_log_response.status_code, detail=call_log_response.json())

        response_json = call_log_response.json()
        call_logs = response_json.get("records", [])

        for log in call_logs:
            recording_info = log.get("recording")
            if recording_info and recording_info.get("id") == recording_id:
                recording_data["phoneNumber"] = log.get("to", {}).get("phoneNumber", "")
                recording_data["name"] = log.get("from", {}).get("name", "")
                utc_time = datetime.fromisoformat(log.get("startTime").replace("Z", "+00:00"))
                est_time = utc_time.astimezone(ZoneInfo("America/New_York"))
                recording_data["startTime"] = est_time.isoformat()
                recording_data["duration"]= log.get("duration", 0)
                found = True
                break

        next_page_uri = response_json.get("navigation", {}).get("nextPage", {}).get("uri")
        if next_page_uri:
            call_log_url = f"https://platform.ringcentral.com{next_page_uri}"
            params = None  
        else:
            break

    existing = db.query(RecordingDetail).filter_by(recording_id=recording_id).first()
    if not existing:
        new_record = RecordingDetail(
            recording_id=recording_id,
            phone_number=recording_data.get("phoneNumber") or None,
            username=recording_data.get("name") or None,
            start_time=recording_data.get("startTime"),
            duration=recording_data.get("duration") or None
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)

        return recording_data

