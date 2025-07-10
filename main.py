from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import logging
import signal
import sys
 
from scheduler import CallAnalysisScheduler 
from src.routes import audio, call_analysis, auth, call_details
from src.database.database import Base, engine
 

Base.metadata.create_all(bind=engine)
 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
 

app = FastAPI(
    title="Audio Analysis API",
    description="API for audio file diarization and call analysis",
    version="1.0.0",
)
 

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 

app.include_router(auth.router)
app.include_router(call_details.router)
app.include_router(audio.router)
app.include_router(call_analysis.router)
 

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Audio Analysis API",
        "documentation": "/docs",
    }
 

scheduler_instance = CallAnalysisScheduler()
background_scheduler = BackgroundScheduler()

try:
    startup_trigger = DateTrigger(run_date=datetime.now() + timedelta(seconds=5))
    background_scheduler.add_job(scheduler_instance.run_daily_analysis, startup_trigger)
    logger.info("Scheduled startup job for daily call analysis.")  
except Exception as e:
    logger.error(f"Failed to schedule startup job: {e}") 

try:
    background_scheduler.start()
    logger.info("Background scheduler started.") 
except Exception as e:
    logger.error(f"Failed to start background scheduler: {e}") 

def shutdown(signal_received, frame):
    try:
        logger.info("Signal received. Shutting down scheduler and app...")
        background_scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down cleanly.")  
    except Exception as e:
        logger.error(f"Error during shutdown: {e}") 
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)
 