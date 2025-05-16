from fastapi import FastAPI, Depends, Form, Query, Header, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Annotated
from urllib.parse import urlencode
from sqlalchemy.orm import Session
from io import BytesIO
import base64
import requests
from src.schemas.schema import  CallLogQueryParams
from fastapi import APIRouter
from src.schemas.schema import RecordingDetail
from src.database.database import get_db
from datetime import datetime
from src.models.model import RecordingDetail
import logging
security = HTTPBearer()

router = APIRouter(
    prefix="/call_details",
    tags=["call_details"]
)

@router.get("/ringcentral/call-log")
def get_call_log(
    params: CallLogQueryParams = Depends(),  # Use the Pydantic schema for query params
    token: HTTPAuthorizationCredentials = Depends(security)
):
    base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    
    params = {
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

    response = requests.get(base_url, headers=headers, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return response.json()

   
# @router.get("/ringcentral/recording/{recording_id}")
# async def get_recording(
#     recording_id: str,
#     token: HTTPAuthorizationCredentials = Depends(security),
#      db: Session = Depends(get_db)
# ):
#     headers = {
#         "Authorization": f"Bearer {token.credentials}"
#     }

#     # Step 1: Get the recording metadata
#     recording_url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}"
#     recording_response = requests.get(recording_url, headers=headers)

#     if recording_response.status_code != 200:
#         raise HTTPException(status_code=recording_response.status_code, detail=recording_response.json())

#     recording_data = recording_response.json()
#     print(recording_data)

#     # Step 2: Get call log entries (you might need to paginate if there are many)
#     call_log_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
#     call_log_response = requests.get(call_log_url, headers=headers)


#     if call_log_response.status_code != 200:
#         raise HTTPException(status_code=call_log_response.status_code, detail=call_log_response.json())

#     call_logs = call_log_response.json().get("records", [])
#     #print(call_logs)
#     phone_number = ""
#     name = ""
#     # Step 3: Find the matching outbound call with the same recording id
#     for log in call_logs:
#         recording_info = log.get("recording")
#         if recording_info and recording_info.get("id") == recording_id:
#             recording_data["phoneNumber"] = log.get("to", {}).get("phoneNumber", "")
#             recording_data["name"] = log.get("from", {}).get("name", "")
#             recording_data["startTime"] = log.get("startTime", "")
#             break  # Stop after finding the matching recording
    

#     existing = db.query(RecordingDetail).filter_by(recording_id=recording_id).first()
#     if not existing:
#         new_record = RecordingDetail(
#             recording_id=recording_id,
#             phone_number=recording_data.get("phoneNumber"),
#             username=recording_data.get("name"),
#             start_time=recording_data.get("startTime")
#         )

#         db.add(new_record)
#         db.commit()
#         db.refresh(new_record)

#     return recording_data



@router.get("/ringcentral/recording/{recording_id}")
async def get_recording(
    recording_id: str,
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    headers = {
        "Authorization": f"Bearer {token.credentials}"
    }

    # Step 1: Get the recording metadata
    recording_url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}"
    recording_response = requests.get(recording_url, headers=headers)

    if recording_response.status_code != 200:
        raise HTTPException(status_code=recording_response.status_code, detail=recording_response.json())

    recording_data = recording_response.json()
    
    # Initialize the additional fields we want to add
    recording_data["name"] = ""
    recording_data["phoneNumber"] = ""
    recording_data["startTime"] = ""
    
    # Step 2: Get call log entries
    call_log_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/call-log"
    call_log_response = requests.get(call_log_url, headers=headers)

    if call_log_response.status_code != 200:
        raise HTTPException(status_code=call_log_response.status_code, detail=call_log_response.json())

    call_logs = call_log_response.json().get("records", [])
    print("Hi",call_logs)
    # Step 3: Find the matching call with the same recording id
    for log in call_logs:
            recording_info = log.get("recording")
            if recording_info and recording_info.get("id") == recording_id:
                recording_data["phoneNumber"] = log.get("to", {}).get("phoneNumber", "")
                recording_data["name"] = log.get("from", {}).get("name", "")
                recording_data["startTime"] = log.get("startTime", "")
                break  # Stop after finding the matching recording
    
    # Save to database
    existing = db.query(RecordingDetail).filter_by(recording_id=recording_id).first()
    if not existing:
        new_record = RecordingDetail(
            recording_id=recording_id,
            phone_number=recording_data.get("phoneNumber"),
            username=recording_data.get("name"),
            start_time=recording_data.get("startTime")
        )

        db.add(new_record)
        db.commit()
        db.refresh(new_record)

    return recording_data

