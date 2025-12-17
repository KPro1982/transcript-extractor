# Railway Deployment Validation Script (PowerShell)
# Tests all deployed services to ensure they're working correctly

param(
    [Parameter(Mandatory=$true)]
    [string]$BackendUrl,
    
    [Parameter(Mandatory=$true)]
    [string]$FrontendUrl
)

$ErrorActionPreference = "Continue"

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host $Text -ForegroundColor Cyan -BackgroundColor Black
    Write-Host ("=" * $Text.Length) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "✅ $Text" -ForegroundColor Green
}

function Write-Failure {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor Red
}

function Write-Warning-Custom {
    param([string]$Text)
    Write-Host "⚠️  $Text" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ️  $Text" -ForegroundColor Blue
}

# Track results
$script:TotalChecks = 0
$script:PassedChecks = 0

function Test-Check {
    param([bool]$Result, [string]$Name)
    $script:TotalChecks++
    if ($Result) {
        $script:PassedChecks++
        Write-Success $Name
    } else {
        Write-Failure $Name
    }
}

Write-Host ""
Write-Host "🚂 Railway Deployment Validation" -ForegroundColor Cyan -BackgroundColor Black
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""
Write-Info "Backend URL:  $BackendUrl"
Write-Info "Frontend URL: $FrontendUrl"

# Check Backend Health
Write-Header "Checking Backend Health"

$backendHealthy = $false
$databaseHealthy = $false
$cacheHealthy = $false
$responseTime = 0

try {
    $startTime = Get-Date
    $response = Invoke-WebRequest -Uri "$BackendUrl/health" -TimeoutSec 30 -UseBasicParsing
    $endTime = Get-Date
    $responseTime = ($endTime - $startTime).TotalMilliseconds
    
    if ($response.StatusCode -eq 200) {
        $data = $response.Content | ConvertFrom-Json
        Write-Success "Basic health check passed ($([math]::Round($responseTime))ms)"
        Write-Info "Service: $($data.service), Version: $($data.version)"
        $backendHealthy = $true
    }
} catch {
    Write-Failure "Basic health check failed: $_"
}

if ($backendHealthy) {
    try {
        $response = Invoke-WebRequest -Uri "$BackendUrl/health/detailed" -TimeoutSec 30 -UseBasicParsing
        
        if ($response.StatusCode -eq 200) {
            $data = $response.Content | ConvertFrom-Json
            Write-Success "Detailed health check passed"
            
            if ($data.services.database -eq "healthy") {
                Write-Success "Database connection: OK"
                $databaseHealthy = $true
            } else {
                Write-Failure "Database connection: $($data.services.database)"
            }
            
            if ($data.services.cache -eq "healthy") {
                Write-Success "Redis cache connection: OK"
                $cacheHealthy = $true
            } else {
                Write-Failure "Redis cache connection: $($data.services.cache)"
            }
        }
    } catch {
        Write-Failure "Detailed health check failed: $_"
    }
}

# Check Frontend
Write-Header "Checking Frontend"

$frontendHealthy = $false
try {
    $startTime = Get-Date
    $response = Invoke-WebRequest -Uri $FrontendUrl -TimeoutSec 30 -UseBasicParsing
    $endTime = Get-Date
    $responseTime = ($endTime - $startTime).TotalMilliseconds
    
    if ($response.StatusCode -eq 200) {
        Write-Success "Frontend is accessible ($([math]::Round($responseTime))ms)"
        
        if ($response.Content -match "<!DOCTYPE html>" -or $response.Content -match "<html") {
            Write-Success "HTML content detected"
            $frontendHealthy = $true
        } else {
            Write-Warning-Custom "Received response but no HTML content found"
        }
    }
} catch {
    Write-Failure "Frontend check failed: $_"
}

# Check CORS
Write-Header "Checking CORS Configuration"

$corsHealthy = $false
try {
    $headers = @{
        "Origin" = $FrontendUrl
        "Access-Control-Request-Method" = "GET"
    }
    $response = Invoke-WebRequest -Uri "$BackendUrl/health" -Method Options -Headers $headers -TimeoutSec 10 -UseBasicParsing
    
    $allowOrigin = $response.Headers["Access-Control-Allow-Origin"]
    if ($allowOrigin) {
        Write-Success "CORS is configured"
        Write-Info "Allowed Origin: $allowOrigin"
        $corsHealthy = $true
    } else {
        Write-Warning-Custom "CORS headers not found in response"
    }
} catch {
    Write-Warning-Custom "CORS check failed: $_"
}

# Check API Endpoints
Write-Header "Checking API Endpoints"

$endpoints = @("/api/documents", "/api/jobs")
$apiHealthy = $true

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-WebRequest -Uri "$BackendUrl$endpoint" -TimeoutSec 30 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -lt 500) {
            Write-Success "$endpoint`: Accessible (HTTP $($response.StatusCode))"
        } else {
            Write-Failure "$endpoint`: Server error (HTTP $($response.StatusCode))"
            $apiHealthy = $false
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -lt 500) {
            Write-Success "$endpoint`: Accessible (HTTP $statusCode)"
        } else {
            Write-Failure "$endpoint`: Failed"
            $apiHealthy = $false
        }
    }
}

# Summary
Write-Header "Deployment Validation Summary"

Test-Check -Result $backendHealthy -Name "Basic health"
Test-Check -Result $backendHealthy -Name "Detailed health"
Test-Check -Result $databaseHealthy -Name "Database connection"
Test-Check -Result $cacheHealthy -Name "Cache connection"
Test-Check -Result $frontendHealthy -Name "Frontend accessible"
Test-Check -Result $corsHealthy -Name "CORS configured"
Test-Check -Result $apiHealthy -Name "API endpoints"

Write-Host ""
$scorePercentage = if ($script:TotalChecks -gt 0) { ($script:PassedChecks / $script:TotalChecks * 100) } else { 0 }

if ($scorePercentage -eq 100) {
    Write-Success "All checks passed! ($script:PassedChecks/$script:TotalChecks)"
    Write-Success "🎉 Your deployment is ready for production!"
    exit 0
} elseif ($scorePercentage -ge 75) {
    Write-Warning-Custom "Most checks passed ($script:PassedChecks/$script:TotalChecks - $([math]::Round($scorePercentage))%)"
    Write-Info "Review the failed checks above and fix any issues"
    exit 1
} else {
    Write-Failure "Many checks failed ($script:PassedChecks/$script:TotalChecks - $([math]::Round($scorePercentage))%)"
    Write-Info "Your deployment needs attention. Review logs and configuration."
    exit 1
}

