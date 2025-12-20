#!/bin/bash
# Migration script to copy environment variables from existing .env to new structure

echo "🔄 Migrating environment variables..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    exit 1
fi

# Source the existing .env
source .env

# Create backend .env
cat > backend/.env << EOF
# Migrated from existing .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/depodigest
REDIS_URL=redis://localhost:6379

# API Keys (from existing .env)
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
GOOGLE_API_KEY=${GOOGLE_API_KEY:-}

# Server Configuration
API_HOST=0.0.0.0
API_PORT=8000
WORKERS_COUNT=4
FRONTEND_URL=http://localhost:3000

# Performance
MAX_CONCURRENT_AI_REQUESTS=50
CACHE_TTL_DAYS=30
LOG_LEVEL=INFO
EOF

# Create frontend .env
cat > frontend/.env.local << EOF
# Migrated from existing .env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
EOF

echo "✅ Environment variables migrated successfully!"
echo ""
echo "Created files:"
echo "  - backend/.env"
echo "  - frontend/.env.local"
echo ""
echo "You can now run: docker-compose up -d"








