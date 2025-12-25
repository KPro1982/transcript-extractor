# Agent Context Summary - Chunk Processing Error Reporting

## Session Overview
This session focused on improving error reporting for chunk processing failures in the DepoDigest multi-worker system.

## Problem Identified
- Users were seeing generic error message: "Processing failed in one or more chunks"
- No visibility into which specific chunks failed, which workers, or what the actual errors were
- Made debugging chunk processing failures difficult

## Changes Implemented

### 1. Backend Error Reporting (`backend/workers/chunk_coordinator.py`)
- Enhanced `check_and_complete_parent()` function to collect detailed chunk failure information
- Now queries `chunk_jobs` table for failed chunks with:
  - `chunk_index`
  - `worker_id`
  - `first_page` and `last_page`
  - `error_message`
- Builds detailed error messages and sends structured data via WebSocket
- Includes both human-readable error details and structured `failed_chunks` array

**Key Code Location:** Lines 270-330 in `chunk_coordinator.py`

### 2. Frontend WebSocket Hook (`frontend/hooks/useWebSocket.ts`)
- Added `FailedChunk` interface with chunk failure details
- Extended `JobProgress` interface to include:
  - `failedChunks?: FailedChunk[]`
  - `errorDetails?: string`
- Updated error handling to capture and store detailed chunk failure information

**Key Code Location:** Lines 1-50 in `useWebSocket.ts`

### 3. Frontend UI (`frontend/app/process/[jobId]/page.tsx`)
- Enhanced error display to show detailed chunk failure information
- Displays:
  - Which chunks failed (chunk index, worker ID)
  - Page ranges for failed chunks
  - Specific error messages for each failed chunk
- Improved visual formatting with structured error display

**Key Code Location:** Error display section around lines 100-150

## Diagnostic Tool Created

### `diagnose_chunks.py`
- Comprehensive diagnostic script for chunk processing failures
- Features:
  - Lists recent processing jobs (last 24 hours)
  - Shows failed chunks with detailed error messages
  - Identifies stuck chunks (processing >30 minutes)
  - Shows worker distribution and health
  - Provides detailed chunk status for recent jobs
- Usage: `python diagnose_chunks.py`

### `DIAGNOSTIC-SCRIPT-README.md`
- Documentation for the diagnostic script
- Includes usage instructions and feature descriptions

## Git Commits Made

1. **Commit:** `1000697` - "Improve chunk processing error reporting with detailed failure information"
   - Modified: `backend/workers/chunk_coordinator.py`
   - Modified: `frontend/hooks/useWebSocket.ts`
   - Modified: `frontend/app/process/[jobId]/page.tsx`

2. **Commit:** `a6f6adc` - "Add diagnostic script for chunk processing failures"
   - Added: `diagnose_chunks.py`
   - Added: `DIAGNOSTIC-SCRIPT-README.md`

Both commits pushed to `dev` branch (Railway auto-deploys from `dev`)

## Current State

### Working Features
- ✅ Enhanced error reporting sends detailed chunk failure info via WebSocket
- ✅ Frontend displays structured error information with chunk details
- ✅ Diagnostic script available for troubleshooting
- ✅ All changes committed and pushed to `dev` branch

### Known Issues / Next Steps
- User reported seeing "Processing failed in one or more chunks" error (0% progress)
- Redis logs show normal background saves (not related to issue)
- Diagnostic script can be used to investigate specific failures
- May need to check Railway worker logs for actual error causes

## Key Files Modified

1. `backend/workers/chunk_coordinator.py` - Enhanced error reporting
2. `frontend/hooks/useWebSocket.ts` - Added chunk failure data structures
3. `frontend/app/process/[jobId]/page.tsx` - Improved error UI display
4. `diagnose_chunks.py` - New diagnostic tool
5. `DIAGNOSTIC-SCRIPT-README.md` - Documentation

## Project Context

- **Project:** DepoDigest - AI-powered deposition transcript summarization
- **Architecture:** FastAPI backend + Next.js frontend + Celery workers
- **Multi-Worker System:** 3 workers (worker-0, worker-1, worker-2) with separate API keys
- **Chunking:** Documents >500 Q&A pairs automatically split across workers
- **Deployment:** Railway (auto-deploys from `dev` branch)
- **Database:** Two PostgreSQL databases (ephemeral + persistent)

## Cursor Rules
- Always commit and push to `dev` branch after refactoring/fixes
- Railway monitors `dev` branch for auto-deployment
- Use `master` branch for production releases

## Next Agent Instructions
- Review the enhanced error reporting implementation
- Use `diagnose_chunks.py` to investigate any chunk processing failures
- Check Railway logs if users report chunk failures
- Consider adding retry logic for failed chunks if needed


