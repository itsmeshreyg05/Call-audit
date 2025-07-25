import os
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, Depends
import torch
import librosa
import numpy as np
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import noisereduce as nr
import soundfile as sf
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import os
from fastapi import APIRouter, HTTPException, Depends, Body
from sqlalchemy.orm import Session
import requests
import uuid
from pathlib import Path
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import re
from src.config.log_config import logger
from src.utils.utils import refresh_ringcentral_token
from datetime import datetime
from src.database.database import get_db
from src.models.model import Audio, Segment
from src.schemas.schema import AudioUploadResponse, DiarizationResult, DiarizationSegment

load_dotenv()



# Create router
router = APIRouter(
    prefix="/audio",
    tags=["audio"],
)
security = HTTPBearer()

UPLOAD_DIR = Path("./data/uploads")
PROCESSED_DIR = Path("./data/processed")
PREPROCESSED_DIR = Path("./data/preprocessed")
ALLOWED_EXTENSIONS = {".opus", ".mp3", ".wav"}
HF_TOKEN = os.getenv("HF_TOKEN")
SAMPLE_RATE = 16000
MIN_SEGMENT_LENGTH = 0.5 



for directory in [UPLOAD_DIR, PROCESSED_DIR, PREPROCESSED_DIR]:
    directory.mkdir(exist_ok=True, parents=True)



try:
    whisper_model_name = "openai/whisper-medium"
    whisper_processor = WhisperProcessor.from_pretrained(whisper_model_name)
    whisper_model = WhisperForConditionalGeneration.from_pretrained(whisper_model_name)
    if torch.cuda.is_available():
        whisper_model = whisper_model.to("cuda")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {str(e)}")
    raise RuntimeError(f"Failed to load Whisper model: {str(e)}")

def preprocess_audio(audio_path: str, output_path: str) -> str:
    """Preprocess audio file to improve quality"""
    try:
        y, sr = librosa.load(audio_path, sr=None, mono=False)
        
     
        if len(y.shape) > 1:
            y = librosa.to_mono(y)
   
        if sr != SAMPLE_RATE:
            y = librosa.resample(y, orig_sr=sr, target_sr=SAMPLE_RATE)
            
    
        y = librosa.util.normalize(y)
        y = nr.reduce_noise(y=y, sr=SAMPLE_RATE, stationary=True)
        y, _ = librosa.effects.trim(y, top_db=20)
        
    
        sf.write(output_path, y, SAMPLE_RATE)
        return output_path
    except Exception as e:
        logger.error(f"Audio preprocessing failed for {audio_path}: {str(e)}")
        print(f"Error in preprocessing: {str(e)}")
        return audio_path



