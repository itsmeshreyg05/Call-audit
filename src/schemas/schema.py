from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import datetime
from pydantic import BaseModel, HttpUrl, Field
from datetime import datetime 

# Audio schemas
class AudioUploadResponse(BaseModel):
    audio_id: str
    file_path:str ## CHANGED IN THIS LINE 
    original_filename: str
    file_type: str
    
    class Config:
        from_attributes = True  

class AudioBase(BaseModel):
    original_filename: str
    file_type: str
    processed: bool = False

class AudioCreate(AudioBase):
    pass

class AudioInDB(AudioBase):
    id: str
    original_path: str
    processed_path: str
    uploaded_at: datetime
    recording_id: str
    
    class Config:
        from_attributes = True  

# # Diarization schemas
# class DiarizationSegment(BaseModel):
#     speaker: str
#     start: float
#     end: float
#     text: str

class DiarizationSegment(BaseModel):
    speaker: str
    text: str

class DiarizationResult(BaseModel):
    audio_id: str
    segments: List[DiarizationSegment]
    full_transcript: str
    status: str

# Call analysis schemas
class CallAnalysisParameters(BaseModel):
    professionalism_score: int  # 1-10
    tone_analysis: Dict[str, float]  # e.g., {"formal": 0.8, "friendly": 0.6}
    context_awareness_score: int  # 1-10
    response_time_analysis: Dict[str, Any]
    fluency_score: int  # 1-10
    probing_effectiveness: int  # 1-10
    call_closing_quality: int  # 1-10
    script_adherence: Optional[Dict[str, Any]] = None
    summary: str

class CallAnalysisResult(BaseModel):
    audio_id: str
    analysis: Dict[str, Any]
    status: str
    
    class Config:
        from_attributes = True  

class SegmentInDB(DiarizationSegment):
    id: int
    audio_id: str
    
    class Config:
        from_attributes = True  

class AnalysisInDB(BaseModel):
    id: int
    audio_id: str
    professionalism_score: int
    tone_analysis: Dict[str, float]
    context_awareness_score: int
    response_time_analysis: Dict[str, Any]
    fluency_score: int
    probing_effectiveness: int
    call_closing_quality: int
    script_adherence: Optional[Dict[str, Any]] = None
    summary: str
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True  

class AudioWithSegments(AudioInDB):
    segments: List[SegmentInDB] = []
    analysis: Optional[AnalysisInDB] = None
    
    class Config:
        from_attributes = True  


class OAuthRequestSchema(BaseModel):
    client_id: str = Field(..., description="RingCentral client ID")
    redirect_uri: HttpUrl = Field(..., description="Redirect URI after authorization")
    state: str = Field(..., description="Unique state string for request tracking")
    brand_id: str = Field(default="1210", description="RingCentral brand ID")        


class TokenRequestSchema(BaseModel):
    grant_type: str = Field(..., example="authorization_code")
    code: str = Field(..., example="auth_code_from_redirect")
    redirect_uri: HttpUrl = Field(..., example="http://localhost:3000/oauth/callback")

class CallLogQueryParams(BaseModel):
    showBlocked: Optional[bool] = True
    view: Optional[str] = "Simple"
    withRecording: Optional[bool] = False
    recordingType: Optional[str] = "All"
    dateFrom: datetime
    dateTo: datetime
    page: Optional[int] = 1
    perPage: Optional[int] = 100
    showDeleted: Optional[bool] = False


class RecordingDetail(BaseModel):
    recording_id: str
    username: Optional[str] = None
    phone_number: Optional[str] = None
    start_time: Optional[datetime] = None
