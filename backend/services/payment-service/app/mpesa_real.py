# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import uuid
import logging
import os
import json
import requests
import base64
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket M-PESA Real Integration", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONSUMER_KEY = os.getenv("MPESA_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("MPESA_CONSUMER_SECRET")
PASSKEY = os.getenv("MPESA_PASSKEY")
SHORTCODE = os.getenv("MPESA_SHORTCODE", "174379")
ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox")
CALLBACK_URL = os.getenv("MPESA_CALLBACK_URL")
TIMEOUT_URL = os.getenv("MPESA_TIMEOUT_URL")

BASE_URLS = {
    "sandbox": "https://sandbox.safaricom.co.ke",
    "production": "https://api.safaricom.co.ke"
}
BASE_URL = BASE_URLS.get(ENVIRONMENT, BASE_URLS["sandbox"])

access_token = None
token_expiry = None

class StkPushRequest(BaseModel):
    phone_number: str
    amount: float
    account_reference: str
    transaction_desc: str = "Payment for order"
    user_id: Optional[str] = None

def get_access_token():
    global access_token, token_expiry
    
    if access_token and token_expiry and datetime.utcnow() < token_expiry:
        return access_token
    
    try:
        auth_url = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
        auth_string = f"{CONSUMER_KEY}:{CONSUMER_SECRET}"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        
        logger.info("Authenticating with Safaricom...")
        
        response = requests.get(
            auth_url,
            headers={"Authorization": f"Basic {auth_b64}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            token_expiry = datetime.utcnow() + timedelta(seconds=3500)
            logger.info("Access token obtained successfully")
            return access_token
        else:
            logger.error(f"Token generation failed: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return None

def generate_password():
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    data_str = f"{SHORTCODE}{PASSKEY}{timestamp}"
    password = base64.b64encode(data_str.encode()).decode()
    return password, timestamp

@app.get("/")
def root():
    return {
        "service": "ZuriMarket M-PESA Integration",
        "environment": ENVIRONMENT,
        "shortcode": SHORTCODE,
        "status": "running"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "mpesa-real-integration",
        "environment": ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/api/mpesa/test-auth")
async def test_auth():
    token = get_access_token()
    if token:
        return {"status": "success", "message": "Authentication successful", "token_preview": token[:20] + "..."}
    else:
        return {"status": "failed", "message": "Authentication failed"}

@app.post("/api/mpesa/stk-push")
async def initiate_stk_push(request: StkPushRequest):
    logger.info(f"STK Push for {request.phone_number}, amount: {request.amount}")
    
    try:
        token = get_access_token()
        if not token:
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        phone = request.phone_number
        if phone.startswith("0"):
            phone = "254" + phone[1:]
        elif phone.startswith("+"):
            phone = phone[1:]
        
        password, timestamp = generate_password()
        
        stk_url = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"
        
        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(request.amount),
            "PartyA": phone,
            "PartyB": SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": CALLBACK_URL,
            "AccountReference": request.account_reference[:12],
            "TransactionDesc": request.transaction_desc[:13]
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(stk_url, json=payload, headers=headers)
        response_data = response.json()
        
        logger.info(f"STK Push response: {response_data}")
        
        if response_data.get("ResponseCode") == "0":
            logger.info("STK Push sent successfully")
            
            return {
                "status": "success",
                "message": "STK Push sent successfully",
                "checkout_request_id": response_data.get("CheckoutRequestID"),
                "merchant_request_id": response_data.get("MerchantRequestID"),
                "response_code": response_data.get("ResponseCode"),
                "response_description": response_data.get("ResponseDescription"),
                "customer_message": response_data.get("CustomerMessage"),
                "transaction_id": str(uuid.uuid4())
            }
        else:
            logger.warning(f"STK Push failed: {response_data}")
            return {
                "status": "error",
                "message": response_data.get("ResponseDescription", "STK Push failed"),
                "response_code": response_data.get("ResponseCode"),
                "checkout_request_id": response_data.get("CheckoutRequestID")
            }
        
    except Exception as e:
        logger.error(f"STK Push error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mpesa/callback")
async def mpesa_callback(request: Request):
    try:
        callback_data = await request.json()
        logger.info("M-PESA Callback received")
        
        body = callback_data.get("Body", {})
        stk_callback = body.get("stkCallback", {})
        
        result_code = stk_callback.get("ResultCode")
        result_desc = stk_callback.get("ResultDesc")
        merchant_request_id = stk_callback.get("MerchantRequestID")
        checkout_request_id = stk_callback.get("CheckoutRequestID")
        
        logger.info(f"Result Code: {result_code}")
        logger.info(f"Result Description: {result_desc}")
        
        if result_code == 0:
            callback_metadata = stk_callback.get("CallbackMetadata", {})
            items = callback_metadata.get("Item", [])
            
            amount = None
            mpesa_receipt = None
            phone_number = None
            transaction_date = None
            
            for item in items:
                if item.get("Name") == "Amount":
                    amount = item.get("Value")
                elif item.get("Name") == "MpesaReceiptNumber":
                    mpesa_receipt = item.get("Value")
                elif item.get("Name") == "PhoneNumber":
                    phone_number = item.get("Value")
                elif item.get("Name") == "TransactionDate":
                    transaction_date = item.get("Value")
            
            logger.info("Payment successful!")
            logger.info(f"Receipt: {mpesa_receipt}")
            logger.info(f"Amount: {amount}")
        else:
            logger.warning(f"Payment failed: {result_desc}")
        
        return {"ResultCode": 0, "ResultDesc": "Success"}
        
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return {"ResultCode": 1, "ResultDesc": str(e)}

@app.post("/api/mpesa/timeout")
async def mpesa_timeout(request: Request):
    try:
        timeout_data = await request.json()
        logger.info("M-PESA Timeout received")
        return {"ResultCode": 0, "ResultDesc": "Timeout received"}
    except Exception as e:
        logger.error(f"Timeout error: {e}")
        return {"ResultCode": 1, "ResultDesc": str(e)}

@app.get("/api/mpesa/status/{checkout_request_id}")
async def check_transaction_status(checkout_request_id: str):
    try:
        token = get_access_token()
        if not token:
            raise HTTPException(status_code=401, detail="Authentication failed")
        
        status_url = f"{BASE_URL}/mpesa/stkpushquery/v1/query"
        password, timestamp = generate_password()
        
        payload = {
            "BusinessShortCode": SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(status_url, json=payload, headers=headers)
        result = response.json()
        
        logger.info(f"Transaction status: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
