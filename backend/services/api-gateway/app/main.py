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

# Service URLs - INCLUDING MPESA
SERVICES = {
    "auth": "http://localhost:8000",
    "product": "http://localhost:8001",
    "order": "http://localhost:8002",
    "cart": "http://localhost:8003",
    "payment": "http://localhost:8004",
    "notification": "http://localhost:8005",
    "mpesa": "http://localhost:8006",  # Added M-PESA service
}

# Rate limiting
rate_limits = {}

def check_rate_limit(client_ip: str, limit: int = 100, window: int = 60):
    key = f"{client_ip}:{window}"
    now = datetime.utcnow().timestamp()
    
    if key not in rate_limits:
        rate_limits[key] = []
    
    rate_limits[key] = [t for t in rate_limits[key] if t > now - window]
    
    if len(rate_limits[key]) >= limit:
        return False
    
    rate_limits[key].append(now)
    return True

@app.get("/")
def root():
    return {
        "service": "ZuriMarket API Gateway",
        "version": "1.0.0",
        "status": "running",
        "services": SERVICES
    }

@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway", "timestamp": datetime.utcnow().isoformat()}

@app.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, service_name: str, path: str):
    # Check rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Please try again later."}
        )
    
    if service_name not in SERVICES:
        return JSONResponse(
            status_code=404,
            content={"error": f"Service '{service_name}' not found. Available: {list(SERVICES.keys())}"}
        )
    
    service_url = SERVICES[service_name]
    target_url = f"{service_url}/{path}"
    
    try:
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
        
        headers = dict(request.headers)
        headers.pop("host", None)
        headers.pop("content-length", None)
        
        # Make request using requests
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=body if body else None,
            params=dict(request.query_params),
            timeout=30
        )
        
        logger.info(f"OK {request.method} /{service_name}/{path} -> {response.status_code}")
        
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"message": response.text[:100]}
        )
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout: {service_name}/{path}")
        return JSONResponse(
            status_code=504,
            content={"error": "Service timeout"}
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
