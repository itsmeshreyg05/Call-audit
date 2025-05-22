import os
import sys
import argparse
import logging
import json
import base64
import requests
from datetime import datetime, timedelta

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import project modules
from src.database.database import SessionLocal
from src.models.model import TokenStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("token_manager.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("token_manager")

class TokenManager:
    def __init__(self):
        self.db = SessionLocal()
        
    def store_initial_token(self, client_id, client_secret, auth_code, redirect_uri):
        """Store the initial token from authorization code"""
        try:
            # First, use the auth code to get the tokens
            token_url = "https://platform.ringcentral.com/restapi/oauth/token"
            
            # Create basic auth header
            auth_str = f"{client_id}:{client_secret}"
            auth_bytes = auth_str.encode('ascii')
            auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_b64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": redirect_uri
            }
            
            response = requests.post(token_url, headers=headers, data=data)
            
            if response.status_code != 200:
                logger.error(f"Failed to get access token: {response.json()}")
                return False
            
            token_data = response.json()
            
            # Calculate expiry time
            expires_at = datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
            
            # Store in database
            existing_token = self.db.query(TokenStore).first()
            
            if existing_token:
                # Update existing token
                existing_token.client_id = client_id
                existing_token.client_secret = client_secret
                existing_token.access_token = token_data["access_token"]
                existing_token.refresh_token = token_data["refresh_token"]
                existing_token.token_type = token_data["token_type"]
                existing_token.expires_at = expires_at
                existing_token.updated_at = datetime.utcnow()
            else:
                # Create new token entry
                token_record = TokenStore(
                    client_id=client_id,
                    client_secret=client_secret,
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    token_type=token_data["token_type"],
                    expires_at=expires_at
                )
                self.db.add(token_record)
            
            self.db.commit()
            logger.info("Token stored successfully")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error storing token: {str(e)}")
            return False
        finally:
            self.db.close()
    
    def get_current_token_info(self):
        """Get information about the current stored token"""
        try:
            token_record = self.db.query(TokenStore).first()
            
            if not token_record:
                logger.info("No token found in database")
                return None
                
            # Check expiration
            now = datetime.utcnow()
            is_expired = token_record.expires_at <= now if token_record.expires_at else True
            
            return {
                "client_id": token_record.client_id,
                "access_token": token_record.access_token[:10] + "..." if token_record.access_token else None,
                "expires_at": token_record.expires_at.isoformat() if token_record.expires_at else None,
                "is_expired": is_expired,
                "created_at": token_record.created_at.isoformat() if token_record.created_at else None,
                "updated_at": token_record.updated_at.isoformat() if token_record.updated_at else None
            }
            
        except Exception as e:
            logger.error(f"Error getting token info: {str(e)}")
            return None
        finally:
            self.db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RingCentral Token Manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Store token command
    store_parser = subparsers.add_parser("store", help="Store a new token")
    store_parser.add_argument("--client-id", required=True, help="RingCentral client ID")
    store_parser.add_argument("--client-secret", required=True, help="RingCentral client secret")
    store_parser.add_argument("--auth-code", required=True, help="Authorization code from OAuth flow")
    store_parser.add_argument("--redirect-uri", required=True, help="Redirect URI used in OAuth flow")
    
    # Get token info command
    info_parser = subparsers.add_parser("info", help="Get information about the stored token")
    
    args = parser.parse_args()
    
    manager = TokenManager()
    
    if args.command == "store":
        success = manager.store_initial_token(
            args.client_id,
            args.client_secret,
            args.auth_code,
            args.redirect_uri
        )
        sys.exit(0 if success else 1)
        
    elif args.command == "info":
        token_info = manager.get_current_token_info()
        if token_info:
            print(json.dumps(token_info, indent=2))
            sys.exit(0)
        else:
            sys.exit(1)
    
    else:
        parser.print_help()
        sys.exit(1)