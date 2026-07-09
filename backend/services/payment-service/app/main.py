from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Payment Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database
payments_db = []
transactions_db = []

class PaymentCreate(BaseModel):
    order_id: str
    user_id: str
    amount: float = Field(..., gt=0)
    currency: str = "KES"
    payment_method: str  # mpesa, card, bank
    phone_number: Optional[str] = None
    card_details: Optional[Dict] = None

class PaymentResponse(BaseModel):
    id: str = Field(alias="_id")
    transaction_id: str
    order_id: str
    user_id: str
    amount: float
    currency: str
    payment_method: str
    status: str  # pending, completed, failed, refunded
    reference: str
    mpesa_code: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

@app.get("/")
def root():
    return {"service": "Payment Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment-service", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/payments/initiate")
def initiate_payment(payment: PaymentCreate):
    logger.info(f"Initiating payment for order: {payment.order_id}")
    
    # Generate transaction ID
    transaction_id = f"TXN-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    payment_dict = payment.dict()
    payment_dict["_id"] = str(uuid.uuid4())
    payment_dict["transaction_id"] = transaction_id
    payment_dict["status"] = "pending"
    payment_dict["reference"] = f"REF-{str(uuid.uuid4())[:10].upper()}"
    payment_dict["mpesa_code"] = None
    payment_dict["created_at"] = datetime.utcnow()
    payment_dict["completed_at"] = None
    
    payments_db.append(payment_dict)
    
    # Simulate payment processing
    # In real app, integrate with M-Pesa/Stripe API
    if payment.payment_method == "mpesa":
        # Simulate M-Pesa STK Push
        logger.info(f"Sending STK Push to {payment.phone_number}")
        # Auto-complete for testing
        payment_dict["status"] = "completed"
        payment_dict["mpesa_code"] = f"MP{random.randint(100000, 999999)}"
        payment_dict["completed_at"] = datetime.utcnow()
    
    return payment_dict

@app.get("/api/payments/{payment_id}")
def get_payment(payment_id: str):
    for payment in payments_db:
        if payment.get("_id") == payment_id:
            return payment
    raise HTTPException(status_code=404, detail="Payment not found")

@app.get("/api/payments/order/{order_id}")
def get_payment_by_order(order_id: str):
    for payment in payments_db:
        if payment.get("order_id") == order_id:
            return payment
    raise HTTPException(status_code=404, detail="Payment not found")

@app.post("/api/payments/{payment_id}/verify")
def verify_payment(payment_id: str):
    for payment in payments_db:
        if payment.get("_id") == payment_id:
            # Simulate verification
            if payment.get("status") == "pending":
                payment["status"] = "completed"
                payment["completed_at"] = datetime.utcnow()
            return payment
    raise HTTPException(status_code=404, detail="Payment not found")

@app.post("/api/payments/{payment_id}/refund")
def refund_payment(payment_id: str):
    for payment in payments_db:
        if payment.get("_id") == payment_id:
            if payment.get("status") != "completed":
                raise HTTPException(status_code=400, detail="Only completed payments can be refunded")
            payment["status"] = "refunded"
            return {"message": "Refund initiated", "payment": payment}
    raise HTTPException(status_code=404, detail="Payment not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
