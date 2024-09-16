from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.v1 import api_router
from core import settings
from log_config import configure_logging

# FastAPI lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure logging when the application starts
    logger = configure_logging(__name__)

    # Startup event
    logger.info("Application startup")
    yield
    # Shutdown event
    logger.info("Application shutdown")

# Pass the lifespan context manager to FastAPI
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# CORS middleware
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)