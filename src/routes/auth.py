from fastapi import FastAPI, Depends, Form, Query, Header, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Annotated
from datetime import datetime
from urllib.parse import urlencode
from io import BytesIO
import base64
import requests
from src.schemas.schema import OAuthRequestSchema , TokenRequestSchema
from fastapi import APIRouter


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)
security = HTTPBasic()


@router.get("/ringcentral/oauth")
def redirect_to_ringcentral(params: OAuthRequestSchema = Depends()):
    base_url = "https://platform.ringcentral.com/restapi/oauth/authorize"

    query = {
        "response_type": "code",
        "client_id": params.client_id,
        "redirect_uri": str(params.redirect_uri),
        "state": params.state,
        "brand_id": params.brand_id

    }

    auth_url = f"{base_url}?{urlencode(query)}"
    return RedirectResponse(url=auth_url)


@router.post("/ringcentral/token")
def get_ringcentral_token(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    token_data: TokenRequestSchema  # Use the Pydantic schema here
):
  
    RINGCENTRAL_TOKEN_URL = "https://platform.ringcentral.com/restapi/oauth/token"
    # token_data = TokenRequestSchema(grant_type=grant_type, code=code, redirect_uri=redirect_uri)

    client_id = credentials.username
    client_secret = credentials.password
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": token_data.grant_type,
        "code": token_data.code,
        "redirect_uri": str(token_data.redirect_uri)
    }

    response = requests.post(RINGCENTRAL_TOKEN_URL, headers=headers, data=data)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.json())

    return response.json()