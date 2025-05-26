# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# import asyncio
# import logging

# from src.routes import audio, call_analysis, auth , call_details
# from src.database.database import Base, engine
# # Create tables in the database
# Base.metadata.create_all(bind=engine)

# # Configure logger
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)
# Base.metadata.create_all(bind=engine)

# # Initialize FastAPI application
# app = FastAPI(
#     title="Audio Analysis API",
#     description="API for audio file diarization and call analysis",
#     version="1.0.0",
# )


# # Configure CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # For production, specify actual origins
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Include routers from different modules
# app.include_router(auth.router)
# app.include_router(call_details.router)
# app.include_router(audio.router)
# app.include_router(call_analysis.router)


# @app.get("/")
# async def root():
#     return {
#         "message": "Welcome to the Audio Analysis API",
#         "documentation": "/docs",  # Swagger documentation URL
#     }

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import asyncio
import logging
import signal
import sys
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from scheduler import CallAnalysisScheduler 

from src.routes import audio, call_analysis, auth, call_details
from src.database.database import Base, engine
import signal
import sys
import time
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


# Create tables in the database
Base.metadata.create_all(bind=engine)

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



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




# # Create APScheduler instance
# apscheduler = BackgroundScheduler()

# # Create scheduler handler instance
# scheduler_instance = CallAnalysisScheduler()

# # Add job
# apscheduler.add_job(
#     scheduler_instance.run_daily_analysis,
#     trigger=CronTrigger(day_of_week='mon', hour=2, minute=0),
#     name="Weekly Call Analysis Job"
# )

# # Handle graceful shutdown
# def shutdown(signum, frame):
#     logger.info("Shutting down scheduler...")
#     apscheduler.shutdown()
#     sys.exit(0)

# signal.signal(signal.SIGINT, shutdown)
# signal.signal(signal.SIGTERM, shutdown)

# # Start the scheduler
# logger.info("Starting background scheduler...")
# apscheduler.start()


# try:
#     while True:
#         time.sleep(60)
# except (KeyboardInterrupt, SystemExit):
#     shutdown(None, None)



@app.get("/")
async def root():
    return {
        "message": "Welcome to the Audio Analysis API",
        "documentation": "/docs",
    }
