# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ZuriMarket API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service URLs
AUTH_SERVICE = os.getenv("AUTH_SERVICE", "https://zurimarket-auth.onrender.com")

@app.get("/")
def root():
    return {"service": "ZuriMarket API Gateway", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}

# Direct routing for auth
@app.post("/auth/api/auth/register")
async def auth_register(request: Request):
    try:
        body = await request.body()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVICE}/api/auth/register",
                content=body,
                headers={"Content-Type": "application/json"}
            )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/auth/api/auth/login")
async def auth_login(request: Request):
    try:
        body = await request.body()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AUTH_SERVICE}/api/auth/login",
                content=body,
                headers={"Content-Type": "application/json"}
            )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/auth/api/auth/me")
async def auth_me(request: Request):
    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{AUTH_SERVICE}/api/auth/me",
                headers=headers
            )
        return JSONResponse(status_code=response.status_code, content=response.json())
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Proxy for all other services
@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, service_name: str, path: str):
    service_url = {
        "product": os.getenv("PRODUCT_SERVICE", "https://zurimarket-product.onrender.com"),
        "order": os.getenv("ORDER_SERVICE", "https://zurimarket-order.onrender.com"),
        "cart": os.getenv("CART_SERVICE", "https://zurimarket-cart.onrender.com"),
        "payment": os.getenv("PAYMENT_SERVICE", "https://zurimarket-payment.onrender.com"),
        "notification": os.getenv("NOTIFICATION_SERVICE", "https://zurimarket-notification.onrender.com"),
        "mpesa": os.getenv("MPESA_SERVICE", "https://zurimarket-mpesa.onrender.com"),
        "admin": os.getenv("ADMIN_SERVICE", "https://zurimarket-admin.onrender.com"),
    }.get(service_name)
    
    if not service_url:
        return JSONResponse(status_code=404, content={"error": f"Service '{service_name}' not found"})
    
    target_url = f"{service_url}/{path}"
    
    try:
        body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
        
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"message": response.text[:100]}
        )
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
