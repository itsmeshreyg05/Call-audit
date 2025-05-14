from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes import audio, call_analysis, auth , call_details
from src.database.database import Base, engine

# Create tables in the database
Base.metadata.create_all(bind=engine)

# Initialize FastAPI application
app = FastAPI(
    title="Audio Analysis API",
    description="API for audio file diarization and call analysis",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers from different modules
app.include_router(auth.router)
app.include_router(call_details.router)
app.include_router(audio.router)
app.include_router(call_analysis.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to the Audio Analysis API",
        "documentation": "/docs",  # Swagger documentation URL
    }