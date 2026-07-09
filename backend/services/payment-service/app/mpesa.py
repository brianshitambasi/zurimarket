# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid
import logging
import random
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket M-PESA Integration", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MpesaSTKPush(BaseModel):
    phone_number: str
    amount: float
    order_id: str
    user_id: str
    account_reference: str = "ZuriMarket"

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
async def stk_push(payment: MpesaSTKPush):
    logger.info(f"STK Push to {payment.phone_number}")
    
    try:
        checkout_id = f"ZURI{datetime.utcnow().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        transaction_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO payments (
                id, transaction_id, order_id, user_id, amount, 
                currency, payment_method, status, reference, phone_number, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            transaction_id,
            f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{checkout_id}",
            payment.order_id,
            payment.user_id,
            payment.amount,
            "KES",
            "mpesa",
            "pending",
            f"REF-{checkout_id}",
            payment.phone_number,
            datetime.utcnow()
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "success",
            "message": "STK Push sent",
            "checkout_request_id": checkout_id,
            "transaction_id": result["transaction_id"],
            "amount": payment.amount
        }
        
    except Exception as e:
        logger.error(f"STK Push error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mpesa/status/{transaction_id}")
def check_status(transaction_id: str):
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
            "mpesa_code": result.get("mpesa_code"),
            "created_at": result["created_at"].isoformat() if result["created_at"] else None,
            "completed_at": result["completed_at"].isoformat() if result.get("completed_at") else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Check status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mpesa/callback")
async def mpesa_callback(request: Request):
    try:
        data = await request.json()
        logger.info(f"M-PESA callback: {data}")
        return {"ResultCode": 0, "ResultDesc": "Success"}
    except Exception as e:
        logger.error(f"Callback error: {e}")
        return {"ResultCode": 1, "ResultDesc": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
