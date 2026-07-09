@echo off
echo ============================================
echo Starting ZuriMarket All Services
echo ============================================
echo.

echo [1/6] Starting Auth Service on port 8000...
start "Auth Service" cmd /k "cd backend\services\auth-service && python -m uvicorn app.fixed:app --reload --port 8000"
timeout /t 3

echo [2/6] Starting Product Service on port 8001...
start "Product Service" cmd /k "cd backend\services\product-service && python -m uvicorn app.fixed_product:app --reload --port 8001"
timeout /t 3

echo [3/6] Starting Order Service on port 8002...
start "Order Service" cmd /k "cd backend\services\order-service && python -m uvicorn app.main:app --reload --port 8002"
timeout /t 3

echo [4/6] Starting Cart Service on port 8003...
start "Cart Service" cmd /k "cd backend\services\cart-service && python -m uvicorn app.main:app --reload --port 8003"
timeout /t 3

echo [5/6] Starting Payment Service on port 8004...
start "Payment Service" cmd /k "cd backend\services\payment-service && python -m uvicorn app.main:app --reload --port 8004"
timeout /t 3

echo [6/6] Starting Notification Service on port 8005...
start "Notification Service" cmd /k "cd backend\services\notification-service && python -m uvicorn app.main:app --reload --port 8005"
timeout /t 3

echo.
echo ============================================
echo All services started successfully!
echo ============================================
echo.
echo í³Š Services Running:
echo.
echo   Auth:        http://localhost:8000/docs
echo   Product:     http://localhost:8001/docs
echo   Order:       http://localhost:8002/docs
echo   Cart:        http://localhost:8003/docs
echo   Payment:     http://localhost:8004/docs
echo   Notification: http://localhost:8005/docs
echo.
echo í·ª Run tests: python test_all_services.py
echo.
echo Press any key to close this window...
pause
