from fastapi import APIRouter, Depends, Request, Body, status, HTTPException
from fastapi.responses import JSONResponse
from core.pay_bearer import AUTHBearer
from crud.user import get_userid_by_token, get_user_info
from sqlalchemy.orm import Session
from database.session import get_session
import iyzipay
import json
from schemas.payment import SubscriptionPlan, InitializePaymentRequest, RetrievePaymentRequest
from models import User
import datetime
from core import settings

SUBSCRIPTION_DETAILS = {
    SubscriptionPlan.MONTHLY: {"name": "Monthly Plan", "price":3000},
    SubscriptionPlan.TRIMONTHLY: {"name": "3-Month Plan", "price": 8000},
    SubscriptionPlan.BIANUAL: {"name": "6-Month Plan", "price": 15000},
    SubscriptionPlan.ANUAL: {"name": "Annual Plan", "price": 30000},
}

router = APIRouter()

options = {
    'api_key': settings.IYZIPAY_API_KEY,
    'secret_key': settings.IYZIPAY_SECRET_KEY,
    'base_url': iyzipay.base_url

}

def calculate_expiry(plan: SubscriptionPlan) -> datetime.datetime:
    duration_map = {
        SubscriptionPlan.MONTHLY: 30,
        SubscriptionPlan.TRIMONTHLY: 90,
        SubscriptionPlan.BIANUAL: 180,
        SubscriptionPlan.ANUAL: 365
    }
    days = duration_map.get(plan, 30)  # Default to 1-month if invalid plan
    return datetime.datetime.now() + datetime.timedelta(days=days)

@router.post("/initialize", tags=["PaymentController"], status_code=200)
async def initialize_checkout(
    request:InitializePaymentRequest,
    dependencies=Depends(AUTHBearer()),
    session: Session = Depends(get_session)
):
    try:
        user_id = get_userid_by_token(dependencies)
        user_info = get_user_info(dependencies, session)
        identity_number = f'id-{user_id}'
        buyer = {
            'id': str(user_id),
            'name': user_info.user_name,
            'surname': user_info.user_name,
            'gsmNumber': '',
            'email': user_info.email,
            'identityNumber': identity_number,
            'lastLoginDate': '',
            'registrationDate': '',
            'registrationAddress': 'Istanbul',
            'ip': '',
            'city': 'Istanbul',
            'country': 'Turkey',
            'zipCode': ''
        }
        address = {
            'contactName': user_info.user_name,
            'city': 'Istanbul',
            'country': 'Turkey',
            'address': 'Istanbul',
            'zipCode': ''
        }
        subscription_details = SUBSCRIPTION_DETAILS[request.plan]
        basket_items = [
            {
                "id":f"{request.plan}Plan",
                "name": subscription_details["name"],
                "category1": "Subscription",
                "itemType": "VIRTUAL",
                "price": str(subscription_details["price"])
            }
        ]
        request = {
            'locale': 'en',
            "conversationId": str(user_id),
            "price":  str(subscription_details["price"]),
            "paidPrice":  str(subscription_details["price"]),
            "currency": "TRY",
            'basketId': str(request.plan),
            'paymentGroup': 'PRODUCT',
            "callbackUrl": settings.PAYMENT_CALLBACK_URL,
            "enabledInstallments": ["1"],
            'buyer': buyer,
            'shippingAddress': address,
            'billingAddress': address,
            'basketItems': basket_items
        }
        checkout_form_initialize = iyzipay.CheckoutFormInitialize()
        checkout_form_initialize_result = checkout_form_initialize.create(request, options)
        checkout_form_initialize_response = json.load(checkout_form_initialize_result)
        print('response:', checkout_form_initialize_response)
        if checkout_form_initialize_response['status'] == 'success':
            secret_key = options['secret_key']
            conversationId = checkout_form_initialize_response['conversationId']
            token = checkout_form_initialize_response['token']
            signature = checkout_form_initialize_response['signature']
            checkout_form_initialize.verify_signature([conversationId, token], secret_key, signature)
            return checkout_form_initialize_response
    except Exception as e:
        return HTTPException(
            detail=f"Internal server error {e}",
            status_code=500,
        )
        
