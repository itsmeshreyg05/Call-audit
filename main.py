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

from src.routes import audio, call_analysis, auth, call_details
from src.database.database import Base, engine

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

# # Scheduler setup
# scheduler = BackgroundScheduler()

# class CallAnalysisScheduler:
#     def run_daily_analysis(self):
#         logger.info("Running daily call analysis...")
#         # Your actual analysis logic goes here

# scheduler_instance = CallAnalysisScheduler()

# async def schedule_job():
#     scheduler_instance.run_daily_analysis()

# @app.on_event("startup")
# async def startup_event():
#     logger.info("FastAPI startup - initializing scheduler")

#     # Schedule job to run once, 3 minutes after startup
#     run_time = datetime.now() + timedelta(minutes=3)
#     scheduler.add_job(
#         lambda: asyncio.run(schedule_job()),
#         trigger=DateTrigger(run_date=run_time),
#         id="run_once_after_startup"
#     )

#     # # Schedule recurring job daily at 5:30 AM
#     # scheduler.add_job(
#     #     lambda: asyncio.run(schedule_job()),
#     #     trigger=CronTrigger(hour=5, minute=30),
#     #     id="daily_job_530am"
#     # )

#     scheduler.start()
#     logger.info(f"Scheduler started. One-time job at {run_time.strftime('%Y-%m-%d %H:%M:%S')} and daily job at 5:30 AM.")

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Audio Analysis API",
        "documentation": "/docs",
    }
