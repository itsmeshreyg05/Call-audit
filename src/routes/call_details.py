from fastapi import FastAPI, Depends, Form, Query, Header, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Annotated
from urllib.parse import urlencode
from io import BytesIO
import base64
import requests
from src.schemas.schema import  CallLogQueryParams
from fastapi import APIRouter


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
    base_url = "https://platform.ringcentral.com/restapi/v1.0/account/~/extension/~/call-log"
    
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

   
@router.get("/ringcentral/recording/{recording_id}")
def get_recording(
    recording_id: str,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    base_url = f"https://platform.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}"

    headers = {
        "Authorization": f"Bearer {token.credentials}"
    }

    response = requests.get(base_url, headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return response.json()

