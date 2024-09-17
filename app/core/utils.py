import os
from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
from typing import Union, Any
from models import TokenTable
import jwt
from core import settings
from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_hashed_password(password: str) -> str:
    """Hash the provided password using bcrypt."""
    try:
        hashed = password_context.hash(password)
        # Log that password hashing was successful
        logger.debug("Password hashed successfully.")
        return hashed
    except Exception as e:
        # Log any exception that occurs during hashing
        logger.error(f"Error hashing password: {e}")
        raise

def verify_password(password: str, hashed_pass: str) -> bool:
    """Verify the provided password against the hashed password."""
    try:
        is_verified = password_context.verify(password, hashed_pass)
        # Log the result of the password verification
        if is_verified:
            logger.debug("Password verification successful.")
        else:
            logger.warning("Password verification failed.")
        return is_verified
    except Exception as e:
        # Log any exception that occurs during verification
        logger.error(f"Error verifying password: {e}")
        raise

def create_access_token(subject: Union[str, Any], expires_delta: int = None) -> str:
    """Create an access JWT token for the given subject."""
    try:
        if expires_delta is not None:
            expires = datetime.now(tz=timezone.utc) + expires_delta
            logger.debug(f"Custom access token expiry set to {expires}.")
        else:
            expires = datetime.now(tz=timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            logger.debug(f"Default access token expiry set to {expires}.")

        to_encode = {"exp": expires, "sub": int(subject)}
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        # Log that the access token was created successfully
        logger.info(f"Access token created for subject {subject}.")
        return encoded_jwt
    except Exception as e:
        # Log any exception that occurs during token creation
        logger.error(f"Error creating access token: {e}")
        raise

def create_refresh_token(subject: Union[str, Any], expires_delta: int = None) -> str:
    """Create a refresh JWT token for the given subject."""
    try:
        if expires_delta is not None:
            expires = datetime.now() + expires_delta
            logger.debug(f"Custom refresh token expiry set to {expires}.")
        else:
            expires = datetime.now() + timedelta(
                minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
            )
            logger.debug(f"Default refresh token expiry set to {expires}.")

        to_encode = {"exp": expires, "sub": int(subject)}
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_REFRESH_SECRET_KEY, settings.ALGORITHM
        )
        # Log that the refresh token was created successfully
        logger.info(f"Refresh token created for subject {subject}.")
        return encoded_jwt
    except Exception as e:
        # Log any exception that occurs during token creation
        logger.error(f"Error creating refresh token: {e}")
        raise
