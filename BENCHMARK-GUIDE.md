# Performance Benchmark Guide

This guide explains how to run the comprehensive performance benchmark that validates the predicted 6.4x speedup from the old Node.js system to the new FastAPI system.

## Quick Start

```bash
# 1. Install benchmark dependencies
pip install -r requirements-benchmark.txt

# 2. Run the benchmark (it will auto-start both systems)
python benchmark_systems.py

# 3. View results
type benchmark_report.md  # Windows
cat benchmark_report.md   # Linux/Mac
```

## What It Tests

### 1. Initial Processing Speed (6.4x Expected)
- Uploads the Buksh transcript to both old and new systems
- Measures end-to-end processing time
- Validates new system is ≥5.1x faster (6.4x with 20% tolerance)

### 2. Caching Performance (4.7x Expected)
- Uploads the same document twice to new system
- Measures speedup from Redis caching
- Validates cached run is ≥3.8x faster (4.7x with 20% tolerance)

### 3. Result Accuracy
- Compares Q&A pairs extracted by both systems
- Validates count difference is <10%
- Ensures migration maintains data quality

### 4. Resource Usage
- Monitors CPU and memory during processing
- Compares peak usage between systems
- Provides insight into efficiency gains

## System Requirements

### Software
- Python 3.8+
- Node.js 16+ (for old system)
- Docker + Docker Compose (for new system)
- 8GB+ RAM recommended

### Ports
- **3001**: Old Node.js system
- **8000**: New FastAPI backend
- **3000**: New Next.js frontend (optional)
- **5432**: PostgreSQL (Docker)
- **6379**: Redis (Docker)

## Test PDF

The benchmark uses:
```
Transcripts/Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf
```

**Why this PDF?**
- Real deposition transcript
- Abridged version (manageable size for repeated testing)
- Contains actual Q&A structure
- Typical of production use cases

To use a different PDF, edit `TEST_PDF` in `benchmark_systems.py`.

## Understanding Results

### Benchmark Report (`benchmark_report.md`)

The report includes:

#### Executive Summary
- ✅/⚠️ Overall pass/fail status
- Key metrics comparison table
- Actual vs expected improvements

#### Detailed Results
- Old System: Processing time, Q&A pairs, resources
- New System Run 1: Initial processing (cold cache)
- New System Run 2: Cached processing (warm cache)

#### Performance Visualization
Text-based bar charts showing relative speeds:
```
Old System (Initial):    ████████████████████ 210.0s
New System (Initial):    ███ 33.0s
New System (Cached):     █ 7.0s
```

#### Validation Results
Pass/fail for each test:
- ✅ Initial Speedup: 6.4x faster
- ✅ Cache Speedup: 4.7x faster  
- ✅ Result Accuracy: Q&A count matches
- ℹ️ Memory Usage: (informational)

### Raw Data (`benchmark_results.json`)

Complete benchmark data including:
- Timestamps for each operation
- Full resource monitoring samples
- Error details (if any)
- System configuration

## Troubleshooting

### Old System Won't Start

**Issue:** Port 3001 already in use
```bash
# Windows
netstat -ano | findstr :3001
taskkill /F /PID <PID>

# Linux/Mac
lsof -ti:3001 | xargs kill -9
```

**Issue:** Missing dependencies
```bash
npm install
```

### New System Won't Start

**Issue:** Docker not running
```bash
# Windows: Start Docker Desktop
# Linux: 
sudo systemctl start docker
```

**Issue:** Ports conflict
```bash
# Stop existing containers
docker-compose down

# Check what's using ports
# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :5432

# Linux/Mac  
lsof -ti:8000
lsof -ti:5432
```

**Issue:** Services not healthy
```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs backend
docker-compose logs worker
docker-compose logs db
docker-compose logs redis

# Rebuild if needed
docker-compose down -v
docker-compose build
docker-compose up -d
```

### Benchmark Fails During Run

**Issue:** API timeout
- Check service logs: `docker-compose logs -f worker`
- Increase timeout in script if processing large PDF
- Verify OpenAI API key is valid

**Issue:** OpenAI rate limit
- The benchmark makes real API calls
- Expect $0.10-$0.50 in API costs per full run
- Rate limits: Wait and retry
- Consider using smaller test PDF

**Issue:** Memory exhaustion
- Close other applications
- Reduce Docker resource limits
- Use smaller test PDF

### Results Don't Meet Expectations

**Possible causes:**

1. **System Resources Constrained**
   - Close background applications
   - Check CPU/RAM availability
   - Ensure Docker has sufficient resources

2. **Different PDF Size**
   - Original estimates based on 200-page documents
   - Adjust expectations for document size
   - Run multiple tests with different PDFs

3. **Network Latency**
   - OpenAI API calls affected by internet speed
   - Try during off-peak hours
   - Check for VPN/proxy interference

4. **Cold Start Effects**
   - First run may include initialization overhead
   - Run benchmark multiple times
   - Average results across runs

## Advanced Usage

### Custom Test PDF

```python
# Edit benchmark_systems.py
TEST_PDF = "path/to/your/test.pdf"
```

### Adjust Tolerance

```python
# Edit benchmark_systems.py
TOLERANCE = 0.2  # 20% tolerance (default)
TOLERANCE = 0.3  # 30% tolerance (more lenient)
```

### Manual System Control

```bash
# Start systems manually before running benchmark
# This gives you more control

# Terminal 1: Old system
$env:PORT=3001
node server.js

# Terminal 2: New system  
docker-compose up

# Terminal 3: Run benchmark (will detect running systems)
python benchmark_systems.py
```

### Multiple Test Runs

```bash
# Run 5 times and average results
for /L %i in (1,1,5) do python benchmark_systems.py

# Save each result
python benchmark_systems.py
move benchmark_results.json results_run1.json
move benchmark_report.md report_run1.md

# Repeat...
```

## Expected Costs

### OpenAI API Costs (per run)
- Old System: ~$0.20-0.40 (depending on PDF size)
- New System Run 1: ~$0.20-0.40 (initial)
- New System Run 2: ~$0.04-0.08 (80% cached)

**Total per benchmark:** ~$0.50-1.00

## Interpreting Success

### ✅ Full Success
All tests pass:
- Initial speedup ≥5.1x (80% of 6.4x target)
- Cache speedup ≥3.8x (80% of 4.7x target)
- Q&A accuracy within 10%

**Conclusion:** Migration successful, predictions verified!

### ⚠️ Partial Success
Some tests pass, some marginal:
- Speedup is 4-5x (still significant!)
- Cache works but less dramatic
- Accuracy is good

**Conclusion:** Migration successful, adjust expectations based on actual environment.

### ❌ Failure
Tests don't pass:
- Speedup <3x
- Cache not working
- Accuracy issues

**Action needed:** Review system configuration, check logs, may need optimization.

## What's Next?

After validating performance:

1. **Document Actual Performance**
   - Update README with real measurements
   - Adjust marketing claims if needed
   - Set realistic user expectations

2. **Production Deployment**
   - See `README-DEPLOYMENT.md`
   - Monitor real-world performance
   - Adjust worker scaling as needed

3. **Further Optimization**
   - Tune worker concurrency
   - Adjust cache settings
   - Optimize database queries

## Support

**Issues?** 
- Check `docker-compose logs`
- Review `benchmark_results.json` 
- Examine detailed error messages

**Questions?**
- See main `README.md` for system architecture
- See `MIGRATION-GUIDE.md` for migration details
- See `START-HERE.md` for quick start

---

**Remember:** The benchmark makes real API calls and costs real money. Budget $0.50-1.00 per run for OpenAI API usage.












