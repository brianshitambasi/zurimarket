# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
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
AUTH_URL = os.getenv("AUTH_SERVICE", "https://zurimarket-auth.onrender.com")
PRODUCT_URL = os.getenv("PRODUCT_SERVICE", "https://zurimarket-product.onrender.com")
ORDER_URL = os.getenv("ORDER_SERVICE", "https://zurimarket-order.onrender.com")
CART_URL = os.getenv("CART_SERVICE", "https://zurimarket-cart.onrender.com")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE", "https://zurimarket-payment.onrender.com")
NOTIFICATION_URL = os.getenv("NOTIFICATION_SERVICE", "https://zurimarket-notification.onrender.com")
MPESA_URL = os.getenv("MPESA_SERVICE", "https://zurimarket-mpesa.onrender.com")
ADMIN_URL = os.getenv("ADMIN_SERVICE", "https://zurimarket-admin.onrender.com")

@app.get("/")
def root():
    return {
        "service": "ZuriMarket API Gateway",
        "status": "running",
        "auth_url": AUTH_URL
    }

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request, path: str):
    # Remove trailing slash if present
    if path.endswith('/'):
        path = path[:-1]
    
    # Determine service
    if path.startswith("auth/"):
        service_url = AUTH_URL
        remaining_path = path[5:]  # Remove "auth/"
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("product/"):
        service_url = PRODUCT_URL
        remaining_path = path[8:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("order/"):
        service_url = ORDER_URL
        remaining_path = path[6:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("cart/"):
        service_url = CART_URL
        remaining_path = path[5:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("payment/"):
        service_url = PAYMENT_URL
        remaining_path = path[8:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("notification/"):
        service_url = NOTIFICATION_URL
        remaining_path = path[13:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("mpesa/"):
        service_url = MPESA_URL
        remaining_path = path[6:]
        target_url = f"{service_url}/{remaining_path}"
    elif path.startswith("admin/"):
        service_url = ADMIN_URL
        remaining_path = path[6:]
        target_url = f"{service_url}/{remaining_path}"
    else:
        return JSONResponse(status_code=404, content={
            "error": f"Unknown path: {path}",
            "available": ["auth", "product", "order", "cart", "payment", "notification", "mpesa", "admin"]
        })
    
    logger.info(f"Proxy: {request.method} {target_url}")
    
    try:
        body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=body,
            params=dict(request.query_params),
            timeout=30
        )
        
        try:
            return JSONResponse(
                status_code=response.status_code,
                content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"message": response.text[:100]}
            )
        except:
            return JSONResponse(
                status_code=response.status_code,
                content={"message": response.text[:100]}
            )
        
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
