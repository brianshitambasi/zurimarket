# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
import uuid
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Notification Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database
notifications_db = []

class NotificationCreate(BaseModel):
    user_id: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    type: str  # email, sms, push
    title: str
    message: str
    data: Optional[Dict] = None

class NotificationResponse(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    type: str
    title: str
    message: str
    data: Optional[Dict] = None
    status: str
    sent_at: Optional[datetime] = None
    created_at: datetime

@app.get("/")
def root():
    return {"service": "Notification Service", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification-service", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/notifications/send")
def send_notification(notification: NotificationCreate):
    logger.info(f"Sending {notification.type} notification to {notification.user_id}")
    
    notif_dict = notification.dict()
    notif_dict["_id"] = str(uuid.uuid4())
    notif_dict["status"] = "sent"
    notif_dict["sent_at"] = datetime.utcnow()
    notif_dict["created_at"] = datetime.utcnow()
    
    if notification.type == "email":
        logger.info(f"Email sent to {notification.user_email}")
    elif notification.type == "sms":
        logger.info(f"SMS sent to {notification.user_phone}")
    elif notification.type == "push":
        logger.info(f"Push notification sent")
    
    notifications_db.append(notif_dict)
    return notif_dict

@app.get("/api/notifications/user/{user_id}")
def get_user_notifications(user_id: str, limit: int = 50):
    user_notifs = [n for n in notifications_db if n.get("user_id") == user_id]
    return user_notifs[-limit:]

@app.get("/api/notifications/{notification_id}")
def get_notification(notification_id: str):
    for notif in notifications_db:
        if notif.get("_id") == notification_id:
            return notif
    raise HTTPException(status_code=404, detail="Notification not found")

@app.post("/api/notifications/{notification_id}/resend")
def resend_notification(notification_id: str):
    for notif in notifications_db:
        if notif.get("_id") == notification_id:
            notif["status"] = "sent"
            notif["sent_at"] = datetime.utcnow()
            return {"message": "Notification resent", "notification": notif}
    raise HTTPException(status_code=404, detail="Notification not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
