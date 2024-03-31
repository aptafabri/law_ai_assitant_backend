from sqlalchemy.orm import Session
from database.session import Base, engine

def initialise(db: Session) -> None:

    with engine.connect() as connection:
        print("Successfully connected to Database!")   
    
    try:
        Base.metadata.create_all(engine)
    
    except Exception as e:
        print("error", e)
    pass
