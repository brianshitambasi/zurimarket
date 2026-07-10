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

SERVICES = {
    "auth": os.getenv("AUTH_SERVICE", "https://zurimarket-auth.onrender.com"),
    "product": os.getenv("PRODUCT_SERVICE", "https://zurimarket-product.onrender.com"),
    "order": os.getenv("ORDER_SERVICE", "https://zurimarket-order.onrender.com"),
    "cart": os.getenv("CART_SERVICE", "https://zurimarket-cart.onrender.com"),
    "payment": os.getenv("PAYMENT_SERVICE", "https://zurimarket-payment.onrender.com"),
    "notification": os.getenv("NOTIFICATION_SERVICE", "https://zurimarket-notification.onrender.com"),
    "mpesa": os.getenv("MPESA_SERVICE", "https://zurimarket-mpesa.onrender.com"),
    "admin": os.getenv("ADMIN_SERVICE", "https://zurimarket-admin.onrender.com"),
}

@app.get("/")
def root():
    return {"service": "ZuriMarket API Gateway", "services": list(SERVICES.keys())}

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, service_name: str, path: str):
    if service_name not in SERVICES:
        return JSONResponse(
            status_code=404,
            content={"error": f"Service '{service_name}' not found. Available: {list(SERVICES.keys())}"}
        )
    
    service_url = SERVICES[service_name]
    target_url = f"{service_url}/{path}"
    
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
        
        logger.info(f"Response: {response.status_code}")
        
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
        
    except requests.exceptions.Timeout:
        return JSONResponse(status_code=504, content={"error": "Service timeout"})
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
