import logging
import os
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def configure_logging(logger_name: str):
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
        timed_handler = TimedRotatingFileHandler(
            f"logs/backend_production_{current_date}.log", when="midnight", interval=1, backupCount=7
        )
        timed_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(timed_handler)

        size_handler = RotatingFileHandler(
            f"logs/backend_production_size_{current_date}.log", maxBytes=10 * 1024 * 1024, backupCount=5
        )
        size_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(size_handler)

        # Adjust logging levels for specific loggers
        logging.getLogger('sse_starlette.sse').setLevel(logging.ERROR)
        logging.getLogger('openai._base_client').setLevel(logging.ERROR)
        logging.getLogger('httpcore.http11').setLevel(logging.ERROR)

    elif env == "development":
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

        # Adjust logging levels for specific loggers
        logging.getLogger('sse_starlette.sse').setLevel(logging.WARNING)
        logging.getLogger('openai._base_client').setLevel(logging.WARNING)
        logging.getLogger('httpcore.http11').setLevel(logging.WARNING)

    elif env == "local":
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(console_handler)

        file_handler = RotatingFileHandler(
            f"logs/backend_local_{current_date}.log", maxBytes=1 * 1024 * 1024, backupCount=2
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

        # Adjust logging levels for specific loggers
        logging.getLogger('sse_starlette.sse').setLevel(logging.INFO)
        logging.getLogger('openai._base_client').setLevel(logging.INFO)
        logging.getLogger('httpcore.http11').setLevel(logging.INFO)

    # Apply logging configuration
    logging.basicConfig(level=log_level, handlers=handlers)

    # Get the logger with the provided name
    logger = logging.getLogger(logger_name)
    return logger
