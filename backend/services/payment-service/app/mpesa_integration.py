# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime
import uuid
import logging
import os
import json
import random
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket M-PESA Integration", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class MpesaSTKPush(BaseModel):
    phone_number: str
    amount: float
    order_id: str
    user_id: str
    account_reference: str = "ZuriMarket"

class MpesaCallback(BaseModel):
    ResultCode: int
    ResultDesc: str
    MerchantRequestID: str
    CheckoutRequestID: str
    MpesaReceiptNumber: Optional[str] = None

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="zurimarket",
        user="zuri",
        password="zuripass",
        port=5432
    )

@app.get("/health")
def health():
    return {"status": "healthy", "service": "mpesa-integration", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/mpesa/stk-push")
async def stk_push(request: MpesaSTKPush):
    """Initiate M-PESA STK Push payment"""
    logger.info(f"STK Push initiated for {request.phone_number}")
    
    try:
        # Generate unique checkout request ID
        checkout_request_id = f"ZURI{datetime.utcnow().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        
        # Store transaction in database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        transaction_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO payments (
                id, transaction_id, order_id, user_id, amount, 
                currency, payment_method, status, reference,
                mpesa_code, phone_number, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            transaction_id,
            f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{checkout_request_id}",
            request.order_id,
            request.user_id,
            request.amount,
            "KES",
            "mpesa",
            "pending",
            f"REF-{checkout_request_id}",
            None,
            request.phone_number,
            datetime.utcnow()
        ))
        
        transaction = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        # Simulate M-PESA STK Push (In production, call Safaricom API)
        # For testing, auto-complete after 2 seconds
        import asyncio
        asyncio.create_task(simulate_mpesa_callback(
            transaction["id"],
            checkout_request_id,
            request.amount
        ))
        
        return {
            "status": "success",
            "message": "STK Push sent",
            "checkout_request_id": checkout_request_id,
            "transaction_id": transaction["transaction_id"],
            "amount": request.amount,
            "phone": request.phone_number
        }
        
    except Exception as e:
        logger.error(f"M-PESA STK Push error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def simulate_mpesa_callback(transaction_id: str, checkout_request_id: str, amount: float):
    """Simulate M-PESA callback (for testing)"""
    import asyncio
    import random
    
    # Simulate network delay
    await asyncio.sleep(random.randint(2, 5))
    
    # Simulate success/failure (90% success rate)
    success = random.random() < 0.9
    
    if success:
        mpesa_code = f"MP{random.randint(100000, 999999)}"
        status = "completed"
        result_desc = "Payment successful"
        result_code = 0
    else:
        mpesa_code = None
        status = "failed"
        result_desc = "Payment failed"
        result_code = 1
    
    # Update transaction
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE payments 
            SET status = %s, 
                mpesa_code = %s,
                completed_at = %s
            WHERE id = %s
        """, (status, mpesa_code, datetime.utcnow(), transaction_id))
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"M-PESA callback: {status} - {checkout_request_id}")
        
    except Exception as e:
        logger.error(f"M-PESA callback error: {e}")

@app.post("/api/mpesa/callback")
async def mpesa_callback(request: Request):
    """M-PESA callback endpoint (for production)"""
    try:
        data = await request.json()
        logger.info(f"M-PESA callback received: {json.dumps(data)}")
        
        # Process callback
        result_code = data.get("ResultCode", 1)
        checkout_request_id = data.get("CheckoutRequestID", "")
        mpesa_receipt = data.get("MpesaReceiptNumber", "")
        
        if result_code == 0:
            status = "completed"
        else:
            status = "failed"
        
        # Update transaction
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE payments 
            SET status = %s, 
                mpesa_code = %s,
                completed_at = %s
            WHERE reference = %s
        """, (status, mpesa_receipt, datetime.utcnow(), f"REF-{checkout_request_id}"))
        conn.commit()
        cur.close()
        conn.close()
        
        return {"ResultCode": 0, "ResultDesc": "Success"}
        
    except Exception as e:
        logger.error(f"M-PESA callback error: {e}")
        return {"ResultCode": 1, "ResultDesc": str(e)}

@app.get("/api/mpesa/status/{transaction_id}")
def check_status(transaction_id: str):
    """Check transaction status"""
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM payments WHERE transaction_id = %s", (transaction_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {
            "transaction_id": result["transaction_id"],
            "status": result["status"],
            "amount": result["amount"],
            "mpesa_code": result["mpesa_code"],
            "created_at": result["created_at"],
            "completed_at": result["completed_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
