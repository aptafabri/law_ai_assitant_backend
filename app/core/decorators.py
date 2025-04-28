from functools import wraps
from fastapi import HTTPException
from sqlalchemy.orm import Session
from crud.user import check_daily_chat_limit
from crud.user import get_userid_by_token

def check_chat_limit():
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies and session from kwargs
            dependencies = kwargs.get('dependencies')
            session = kwargs.get('session')
            
            if not dependencies or not session:
                raise HTTPException(
                    status_code=500,
                    detail="Required dependencies not provided"
                )
            
            # Get user_id from token
            user_id = get_userid_by_token(dependencies)
            
            # Check daily limit
            await check_daily_chat_limit(user_id, session)
            
            # Call the original function
            return await func(*args, **kwargs)
        return wrapper
    return decorator 