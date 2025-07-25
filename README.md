# Call Audit Platform

## Overview

Call Audit is a FastAPI-based platform for automated analysis of call recordings. It integrates with RingCentral to fetch recent call logs, processes and transcribes audio using OpenAI's Whisper Large V3 model, and analyzes conversations using Ollama's Mistral model. Results are diarized, scored, and optionally exported to Google Sheets for reporting.

---

## Features

- **Fetch Call Recordings:** Automatically retrieves recent call recordings from RingCentral.
- **Audio Preprocessing:** Applies noise reduction, silence trimming, and normalization for improved transcription accuracy.
- **Transcription:** Uses Whisper Large V3 for high-quality speech-to-text conversion.
- **Speaker Diarization:** Identifies and segments speakers in the conversation.
- **Conversation Analysis:** Leverages Ollama's Mistral model to score and summarize calls across multiple dimensions (introduction, script adherence, listening, fumble, probing, closing, outcome).
- **Google Sheets Integration:** Exports analyzed results for reporting and tracking.
- **Token Management:** Handles RingCentral token refresh automatically.
- **REST API:** Exposes endpoints for uploading audio, diarization, and call analysis.
- **Swagger UI:** Interactive API documentation at `/docs`.

---

## API Endpoints

- `POST /audio/upload`  
  Upload and process a call recording.

- `GET /audio/diarize/{audio_id}`  
  Diarize speakers and segment the audio.

- `POST /call-analysis/`  
  Analyze a call transcript using Ollama's Mistral model.

---

## Setup & Usage

1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd Call-audit
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   - Create a `.env` file with your RingCentral, HuggingFace, and Google Sheets credentials.

4. **Run the FastAPI server:**
   ```sh
   uvicorn src.main:app --host 0.0.0.0 --port 8004
   ```

5. **Access Swagger UI:**
   - [http://127.0.0.1:8004/docs](http://127.0.0.1:8004/docs)

---

## Project Structure

```
Call-audit/
├── src/
│   ├── routes/
│   │   ├── audio.py
│   │   └── call_analysis.py
│   ├── models/
│   ├── schemas/
│   ├── database/
│   ├── utils/
│   └── config/
├── scheduler.py
├── requirements.txt
└── README.md
```

---

## Technologies Used

- **FastAPI** (REST API)
- **SQLAlchemy** (Database ORM)
- **Librosa, noisereduce, soundfile** (Audio processing)
- **Transformers (Whisper)** (Speech-to-text)
- **Ollama (Mistral)** (Conversation analysis)
- **RingCentral API** (Call recordings)
- **Google Sheets API** (Reporting)

---

## Notes

- Ensure your RingCentral and HuggingFace tokens are valid.
- For best transcription accuracy, use high-quality audio recordings.
- The analysis pipeline is optimized for English-language calls.

---

## License

MIT License

---

## Contact

For questions or support, please open an issue
