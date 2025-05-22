from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import relationship
import datetime
from datetime import datetime
from src.database.database import Base

class Audio(Base):
    __tablename__ = "audios"

    id = Column(String, primary_key=True, index=True)
    original_filename = Column(String)
    original_path = Column(String)
    processed_path = Column(String)
    file_type = Column(String)
    processed = Column(Boolean, default=False)
    full_transcript = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    recording_id = Column(String, unique=True, nullable=False)
    
    
    # Relationships
    segments = relationship("Segment", back_populates="audio", cascade="all, delete-orphan")
    analysis = relationship("Analysis", back_populates="audio", uselist=False, cascade="all, delete-orphan")


class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    audio_id = Column(String, ForeignKey("audios.id"))
    speaker = Column(String)
    start = Column(Float)
    end = Column(Float)
    text = Column(Text)
    
    # Relationship
    audio = relationship("Audio", back_populates="segments")

class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    audio_id = Column(String, ForeignKey("audios.id"), unique=True)
    
    # Scores and metrics
    professionalism_score = Column(Float)
    professionalism_explanation = Column(Text, nullable=True)
    
    context_awareness_score = Column(Float)
    context_awareness_explanation = Column(Text, nullable=True)
    
    fluency_score = Column(Float)
    fluency_explanation = Column(Text, nullable=True)
    
    probing_effectiveness = Column(Float)
    probing_explanation = Column(Text, nullable=True)
    
    call_closing_quality = Column(Float)
    call_closing_explanation = Column(Text, nullable=True)
    
    # Complex analyses stored as JSON
    tone_analysis = Column(JSON)
    response_time_analysis = Column(JSON)
    
    # Call outcome fields
    outcome_category = Column(String, nullable=True)
    outcome_phrases = Column(JSON, nullable=True)  # Stores list of phrases
    outcome_explanation = Column(Text, nullable=True)
    
    # Summary and metadata
    summary = Column(Text)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
    
    # Relationship
    audio = relationship("Audio", back_populates="analysis")


class RecordingDetail(Base):
    __tablename__ = "recording_details"

    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(String, unique=True, nullable=False)
    username = Column(String)
    phone_number = Column(String)
    start_time = Column(DateTime)


class TokenStore(Base):
    __tablename__ = "token_store"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String, nullable=False)
    client_secret = Column(String, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_type = Column(String, default="Bearer")
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)