@router.post("/upload", response_model=AudioUploadResponse)
async def upload_audio(
    contentUri: str = Body(..., embed=True),
    contentType: str = Body("audio/mpeg", embed=True),
    token: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    try:

        match = re.search(r"/recording/(\d+)/content", contentUri)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid content URI format")
        recording_id = match.group(1)


        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)


        headers = {"Authorization": f"Bearer {token.credentials}"}
        response = requests.get(contentUri, headers=headers)
   
        if response is None:
            raise HTTPException(status_code=400, detail="Downloaded file is empty")
       

        if response.status_code == 401:
            try:
                refreshed_token = refresh_ringcentral_token(db)  # <- Call your function here
                headers = {"Authorization": f"Bearer {refreshed_token}"}
                response = requests.get(contentUri, headers=headers)
            except Exception as e:
                logger.error(f"Token refresh failed for recording {recording_id}: {str(e)}")
                raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")

  
        if response.status_code != 200:
            logger.error(f"Failed to download audio from {contentUri}: Status {response.status_code}, Response: {response.text}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download audio file: {response.text}"
            )

        if not response.content:
            raise HTTPException(status_code=400, detail="Downloaded file is empty")

    
        ext_map = {
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/mp3": ".mp3",
        }

        contentType = contentType or response.headers.get("Content-Type", "audio/mpeg")
        file_extension = ext_map.get(contentType.lower(), ".mp3")

        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Save file
        audio_id = str(uuid.uuid4())
        filename = f"{audio_id}{file_extension}"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as f:
            f.write(response.content)

        # Preprocess audio
        preprocessed_path = PREPROCESSED_DIR / f"{audio_id}_preprocessed.wav"
        processed_path = preprocess_audio(str(file_path), str(preprocessed_path))

        # Save metadata to DB
        db_audio = Audio(
            id=audio_id,
            original_filename=filename,
            original_path=str(file_path),
            processed_path=processed_path,
            file_type=file_extension,
            processed=False,  # Change to True if preprocessing is final
            uploaded_at=datetime.utcnow(),
            recording_id=recording_id
        )

        db.add(db_audio)
        db.commit()
        db.refresh(db_audio)

        return AudioUploadResponse(
            audio_id=audio_id,
            file_path=processed_path,
            original_filename=filename,
            file_type=file_extension
        )

    except Exception as e:
        logger.error(f"Audio upload failed for recording {recording_id if 'recording_id' in locals() else 'unknown'}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


def transcribe_audio(audio_data: np.ndarray, sr: int = SAMPLE_RATE) -> str:
    try:
        processed = whisper_processor(
            audio_data,
            sampling_rate=sr,
            return_tensors="pt",
            return_attention_mask=True
        )
        if torch.cuda.is_available():
            processed = {k: v.to("cuda") for k, v in processed.items()}
        with torch.no_grad():
            generated_ids = whisper_model.generate(
                input_features=processed["input_features"],
                attention_mask=processed["attention_mask"],
                language="en",
                task="transcribe"
            )
        return whisper_processor.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        print(f"Transcription error: {str(e)}")
        return ""

def transcribe_long_audio(audio_data: np.ndarray, sr: int = SAMPLE_RATE, chunk_duration: int = 30) -> str:
    """Split long audio into chunks and transcribe each, then join."""
    chunk_size = chunk_duration * sr
    full_text = []
    start = 0
    total_len = len(audio_data)

    while start < total_len:
        end = min(start + chunk_size, total_len)
        chunk = audio_data[start:end]
        text = transcribe_audio(chunk, sr)
        if text:
            full_text.append(text)
        start = end

    return " ".join(full_text).strip()

@router.get("/diarize/{audio_id}", response_model=DiarizationResult)
async def diarize_audio(audio_id: str, db: Session = Depends(get_db)):
    try:
        db_audio = db.query(Audio).filter(Audio.id == audio_id).first()
        if not db_audio:
            raise HTTPException(status_code=404, detail="Audio ID not found")

        audio_path = db_audio.processed_path
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found for audio_id {audio_id}: {audio_path}")
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Full transcription with chunking to avoid truncation
        y, sr = librosa.load(audio_path, sr=SAMPLE_RATE)
        full_transcript = transcribe_long_audio(y, sr)

        # Diarization pipeline
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=HF_TOKEN
        )
        diarization = pipeline(audio_path, num_speakers=2, min_speakers=1, max_speakers=2)

        segments = []
        speaker_mapping = {}
        db.query(Segment).filter(Segment.audio_id == audio_id).delete()

        for turn, _, speaker in diarization.itertracks(yield_label=True):
            if turn.end - turn.start < MIN_SEGMENT_LENGTH:
                continue
            if speaker not in speaker_mapping:
                speaker_mapping[speaker] = f"Speaker_{len(speaker_mapping) + 1}"

            # Transcribe segment
            start_sample = int(turn.start * sr)
            end_sample = int(turn.end * sr)
            segment_audio = y[start_sample:end_sample]
            text = transcribe_audio(segment_audio, sr)

            db_segment = Segment(
                audio_id=audio_id,
                speaker=speaker_mapping[speaker],
                start=turn.start,
                end=turn.end,
                text=text
            )
            db.add(db_segment)

            segments.append({
                "speaker": speaker_mapping[speaker],
                "start": turn.start,
                "end": turn.end,
                "text": text
            })

        db_audio.processed = True
        db_audio.full_transcript = full_transcript
        db.commit()

        return DiarizationResult(
            audio_id=audio_id,
            segments=segments,
            full_transcript=full_transcript,
            status="completed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Diarization failed for audio_id {audio_id}: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Diarization failed: {str(e)}")

def get_audio_segments(audio_id: str, db: Session) -> List[DiarizationSegment]:
    segments = db.query(Segment).filter(Segment.audio_id == audio_id).all()
    return [
        DiarizationSegment(
            speaker=segment.speaker,
            start=segment.start,
            end=segment.end,
            text=segment.text
        ) for segment in segments
    ]