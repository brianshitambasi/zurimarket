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
    return {"service": "ZuriMarket API Gateway", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def catch_all(request: Request, path: str):
    """Catch all requests and route to appropriate service"""
    
    # Determine which service to route to based on path prefix
    if path.startswith("auth/"):
        target_url = f"{AUTH_URL}/{path}"
    elif path.startswith("product/"):
        target_url = f"{PRODUCT_URL}/{path}"
    elif path.startswith("order/"):
        target_url = f"{ORDER_URL}/{path}"
    elif path.startswith("cart/"):
        target_url = f"{CART_URL}/{path}"
    elif path.startswith("payment/"):
        target_url = f"{PAYMENT_URL}/{path}"
    elif path.startswith("notification/"):
        target_url = f"{NOTIFICATION_URL}/{path}"
    elif path.startswith("mpesa/"):
        target_url = f"{MPESA_URL}/{path}"
    elif path.startswith("admin/"):
        target_url = f"{ADMIN_URL}/{path}"
    else:
        return JSONResponse(status_code=404, content={"error": f"Unknown path: {path}"})
    
    logger.info(f"Proxying: {request.method} {target_url}")
    
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
# Force redeploy Fri, Jul 10, 2026  7:54:25 PM
