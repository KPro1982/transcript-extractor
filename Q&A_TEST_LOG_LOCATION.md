# Q/A Test Log File Locations

## Where to Find Q/A Test Log Files

### Backend Server (Railway/Local)

The Q/A test log files are created on the **backend server** during document upload in the `/tmp/` directory:

**File Path Pattern:**
```
/tmp/qa_test_{document_id_first_8_chars}.log
```

**Example:**
```
/tmp/qa_test_12345678.log
```

### Important Notes:

1. **File Location is Server-Side**
   - Log files are stored on the backend server (Railway container or local machine running backend)
   - They are NOT stored on your local machine unless you download them
   - On Railway, files are in the ephemeral `/tmp/` directory of the backend container

2. **File Lifecycle**
   - Files are created during document upload after Q/A extraction test runs
   - Files persist in `/tmp/` until the server restarts or manually cleaned
   - On Railway, files are lost when container restarts
   - Log files are kept for the duration of the container session

3. **How to Access Log Files**

   **Option A: Via Frontend UI (Recommended)**
   - Upload a PDF document
   - Go to Select Pages page
   - Click "View Q/A Test Log" button
   - Click "Download Log" button to save locally
   - File will be saved as: `qa_test_log_{document_id}.txt` in your Downloads folder

   **Option B: Via Backend Server Direct Access (Railway)**
   ```bash
   # SSH into Railway container (if available)
   railway shell --service backend
   
   # List log files
   ls -lh /tmp/qa_test_*.log
   
   # View a log file
   cat /tmp/qa_test_12345678.log
   
   # Copy log file content
   cat /tmp/qa_test_12345678.log | pbcopy  # macOS
   cat /tmp/qa_test_12345678.log | clip    # Windows
   ```

   **Option C: Via Backend Server Direct Access (Local)**
   ```bash
   # Windows
   dir C:\Users\{YourUsername}\AppData\Local\Temp\qa_test_*.log
   type C:\Users\{YourUsername}\AppData\Local\Temp\qa_test_12345678.log
   
   # Linux/macOS
   ls -lh /tmp/qa_test_*.log
   cat /tmp/qa_test_12345678.log
   ```

   **Option D: Via API (For Debugging)**
   ```bash
   # Get log file content via API
   curl "http://localhost:8000/api/documents/qa-test-log?log_file=/tmp/qa_test_12345678.log"
   
   # Or on Railway
   curl "https://backend-production-e4c7.up.railway.app/api/documents/qa-test-log?log_file=/tmp/qa_test_12345678.log"
   ```

4. **Finding the Log File Path**
   
   The log file path is stored in the database:
   ```sql
   SELECT qa_test_log_file FROM documents WHERE id = '{document_id}';
   ```
   
   Or check the browser console when viewing the Select Pages page:
   ```
   Q/A test log file found: /tmp/qa_test_12345678.log
   ```

5. **Downloading Logs for Analysis**

   **Via Frontend (Easiest):**
   1. Click "View Q/A Test Log" button
   2. Click "Download Log" button
   3. Log saved to your Downloads folder as `qa_test_log_{document_id}.txt`

   **Via Backend Logs:**
   - Check Railway logs for log file paths
   - Look for: "✓ Q/A test log file saved: /tmp/qa_test_..."
   - Use the API endpoint to retrieve content

6. **Troubleshooting "Log Not Found"**

   If the log doesn't show:
   - Check browser console for errors
   - Check if `qa_test_log_file` is set in document record
   - Verify backend has access to `/tmp/` directory
   - Check if file was cleaned up (server restart)
   - Check Railway backend logs for file creation confirmation

## Log File Content Structure

The log file contains 6 sections:

1. **Test Configuration** - Patterns used for detection
2. **Text Extraction Diagnostics** - Sample text from PDF pages
3. **Pattern Matching Analysis** - Which patterns matched and statistics
4. **Line-by-Line Analysis** - First 100 lines with classifications
5. **State Machine Tracking** - Extraction state transitions
6. **Results Summary** - Conclusions and recommendations

See `SAMPLE_QA_TEST_LOG.md` for an example of the log format.

## Backend Server Locations

### Railway Production
- **Backend URL**: https://backend-production-e4c7.up.railway.app
- **Log Directory**: `/tmp/` (ephemeral, resets on container restart)
- **Access**: Via API endpoint or Railway shell (if available)

### Local Development
- **Backend URL**: http://localhost:8000
- **Log Directory**: 
  - Windows: `C:\Users\{Username}\AppData\Local\Temp\`
  - Linux/macOS: `/tmp/`
- **Access**: Direct file system access

## Recommended Workflow

1. Upload PDF via frontend
2. Check browser console for log file path
3. Click "View Q/A Test Log" on Select Pages page
4. Review diagnostic information in modal
5. Click "Download Log" to save locally for analysis
6. Share log file if debugging extraction issues

