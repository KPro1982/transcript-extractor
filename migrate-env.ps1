# PowerShell migration script for Windows
# Copies environment variables from existing .env to new structure

Write-Host "🔄 Migrating environment variables..." -ForegroundColor Cyan

# Check if .env exists
if (-not (Test-Path .env)) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    exit 1
}

# Read existing .env
$envContent = Get-Content .env
$envVars = @{}

foreach ($line in $envContent) {
    if ($line -match '^([^=]+)=(.*)$') {
        $envVars[$matches[1]] = $matches[2]
    }
}

# Get API key
$openaiKey = $envVars['OPENAI_API_KEY']
if (-not $openaiKey) {
    $openaiKey = $envVars['VITE_OPENAI_API_KEY']
}

if (-not $openaiKey) {
    Write-Host "⚠️  Warning: OPENAI_API_KEY not found in .env" -ForegroundColor Yellow
}

# Create backend .env
$backendEnv = @"
# Migrated from existing .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/depodigest
REDIS_URL=redis://localhost:6379

# API Keys (from existing .env)
OPENAI_API_KEY=$openaiKey
ANTHROPIC_API_KEY=$($envVars['ANTHROPIC_API_KEY'])
GOOGLE_API_KEY=$($envVars['GOOGLE_API_KEY'])

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
WORKERS_COUNT=4
FRONTEND_URL=http://localhost:3000

# Performance
MAX_CONCURRENT_AI_REQUESTS=50
CACHE_TTL_DAYS=30
LOG_LEVEL=INFO
"@

# Create frontend .env.local
$frontendEnv = @"
# Migrated from existing .env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
"@

# Ensure directories exist
New-Item -ItemType Directory -Force -Path backend | Out-Null
New-Item -ItemType Directory -Force -Path frontend | Out-Null

# Write files
$backendEnv | Out-File -FilePath backend/.env -Encoding UTF8
$frontendEnv | Out-File -FilePath frontend/.env.local -Encoding UTF8

Write-Host "✅ Environment variables migrated successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Created files:"
Write-Host "  - backend/.env"
Write-Host "  - frontend/.env.local"
Write-Host ""
Write-Host "Your OpenAI API Key: $($openaiKey.Substring(0, 10))..." -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run: docker-compose up -d" -ForegroundColor Yellow

