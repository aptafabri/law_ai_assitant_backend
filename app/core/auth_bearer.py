import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import FastAPI, Depends, HTTPException,status
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from models import TokenTable
from database.session import SessionLocal, get_session
from crud.user import create_access_token, create_refresh_token
from contextlib import contextmanager
from core import settings

def decodeJWT(jwtoken: str):
    try:
        # Decode and verify the token
        payload = jwt.decode(jwtoken, settings.JWT_SECRET_KEY, settings.ALGORITHM)
        
        return payload
    except InvalidTokenError:
        return None


class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            
            payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, settings.ALGORITHM)
            user_id = payload['sub']
            print("user-id:", user_id)
            session = next(get_session())
            data=session.query(TokenTable).filter_by(user_id=user_id,access_token=credentials.credentials,status=True).first()
            
            if data:
                session.query(TokenTable)\
                    .filter(TokenTable.access_token == credentials.credentials)\
                    .delete()
                session.commit()
                access_token = create_access_token(user_id)
                refresh_token = create_refresh_token(user_id)
                token_db = TokenTable(user_id=user_id,  access_token=access_token,  refresh_token=refresh_token, status=True)
                session.add(token_db)
                session.commit()
                session.refresh(token_db)
                                              
                return access_token   
           
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
        return isTokenValid
    
jwt_bearer = JWTBearer()