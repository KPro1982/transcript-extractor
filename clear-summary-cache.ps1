# Clear summary cache to force regeneration
$API_URL = "https://backend-production-e4c7.up.railway.app"

Write-Host "Clearing summary cache..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "$API_URL/api/cache/clear?cache_type=summaries" -Method Post
    Write-Host "Success!" -ForegroundColor Green
    Write-Host "Cleared $($response.keys_deleted) cached summaries" -ForegroundColor Green
    Write-Host ""
    Write-Host "Now re-upload your document and it will generate fresh summaries." -ForegroundColor Cyan
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
}





