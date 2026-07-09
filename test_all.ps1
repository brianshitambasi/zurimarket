Write-Host "Testing all ZuriMarket services..." -ForegroundColor Green
Write-Host ""

$services = @(
    @{Name="Auth"; Port=8000},
    @{Name="Product"; Port=8001},
    @{Name="Order"; Port=8002},
    @{Name="Cart"; Port=8003},
    @{Name="Payment"; Port=8004},
    @{Name="Notification"; Port=8005},
    @{Name="M-PESA"; Port=8006},
    @{Name="Gateway"; Port=8080}
)

foreach ($s in $services) {
    $url = "http://localhost:$($s.Port)/health"
    try {
        $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✅ $($s.Name): Running on port $($s.Port)" -ForegroundColor Green
        }
    } catch {
        Write-Host "  ❌ $($s.Name): Not running on port $($s.Port)" -ForegroundColor Red
    }
}
