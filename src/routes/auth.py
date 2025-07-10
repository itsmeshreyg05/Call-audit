from fastapi import Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import  Annotated
from urllib.parse import urlencode
import base64
import requests
from src.schemas.schema import OAuthRequestSchema , TokenRequestSchema
from fastapi import APIRouter
from src.config.log_config import logger


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
    token_data: TokenRequestSchema  
):
  
    RINGCENTRAL_TOKEN_URL = "https://platform.ringcentral.com/restapi/oauth/token"
    

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
    try:

        response = requests.post(RINGCENTRAL_TOKEN_URL, headers=headers, data=data)

        if response.status_code != 200:
            logger.error(f"RingCentral token request failed - Status: {response.status_code}, Response: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=response.json())

        return response.json()
    
    except requests.exceptions.RequestException as e:  # **ADDED**
        logger.error(f"Network error during RingCentral token request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to RingCentral API")
    
    except Exception as e:  # **ADDED**
        logger.error(f"Unexpected error in get_ringcentral_token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
