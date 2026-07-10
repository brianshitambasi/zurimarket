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

# Service URLs - READ FROM ENVIRONMENT
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
async def root():
    return {
        "service": "ZuriMarket API Gateway", 
        "version": "1.0.0",
        "status": "running",
        "endpoints": list(SERVICES.keys())
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "gateway", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    # Parse service from path: service/rest/of/path
    parts = path.split("/", 1)
    service_name = parts[0]
    remaining_path = parts[1] if len(parts) > 1 else ""
    
    if service_name not in SERVICES:
        return JSONResponse(
            status_code=404,
            content={"error": f"Service '{service_name}' not found", "available": list(SERVICES.keys())}
        )
    
    target_url = f"{SERVICES[service_name]}/{remaining_path}"
    logger.info(f"➡️  {request.method} {target_url}")
    
    try:
        body = await request.body() if request.method in ["POST", "PUT", "PATCH"] else None
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ["host", "content-length"]}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params
            )
        
        logger.info(f"✅ {response.status_code}")
        
        try:
            return JSONResponse(status_code=response.status_code, content=response.json())
        except:
            return JSONResponse(status_code=response.status_code, content={"message": response.text[:500]})
            
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"error": "Service timeout"})
    except Exception as e:
        logger.error(f"❌ {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