@router.post("/verify-payment" , tags=["PaymentController"], status_code=200)
async def retrieve_payment(
    request: RetrievePaymentRequest,
    dependencies=Depends(AUTHBearer()),
    session:Session = Depends(get_session)
):
    try:
        user_id = get_userid_by_token(dependencies)
        payment_request = {
            "locale": "en",
            "conversationId": str(user_id),
            "token": request.token
        }

        checkout_form_retrieve = iyzipay.CheckoutForm()
        checkout_form_retrieve_result = checkout_form_retrieve.retrieve(payment_request, options)
        checkout_form_retrieve_response = json.loads(checkout_form_retrieve_result.read().decode("utf-8"))
        conversation_id = str(user_id)
        print("Paymenet status",checkout_form_retrieve_response.get("paymentStatus"))
        if checkout_form_retrieve_response.get("paymentStatus") == "SUCCESSS":
            user_id = checkout_form_retrieve_response["conversationId"]
            plan = checkout_form_retrieve_response["basketId"]
            paid_price = str(checkout_form_retrieve_response["paidPrice"]).rstrip("0").rstrip(".")
            
            payment_status = checkout_form_retrieve_response["paymentStatus"]
            payment_id = checkout_form_retrieve_response["paymentId"]
            currency = checkout_form_retrieve_response["currency"]
            price = str(checkout_form_retrieve_response["price"]).rstrip("0").rstrip(".")
            token = checkout_form_retrieve_response["token"]
            signature = checkout_form_retrieve_response["signature"]
            secret_key = options["secret_key"]
            checkout_form_retrieve.verify_signature(
                [payment_status, payment_id, currency, plan, conversation_id, paid_price, price, token],
                secret_key,
                signature,
            )
            
            print("Payment Information:", user_id, plan, paid_price)
            user = session.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return JSONResponse(status_code=404, content={"message":"User not found"})
            try:
                subscription_plan = SubscriptionPlan(plan)
            except ValueError:
                return JSONResponse(status_code=400,  content={"message":"Invalid subscription plan"})
            user.subscription_plan = subscription_plan
            user.subscription_expiry = calculate_expiry(subscription_plan)
            user.paid_price = paid_price 
            session.commit()
            
            return checkout_form_retrieve_response
        else:
            return JSONResponse(content={"message":"Payment verification failed!","paymentStatus":"FAILURE"},status_code=400)
    except Exception as e:
        raise HTTPException(
            detail=f"Internal Server error:{e}",
            status_code=500,
        )
        
@router.post("/payment_hook", tags=["PaymentController"], status_code=200)
async def webhook(
    body: dict = Body(),
    session:Session = Depends(get_session)
):
    print("payment successful", body)
    status = body.get("status")
    if status == "SUCCESS":
        conversation_id = body.get("paymentConversationId")
        token = body.get("token")
        request = {
            "locale": "en",
            "conversationId": str(conversation_id),
            "token": token
        }
        checkout_form_retrieve = iyzipay.CheckoutForm()
        checkout_form_retrieve_result = checkout_form_retrieve.retrieve(request, options)
        checkout_form_retrieve_response = json.loads(checkout_form_retrieve_result.read().decode("utf-8"))
        if checkout_form_retrieve_response.get("status") == "success":
            user_id = checkout_form_retrieve_response["conversationId"]
            plan = checkout_form_retrieve_response["basketId"]
            paid_price = str(checkout_form_retrieve_response["paidPrice"]).rstrip("0").rstrip(".")
            
            payment_status = checkout_form_retrieve_response["paymentStatus"]
            payment_id = checkout_form_retrieve_response["paymentId"]
            currency = checkout_form_retrieve_response["currency"]
            price = str(checkout_form_retrieve_response["price"]).rstrip("0").rstrip(".")
            token = checkout_form_retrieve_response["token"]
            signature = checkout_form_retrieve_response["signature"]
            secret_key = options["secret_key"]
            checkout_form_retrieve.verify_signature(
                [payment_status, payment_id, currency, plan, conversation_id, paid_price, price, token],
                secret_key,
                signature,
            )
            
            print("Payment Information:", user_id, plan, paid_price)
            user = session.query(User).filter(User.id == int(user_id)).first()
            if not user:
                return JSONResponse(status_code=404, detail="User not found")
            try:
                subscription_plan = SubscriptionPlan(plan)
            except ValueError:
                return JSONResponse(status_code=400, detail="Invalid subscription plan")
            user.subscription_plan = subscription_plan
            user.subscription_expiry = calculate_expiry(subscription_plan)
            user.paid_price = paid_price 
            session.commit()
            
        else:
            raise HTTPException(status_code=400, detail="Payment failed")
