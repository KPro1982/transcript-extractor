# Multi-Worker Parallel Processing Setup Guide

## Overview

DepoDigest now supports multi-worker parallel processing with document chunking. This feature allows large documents to be split into chunks and processed simultaneously across multiple workers, each using a separate OpenAI API key to avoid rate limit conflicts.

## Speed Improvements

With 3 API keys and 3 workers:
- **3× faster processing** for large documents (>500 Q&A pairs)
- Each worker gets its own rate limit bucket (500 RPM, 200k TPM)
- Total throughput: 1500 RPM, 600k TPM

Example: 1000 Q&A pairs
- Single worker: ~6-8 minutes
- 3 workers (3 keys): ~2-3 minutes
- **Speed multiplier: ~3×**

## How It Works

### Automatic Chunking

The system automatically determines when to use chunking:
1. Document must have >500 Q&A pairs (configurable)
2. Multiple API keys must be available
3. Document must have >100 pages

When conditions are met:
- Document is split into N chunks (one per available API key)
- Each chunk is assigned to a different worker
- Workers process chunks in parallel using separate API keys
- Results are merged automatically when all chunks complete

### Worker Key Assignment

Each worker is assigned an API key based on its `WORKER_ID`:
- Worker 0 → `OPENAI_API_KEY_1` (or `OPENAI_API_KEY`)
- Worker 1 → `OPENAI_API_KEY_2`
- Worker 2 → `OPENAI_API_KEY_3`

## Configuration

### Local Development

Add to `backend/.env`:

```bash
# Worker Configuration
WORKER_ID=0  # Set to 0, 1, or 2 depending on worker

# Multi-key support (3 keys for 3× speed)
OPENAI_API_KEY=sk-proj-your-first-key   # Worker 0 (backward compatible)
OPENAI_API_KEY_1=sk-proj-your-first-key  # Worker 0
OPENAI_API_KEY_2=sk-proj-your-second-key  # Worker 1
OPENAI_API_KEY_3=sk-proj-your-third-key   # Worker 2

# Chunking configuration (optional, has defaults)
ENABLE_CHUNKING=true
CHUNKING_THRESHOLD=500  # Min Q&A pairs to trigger chunking
MAX_CHUNKS=3            # Max chunks per document
```

### Railway Deployment

You need to create **3 separate worker services** in Railway:

#### Worker Service 1
```bash
WORKER_ID=0
OPENAI_API_KEY=sk-proj-your-first-key
# ... other env vars
```

#### Worker Service 2
```bash
WORKER_ID=1
OPENAI_API_KEY=sk-proj-your-second-key
# ... other env vars
```

#### Worker Service 3
```bash
WORKER_ID=2
OPENAI_API_KEY=sk-proj-your-third-key
# ... other env vars
```

### Railway Service Configuration

