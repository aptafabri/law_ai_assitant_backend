import logging
import os
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from datetime import datetime

# Load environment variables (for local testing, if needed)
from dotenv import load_dotenv

load_dotenv()

def configure_logging():
    # Determine environment
    env = os.getenv("ADALETGPT_ENV", "development")

    # Set logging level
    log_level = logging.DEBUG if env in ["development", "local"] else logging.INFO

    # Create log directory if it doesn't exist
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Get the current date to use in the log file name
    current_date = datetime.now().strftime("%Y-%m-%d")

    # Handlers
    handlers = []

    if env == "production":
        # Timed rotation for daily logs, with date in the filename
        timed_handler = TimedRotatingFileHandler(
            f"logs/backend_production_{current_date}.log", when="midnight", interval=1, backupCount=7
        )
        timed_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(timed_handler)

        # Rotating handler based on size, with date in the filename
        size_handler = RotatingFileHandler(
            f"logs/backend_production_size_{current_date}.log", maxBytes=10 * 1024 * 1024, backupCount=5
        )
        size_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(size_handler)

    elif env == "development":
        # Development: Log to console and file, rotate by size with date in the filename
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(console_handler)

        file_handler = RotatingFileHandler(
            f"logs/backend_development_{current_date}.log", maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    elif env == "local":
        # Local: Log to console and file, more frequent rotation with date in the filename
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(console_handler)

        # Rotate more frequently, keeping logs small for easier local inspection
        file_handler = RotatingFileHandler(
            f"logs/backend_local_{current_date}.log", maxBytes=1 * 1024 * 1024, backupCount=2
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    # Apply logging configuration
    logging.basicConfig(level=log_level, handlers=handlers)

    logger = logging.getLogger(__name__)
    return logger