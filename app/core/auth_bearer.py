import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import TokenTable
from database.session import get_session
from core import settings
from log_config import configure_logging

# Configure logging
logger = configure_logging(__name__)

def decodeJWT(jwtoken: str):
    try:
        logger.debug("Attempting to decode JWT token.")
        
        # Decode and verify the token
        payload = jwt.decode(jwtoken, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        
        logger.debug(f"JWT token decoded successfully: {payload}")
        return payload
    except InvalidTokenError:
        logger.error("Invalid JWT token provided.")
        return None

class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)

        if credentials:
            logger.debug(f"Authorization credentials received.")

            if not credentials.scheme == "Bearer":
                logger.warning("Invalid authentication scheme used.")
                raise HTTPException(
                    status_code=403, detail="Invalid authentication scheme."
                )
            
            if not self.verify_jwt(credentials.credentials):
                logger.error("Invalid or expired JWT token.")
                raise HTTPException(
                    status_code=403, detail="Invalid token or expired token."
                )

            payload = jwt.decode(
                credentials.credentials, settings.JWT_SECRET_KEY, settings.ALGORITHM
            )
            user_id = int(payload["sub"])

            logger.info(f"Token validated successfully for user ID: {user_id}")

            session = next(get_session())
            data = (
                session.query(TokenTable)
                .filter_by(
                    user_id=user_id, access_token=credentials.credentials, status=True
                )
                .first()
            )

            if data:
                return credentials.credentials

            else:
                raise HTTPException(status_code=403, detail="Token blocked.")
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    def verify_jwt(self, jwtoken: str) -> bool:
        isTokenValid: bool = False
        try:
            payload = decodeJWT(jwtoken)
        except:
            payload = None
        
        if payload:
            isTokenValid = True
            logger.debug("JWT token verified successfully.")
        else:
            logger.debug("JWT verification failed.")
            
        return isTokenValid

jwt_bearer = JWTBearer()