Each worker service should have:
- **Build**: Use `backend/Dockerfile`
- **Start Command**: `PYTHONPATH=/app celery -A workers.celery_app worker --loglevel=info --concurrency=4`
- **Environment Variables**: As shown above
- **Replicas**: 1 per service (don't scale horizontally within a service)

## Testing the Setup

### 1. Verify API Keys

Check that different keys are loaded:

```bash
# In Railway logs for each worker
Worker 0: ✅ OpenAI provider initialized (Worker 0) with key: sk-proj-9...9MA
Worker 1: ✅ OpenAI provider initialized (Worker 1) with key: sk-proj-A...ABC
Worker 2: ✅ OpenAI provider initialized (Worker 2) with key: sk-proj-B...XYZ
```

### 2. Upload a Large Document

Upload a document with >500 Q&A pairs (typically >100 pages).

### 3. Monitor Chunking

Check backend logs:
```
Chunking enabled: 1500 pairs, 3 keys available
Optimal chunks: 3 (pages=300, keys=3)
Created chunk 0: pages 1-100, worker 0
Created chunk 1: pages 101-200, worker 1
Created chunk 2: pages 201-300, worker 2
```

### 4. Watch Parallel Processing

Each worker will process its chunk simultaneously:
```
Worker 0: Chunk 0: Processing pages 1-100
Worker 1: Chunk 1: Processing pages 101-200
Worker 2: Chunk 2: Processing pages 201-300
```

### 5. Verify Results

All chunks should complete and merge:
```
Chunk 0 complete: 500 items in 120s
Chunk 1 complete: 500 items in 118s
Chunk 2 complete: 500 items in 125s
Parent job completed: 1500 items processed
```

## Troubleshooting

### Chunking Not Triggering

Check:
- Document has >500 Q&A pairs
- `ENABLE_CHUNKING=true`
- Multiple API keys are configured
- Keys are valid (not expired/invalid)

### Workers Using Same Key

Check:
- Each worker has unique `WORKER_ID` (0, 1, 2)
- Each worker has its assigned `OPENAI_API_KEY_*` set
- Railway services are separate (not scaled replicas of one service)

### Chunks Failing

Check:
- All API keys are valid and have sufficient quota
- Rate limits not exceeded (each key should have its own bucket)
- Worker logs for specific error messages

### Slower Than Expected

Check:
- All workers are actually running (Railway dashboard)
- Each worker is using a different API key
- Cache hit rate (should be 80-90%)
- Network/API latency issues

## Performance Tuning

### Adjust Chunking Threshold

For smaller documents:
```bash
CHUNKING_THRESHOLD=300  # Trigger chunking at 300 Q&A pairs
```

### Adjust Max Chunks

For more than 3 keys:
```bash
MAX_CHUNKS=5
OPENAI_API_KEY_4=sk-proj-fourth-key
OPENAI_API_KEY_5=sk-proj-fifth-key
```

Update `config.py` to support more keys in the `assigned_openai_key` property.

### Disable Chunking

To disable chunking temporarily:
```bash
ENABLE_CHUNKING=false
```

## Cost Considerations

### Multiple API Keys

- Each key has separate billing
- Cost scales linearly with number of keys
- Ensure even distribution of usage

### Cache Benefits

- 80-90% cache hit rate reduces API costs
- Cache is shared across all workers
- Repeated content is only processed once

### Monitoring Costs

Check OpenAI dashboard for each API key:
- Track usage per key
- Monitor rate limit usage
- Set up billing alerts

## Migration Path

### Existing Users (1 API Key)

No changes required! System falls back to single-worker mode:
- Documents processed as before
- No chunking unless multiple keys configured
- Backward compatible

### Adding Second Key

1. Get second API key from OpenAI
2. Set `OPENAI_API_KEY_2` in environment
3. Create second worker service in Railway
4. System automatically uses chunking for large documents

### Adding Third Key

1. Get third API key from OpenAI
2. Set `OPENAI_API_KEY_3` in environment
3. Create third worker service in Railway
4. 3× speed for large documents

## Database Changes

### New Tables

- `chunk_jobs`: Tracks individual chunk processing
- Columns added to `processing_jobs`:
  - `is_chunked`: Whether job uses chunking
  - `num_chunks`: Number of chunks created

### Queries

Get chunk status:
```sql
SELECT chunk_index, status, progress, worker_id
FROM chunk_jobs
WHERE parent_job_id = 'job-uuid'
ORDER BY chunk_index;
```

## API Changes

### Job Start Endpoint

No changes to request format. Response includes chunking info in logs:
```json
{
  "job_id": "uuid",
  "status": "queued",
  "websocket_url": "/ws/jobs/uuid"
}
```

Backend logs will show:
```
Job uuid queued with 3 chunks for document filename.pdf
```

### Progress Updates

WebSocket updates remain the same. Progress is aggregated from all chunks.

## Summary

Multi-worker parallel processing provides significant speed improvements for large documents with minimal configuration. The system automatically detects when to use chunking and handles all coordination transparently.

**Key Benefits:**
- 3× faster with 3 API keys
- Automatic chunking decision
- No API changes required
- Backward compatible
- Easy Railway deployment

