from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Order Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database
orders_db = []

# Models
class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    total_price: float

class OrderCreate(BaseModel):
    user_id: str
    items: List[OrderItem]
    shipping_address: Dict[str, str]
    payment_method: str  # mpesa, card, cash

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    tracking_number: Optional[str] = None

class OrderResponse(BaseModel):
    id: str = Field(alias="_id")
    order_number: str
    user_id: str
    items: List[OrderItem]
    subtotal: float
    shipping_fee: float
    tax: float
    total_amount: float
    status: str  # pending, confirmed, shipped, delivered, cancelled
    shipping_address: Dict[str, str]
    payment_method: str
    payment_status: str  # pending, paid, failed
    tracking_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Helper
def generate_order_number() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

@app.get("/")
def root():
    return {"service": "Order Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "order-service", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/orders", response_model=OrderResponse)
def create_order(order: OrderCreate):
    logger.info(f"Creating order for user: {order.user_id}")
    
    # Calculate totals
    subtotal = sum(item.total_price for item in order.items)
    shipping_fee = 0 if subtotal > 50000 else 500  # Free shipping over 50,000 KES
    tax = subtotal * 0.16  # 16% VAT
    total = subtotal + shipping_fee + tax
    
    order_dict = order.dict()
    order_dict["_id"] = str(uuid.uuid4())
    order_dict["order_number"] = generate_order_number()
    order_dict["subtotal"] = subtotal
    order_dict["shipping_fee"] = shipping_fee
    order_dict["tax"] = tax
    order_dict["total_amount"] = total
    order_dict["status"] = "pending"
    order_dict["payment_status"] = "pending"
    order_dict["tracking_number"] = None
    order_dict["created_at"] = datetime.utcnow()
    order_dict["updated_at"] = datetime.utcnow()
    
    orders_db.append(order_dict)
    logger.info(f"Order created: {order_dict['order_number']}")
    
    return order_dict

@app.get("/api/orders")
def get_orders(user_id: Optional[str] = None):
    if user_id:
        return [o for o in orders_db if o.get("user_id") == user_id]
    return orders_db

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    for order in orders_db:
        if order.get("_id") == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")

@app.put("/api/orders/{order_id}")
def update_order(order_id: str, order_update: OrderUpdate):
    for order in orders_db:
        if order.get("_id") == order_id:
            update_data = order_update.dict(exclude_unset=True)
            order.update(update_data)
            order["updated_at"] = datetime.utcnow()
            return order
    raise HTTPException(status_code=404, detail="Order not found")

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: str):
    for i, order in enumerate(orders_db):
        if order.get("_id") == order_id:
            if order.get("status") in ["shipped", "delivered"]:
                raise HTTPException(status_code=400, detail="Cannot delete shipped order")
            orders_db.pop(i)
            return {"message": "Order cancelled"}
    raise HTTPException(status_code=404, detail="Order not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
