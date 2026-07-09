# -*- coding: utf-8 -*-
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse
import time
from datetime import datetime
import logging
import os
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Metrics
REQUEST_COUNT = Counter(
    'zurimarket_requests_total',
    'Total request count',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'zurimarket_request_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'zurimarket_active_requests',
    'Active requests'
)

USER_COUNT = Gauge(
    'zurimarket_users_total',
    'Total number of users'
)

PRODUCT_COUNT = Gauge(
    'zurimarket_products_total',
    'Total number of products'
)

ORDER_COUNT = Gauge(
    'zurimarket_orders_total',
    'Total number of orders'
)

async def monitor_middleware(request: Request, call_next):
    """Middleware for monitoring"""
    start_time = time.time()
    
    # Increment active requests
    ACTIVE_REQUESTS.inc()
    
    try:
        response = await call_next(request)
        
        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(time.time() - start_time)
        
        return response
        
    except Exception as e:
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=500
        ).inc()
        raise
        
    finally:
        # Decrement active requests
        ACTIVE_REQUESTS.dec()

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return FastAPIResponse(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

def update_metrics():
    """Update business metrics"""
    try:
        # Update user count
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="zurimarket",
            user="zuri",
            password="zuripass",
            port=5432
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        USER_COUNT.set(cur.fetchone()[0])
        cur.close()
        conn.close()
    except:
        pass
    
    try:
        # Update product count
        from motor.motor_asyncio import AsyncIOMotorClient
        import asyncio
        client = AsyncIOMotorClient("mongodb://localhost:27017")
        db = client["zurimarket"]
        count = asyncio.run(db.products.count_documents({}))
        PRODUCT_COUNT.set(count)
        client.close()
    except:
        pass
    
    try:
        # Update order count
        conn = psycopg2.connect(
            host="localhost",
            database="zurimarket",
            user="zuri",
            password="zuripass",
            port=5432
        )
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM orders")
        ORDER_COUNT.set(cur.fetchone()[0])
        cur.close()
        conn.close()
    except:
        pass
