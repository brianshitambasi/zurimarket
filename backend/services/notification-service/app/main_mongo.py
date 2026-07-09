# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from datetime import datetime
import uuid
import logging
import os
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket Notification Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("MONGODB_DB", "zurimarket")

client = None
db = None

@app.on_event("startup")
async def startup():
    global client, db
    try:
        client = AsyncIOMotorClient(MONGODB_URL)
        db = client[DATABASE_NAME]
        
        # Create indexes using correct syntax
        await db.notifications.create_index([("user_id", 1)])
        await db.notifications.create_index([("created_at", -1)])
        await db.notifications.create_index([("status", 1)])
        
        logger.info("MongoDB connected for Notification Service")
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown():
    if client:
        client.close()
        logger.info("MongoDB disconnected")

class NotificationCreate(BaseModel):
    user_id: str
    user_email: Optional[EmailStr] = None
    user_phone: Optional[str] = None
    type: str
    title: str
    message: str
    data: Optional[Dict] = None

class NotificationUpdate(BaseModel):
    status: Optional[str] = None

@app.get("/")
def root():
    return {"service": "Notification Service", "database": "mongodb", "status": "running"}

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "notification-service",
        "database": "mongodb",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/notifications/send")
async def send_notification(notification: NotificationCreate):
    logger.info(f"Sending notification to {notification.user_id}")
    
    try:
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
            logger.info("Push notification sent")
        
        await db.notifications.insert_one(notif_dict)
        notif_dict["_id"] = str(notif_dict["_id"])
        return notif_dict
        
    except Exception as e:
        logger.error(f"Send notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notifications/user/{user_id}")
async def get_user_notifications(user_id: str, limit: int = 50, skip: int = 0):
    try:
        cursor = db.notifications.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
        notifications = await cursor.to_list(length=limit)
        
        for notif in notifications:
            notif["_id"] = str(notif["_id"])
        
        total = await db.notifications.count_documents({"user_id": user_id})
        
        return {
            "notifications": notifications,
            "total": total,
            "limit": limit,
            "skip": skip
        }
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notifications/{notification_id}")
async def get_notification(notification_id: str):
    try:
        notification = await db.notifications.find_one({"_id": notification_id})
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        notification["_id"] = str(notification["_id"])
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/notifications/{notification_id}")
async def update_notification(notification_id: str, update: NotificationUpdate):
    try:
        if update.status:
            result = await db.notifications.update_one(
                {"_id": notification_id},
                {"$set": {"status": update.status}}
            )
            if result.matched_count == 0:
                raise HTTPException(status_code=404, detail="Notification not found")
        
        notification = await db.notifications.find_one({"_id": notification_id})
        notification["_id"] = str(notification["_id"])
        return notification
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notifications/{notification_id}/resend")
async def resend_notification(notification_id: str):
    try:
        notification = await db.notifications.find_one({"_id": notification_id})
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        await db.notifications.update_one(
            {"_id": notification_id},
            {
                "$set": {
                    "status": "sent",
                    "sent_at": datetime.utcnow()
                }
            }
        )
        
        notification["_id"] = str(notification["_id"])
        return {"message": "Notification resent", "notification": notification}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend notification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
