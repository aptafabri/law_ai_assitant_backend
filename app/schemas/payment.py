from pydantic import BaseModel
from datetime import datetime
from typing import List, Any
from enum import StrEnum

class SubscriptionPlan(StrEnum):
    MONTHLY = "MONTHLY" 
    TRIMONTHLY = "TRIMONTHLY"
    BIANUAL = "BIANUAL"
    ANUAL = "ANUAL"
    
class InitializePaymentRequest(BaseModel):
    plan:SubscriptionPlan

class RetrievePaymentRequest(BaseModel):
    token:str