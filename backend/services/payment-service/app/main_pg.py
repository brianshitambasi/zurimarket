# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import uuid
import logging
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Payment Service (PostgreSQL)", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class PaymentCreate(BaseModel):
    order_id: str
    user_id: str
    amount: float
    currency: str = "KES"
    payment_method: str  # mpesa, card, bank
    phone_number: Optional[str] = None
    card_details: Optional[Dict] = None

class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    mpesa_code: Optional[str] = None

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="zurimarket",
        user="zuri",
        password="zuripass",
        port=5432
    )

# Create tables
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id VARCHAR(36) PRIMARY KEY,
                transaction_id VARCHAR(50) UNIQUE NOT NULL,
                order_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                currency VARCHAR(10) DEFAULT 'KES',
                payment_method VARCHAR(50) NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                reference VARCHAR(50) UNIQUE NOT NULL,
                mpesa_code VARCHAR(50),
                phone_number VARCHAR(20),
                card_details JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        logger.info("✅ Payment tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database error: {e}")

init_db()

@app.get("/")
def root():
    return {"service": "Payment Service", "database": "postgresql", "status": "running"}

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "payment-service",
        "database": "postgresql",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/payments/initiate")
def initiate_payment(payment: PaymentCreate):
    logger.info(f"Initiating payment for order: {payment.order_id}")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        payment_id = str(uuid.uuid4())
        transaction_id = f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        reference = f"REF-{str(uuid.uuid4())[:10].upper()}"
        
        # Simulate M-PESA processing
        mpesa_code = None
        status = "pending"
        
        if payment.payment_method == "mpesa":
            # Simulate successful payment
            mpesa_code = f"MP{random.randint(100000, 999999)}"
            status = "completed"
            completed_at = datetime.utcnow()
        else:
            completed_at = None
        
        cur.execute("""
            INSERT INTO payments (
                id, transaction_id, order_id, user_id, amount, currency,
                payment_method, status, reference, mpesa_code, phone_number,
                card_details, completed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            payment_id, transaction_id, payment.order_id, payment.user_id,
            payment.amount, payment.currency, payment.payment_method,
            status, reference, mpesa_code, payment.phone_number,
            json.dumps(payment.card_details) if payment.card_details else None,
            completed_at
        ))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        logger.info(f"✅ Payment initiated: {transaction_id}")
        return dict(result)
        
    except Exception as e:
        logger.error(f"❌ Payment initiation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM payments WHERE id = %s", (payment_id,))
        payment = cur.fetchone()
        cur.close()
        conn.close()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return dict(payment)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/payments/order/{order_id}")
def get_payment_by_order(order_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM payments WHERE order_id = %s ORDER BY created_at DESC LIMIT 1", (order_id,))
        payment = cur.fetchone()
        cur.close()
        conn.close()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        return dict(payment)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Get payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payments/{payment_id}/verify")
def verify_payment(payment_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute("""
            UPDATE payments 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'pending'
            RETURNING *
        """, (payment_id,))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="Payment not found or already completed")
        return dict(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Verify payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/payments/{payment_id}/refund")
def refund_payment(payment_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if payment can be refunded
        cur.execute("SELECT status FROM payments WHERE id = %s", (payment_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        if result['status'] != 'completed':
            raise HTTPException(status_code=400, detail="Only completed payments can be refunded")
        
        cur.execute("""
            UPDATE payments 
            SET status = 'refunded', completed_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
        """, (payment_id,))
        
        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        
        return {"message": "Refund initiated", "payment": dict(result)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Refund payment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
