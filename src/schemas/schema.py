from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import datetime

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
    uploaded_at: datetime.datetime
    
    class Config:
        orm_mode = True

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
        orm_mode = True

class SegmentInDB(DiarizationSegment):
    id: int
    audio_id: str
    
    class Config:
        orm_mode = True

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
    created_at: datetime.datetime
    
    class Config:
        orm_mode = True

class AudioWithSegments(AudioInDB):
    segments: List[SegmentInDB] = []
    analysis: Optional[AnalysisInDB] = None
    
    class Config:
        orm_mode = True