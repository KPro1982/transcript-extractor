# Deploy DepoDigest

Choose your deployment method and get started!

## 🚂 Railway (Recommended)

Deploy to Railway for a managed, production-ready environment.

### Start Here
1. **[RAILWAY-QUICKSTART.md](RAILWAY-QUICKSTART.md)** - Deploy in 30 minutes
2. **[RAILWAY-DEPLOYMENT.md](RAILWAY-DEPLOYMENT.md)** - Complete detailed guide
3. **[RAILWAY-CHECKLIST.md](RAILWAY-CHECKLIST.md)** - Ensure nothing is missed

### Tools & Resources
- **[railway-deploy.sh](railway-deploy.sh)** / **[railway-deploy.ps1](railway-deploy.ps1)** - Automated deployment scripts
- **[railway-env-template.txt](railway-env-template.txt)** - Environment variables template
- **[validate-railway-deployment.py](validate-railway-deployment.py)** - Validation script

### Quick Deploy

**Windows:**
```powershell
# Install Railway CLI
npm install -g @railway/cli
railway login

# Deploy
.\railway-deploy.ps1
```

**Mac/Linux:**
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Deploy
bash railway-deploy.sh
```

**Cost:** ~$23-35/month for development, ~$50-100/month for production

---

## 🐳 Docker (Local Development)

Run locally with Docker for development and testing.

### Quick Start
```bash
# Clone repository
git clone <repo-url>
cd depodigest

# Configure environment
cp backend/.env.example backend/.env
# Add your OPENAI_API_KEY to backend/.env

# Start all services
docker-compose up -d

# Access
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Documentation
- **[README-LOCAL.md](README-LOCAL.md)** - Complete local development guide
- **[docker-compose.yml](docker-compose.yml)** - Service configuration

**Cost:** Free (local machine resources only)

---

## ☁️ AWS / GCP / Azure (Enterprise)

Deploy to major cloud providers for enterprise requirements.

### AWS Deployment
- **ECS/Fargate** - Container orchestration
- **RDS** - Managed PostgreSQL
- **ElastiCache** - Managed Redis
- **S3** - File storage
- **CloudFront** - CDN for frontend

### GCP Deployment
- **Cloud Run** - Serverless containers
- **Cloud SQL** - Managed PostgreSQL
- **Memorystore** - Managed Redis
- **Cloud Storage** - File storage

### Azure Deployment
- **Container Instances** - Container hosting
- **Azure Database** - Managed PostgreSQL
- **Azure Cache** - Managed Redis
- **Blob Storage** - File storage

### Prerequisites
- Cloud account with appropriate permissions
- Infrastructure as Code tools (Terraform/CloudFormation)
- CI/CD pipeline setup

**Documentation:** Contact for enterprise deployment guide

**Cost:** Varies by usage, typically $100-500/month

---

## 🔧 VPS / Dedicated Server

Deploy to your own server with full control.

### Prerequisites
- Ubuntu 20.04+ or similar Linux distribution
- Docker and Docker Compose installed
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt)

### Installation Steps

1. **Install Docker**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

2. **Clone and Configure**
```bash
git clone <repo-url>
cd depodigest
cp backend/.env.example backend/.env
# Edit backend/.env with your settings
```

3. **Deploy**
```bash
docker-compose up -d
```

4. **Setup Nginx (optional)**
```bash
sudo apt install nginx certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### Monitoring
- Use tools like Grafana, Prometheus
- Set up log aggregation
- Configure backup systems

**Cost:** Server cost + $5-20/month for monitoring tools

---

## 📊 Comparison

| Method | Ease | Cost/Month | Scalability | Maintenance | Best For |
|--------|------|------------|-------------|-------------|----------|
| **Railway** | ⭐⭐⭐⭐⭐ | $23-100 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Most users |
| **Docker Local** | ⭐⭐⭐⭐ | Free | ⭐ | ⭐⭐⭐ | Development |
| **AWS/GCP/Azure** | ⭐⭐ | $100-500 | ⭐⭐⭐⭐⭐ | ⭐⭐ | Enterprise |
| **VPS** | ⭐⭐⭐ | $20-100 | ⭐⭐⭐ | ⭐⭐ | Tech-savvy users |

---

## 🎯 Recommended Path

### For Beginners
1. Start with **Docker Local** to understand the system
2. Move to **Railway** for production deployment
3. Follow [RAILWAY-QUICKSTART.md](RAILWAY-QUICKSTART.md)

### For Developers
1. Use **Docker Local** for development
2. Deploy to **Railway** for staging
3. Scale to **AWS/GCP** if needed for production

### For Enterprises
1. Start with **Railway** for proof of concept
2. Plan **AWS/GCP/Azure** deployment
3. Implement full CI/CD and monitoring

---

## ✅ Post-Deployment

After deploying, ensure everything works:

### 1. Run Validation
```bash
# For Railway deployments
python validate-railway-deployment.py \
  --backend https://your-backend-url \
  --frontend https://your-frontend-url

# For local deployments
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed
```

### 2. Test Upload Workflow
1. Go to your frontend URL
2. Upload a test PDF (sample deposition transcript)
3. Monitor processing progress
4. Verify results are correct

### 3. Monitor Performance
- Check response times
- Review logs for errors
- Monitor resource usage
- Test under load

### 4. Set Up Monitoring
- Configure uptime monitoring
- Set up error tracking (Sentry)
- Enable log aggregation
- Create alerting rules

---

## 🆘 Need Help?

### Railway Deployment
- [RAILWAY-QUICKSTART.md](RAILWAY-QUICKSTART.md) - Quick start guide
- [RAILWAY-DEPLOYMENT.md](RAILWAY-DEPLOYMENT.md) - Detailed guide
- [RAILWAY-CHECKLIST.md](RAILWAY-CHECKLIST.md) - Deployment checklist
- Railway Discord: https://discord.gg/railway

### Local Development
- [README-LOCAL.md](README-LOCAL.md) - Local setup guide
- [README.md](README.md) - Main documentation

### General
- [README.md](README.md) - Architecture and overview
- [MIGRATION-GUIDE.md](MIGRATION-GUIDE.md) - Migration from v1.0
- GitHub Issues - Report bugs or request features

---

## 🚀 Let's Deploy!

Choose your deployment method above and get started. We recommend most users start with **Railway** for the best balance of ease and functionality.

**Ready?** Start with [RAILWAY-QUICKSTART.md](RAILWAY-QUICKSTART.md) →

