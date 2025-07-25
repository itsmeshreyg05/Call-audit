from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password : str
    database_name : str
    database_username : str
    hf_token: str


    google_service_account_file: str
    google_spreadsheet_id: str 


    class Config:
        env_file = '.env'
        
settings = Settings() 