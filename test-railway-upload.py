"""
Test script to verify Railway deployment is working end-to-end.
Tests PDF upload, processing, and real-time updates.
"""
import requests
import websocket
import json
import time
import sys
import threading
from pathlib import Path

# Railway URLs
BACKEND_URL = "https://backend-production-e4c7.up.railway.app"
FRONTEND_URL = "https://frontend-production-e051f.up.railway.app"
WS_URL = "wss://backend-production-e4c7.up.railway.app"

# Test PDF
TEST_PDF = "Transcripts/Working transcript.pdf"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log(message, color=Colors.BLUE):
    print(f"{color}[TEST]{Colors.RESET} {message}")

def log_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.RESET}")

def log_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.RESET}")

def log_warning(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.RESET}")

def test_backend_health():
    """Test 1: Verify backend is responding"""
    log("Testing backend health...")
    try:
        response = requests.get(f"{BACKEND_URL}/api/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_success(f"Backend healthy: {data}")
            return True
        else:
            log_error(f"Backend returned status {response.status_code}")
            return False
    except Exception as e:
        log_error(f"Backend health check failed: {e}")
        return False

def test_frontend_reachable():
    """Test 2: Verify frontend is accessible"""
    log("Testing frontend accessibility...")
    try:
        response = requests.get(FRONTEND_URL, timeout=10)
        if response.status_code == 200:
            log_success("Frontend is accessible")
            return True
        else:
            log_error(f"Frontend returned status {response.status_code}")
            return False
    except Exception as e:
        log_error(f"Frontend check failed: {e}")
        return False

def upload_document():
    """Test 3: Upload a PDF document"""
    log(f"Uploading test PDF: {TEST_PDF}")
    
    if not Path(TEST_PDF).exists():
        log_error(f"Test PDF not found: {TEST_PDF}")
        return None
    
    try:
        with open(TEST_PDF, 'rb') as f:
            files = {'file': (Path(TEST_PDF).name, f, 'application/pdf')}
            response = requests.post(
                f"{BACKEND_URL}/api/documents/upload",
                files=files,
                timeout=30
            )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Upload successful!")
            log(f"  Document ID: {data.get('document_id')}")
            log(f"  Job ID: {data.get('job_id')}")
            log(f"  Status: {data.get('status')}")
            return data
        else:
            log_error(f"Upload failed with status {response.status_code}")
            log_error(f"Response: {response.text}")
            return None
    
    except Exception as e:
        log_error(f"Upload failed: {e}")
        return None

def monitor_websocket(job_id, duration=120):
    """Test 4: Monitor WebSocket for real-time updates"""
    log(f"Connecting to WebSocket for job: {job_id}")
    
    messages = []
    ws_url = f"{WS_URL}/api/ws/jobs/{job_id}"
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            messages.append(data)
            
            msg_type = data.get('type', 'unknown')
            
            if msg_type == 'connected':
                log_success(f"WebSocket connected: {data.get('message', '')}")
            
            elif msg_type == 'progress':
                progress_data = data.get('data', {})
                progress = progress_data.get('progress', 0)
                status = progress_data.get('status', 'unknown')
                message_text = progress_data.get('message', '')
                log(f"Progress: {progress}% - {status} - {message_text}")
            
            elif msg_type == 'error':
                error_data = data.get('data', {})
                error_msg = error_data.get('error_message', 'Unknown error')
                log_error(f"Processing error: {error_msg}")
            
            elif msg_type == 'complete':
                result_data = data.get('data', {})
                log_success(f"Processing complete!")
                log(f"  Total Q&A pairs: {result_data.get('total_qa_pairs', 0)}")
                log(f"  Pages processed: {result_data.get('pages_processed', 0)}")
                log(f"  Document ID: {result_data.get('document_id', '')}")
            
            elif msg_type == 'partial_result':
                result_data = data.get('data', {})
                saved = result_data.get('saved_count', 0)
                total = result_data.get('total', 0)
                log(f"Partial results: {saved}/{total} items saved")
            
            else:
                log_warning(f"Unknown message type: {msg_type}")
                log(f"  Data: {json.dumps(data, indent=2)}")
        
        except json.JSONDecodeError:
            log_warning(f"Non-JSON message: {message}")
        except Exception as e:
            log_error(f"Error processing message: {e}")
    
    def on_error(ws, error):
        log_error(f"WebSocket error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        log(f"WebSocket closed (status={close_status_code}, msg={close_msg})")
    
    def on_open(ws):
        log_success("WebSocket connection opened")
    
    try:
        ws = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Run WebSocket in a thread with timeout
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for duration or until processing completes
        start_time = time.time()
        while time.time() - start_time < duration:
            time.sleep(1)
            
            # Check if we received a complete or error message
            has_completion = any(
                msg.get('type') in ['complete', 'error'] 
                for msg in messages
            )
            if has_completion:
                log("Processing finished, waiting 5 more seconds for any final messages...")
                time.sleep(5)
                break
        
        ws.close()
        ws_thread.join(timeout=2)
        
        return messages
    
    except Exception as e:
        log_error(f"WebSocket monitoring failed: {e}")
        return messages

def verify_results(document_id):
    """Test 5: Verify results are in database"""
    log(f"Verifying results for document: {document_id}")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/documents/{document_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success("Document retrieved successfully!")
            log(f"  Filename: {data.get('filename')}")
            log(f"  Status: {data.get('status')}")
            
            # Get Q&A items
            qa_response = requests.get(
                f"{BACKEND_URL}/api/documents/{document_id}/qa",
                timeout=10
            )
            
            if qa_response.status_code == 200:
                qa_data = qa_response.json()
                qa_count = len(qa_data)
                log_success(f"Found {qa_count} Q&A pairs in database")
                
                # Show first few
                if qa_count > 0:
                    log("First Q&A pair:")
                    first = qa_data[0]
                    log(f"  Q: {first.get('question', '')[:100]}...")
                    log(f"  A: {first.get('answer', '')[:100]}...")
                    log(f"  Topic: {first.get('topic', 'N/A')}")
                
                return qa_count > 0
            else:
                log_error(f"Failed to get Q&A items: {qa_response.status_code}")
                return False
        else:
            log_error(f"Failed to get document: {response.status_code}")
            return False
    
    except Exception as e:
        log_error(f"Result verification failed: {e}")
        return False

def main():
    print("=" * 60)
    print(f"{Colors.BLUE}Railway Deployment End-to-End Test{Colors.RESET}")
    print("=" * 60)
    print()
    
    # Track test results
    results = {
        'backend_health': False,
        'frontend_reachable': False,
        'upload_success': False,
        'websocket_updates': False,
        'results_verified': False
    }
    
    # Test 1: Backend Health
    print(f"\n{Colors.YELLOW}Test 1: Backend Health{Colors.RESET}")
    results['backend_health'] = test_backend_health()
    if not results['backend_health']:
        log_error("Backend is not healthy, stopping tests")
        sys.exit(1)
    
    # Test 2: Frontend
    print(f"\n{Colors.YELLOW}Test 2: Frontend Accessibility{Colors.RESET}")
    results['frontend_reachable'] = test_frontend_reachable()
    
    # Test 3: Upload
    print(f"\n{Colors.YELLOW}Test 3: Document Upload{Colors.RESET}")
    upload_result = upload_document()
    if upload_result:
        results['upload_success'] = True
        job_id = upload_result.get('job_id')
        document_id = upload_result.get('document_id')
    else:
        log_error("Upload failed, stopping tests")
        sys.exit(1)
    
    # Test 4: WebSocket
    print(f"\n{Colors.YELLOW}Test 4: WebSocket Real-Time Updates{Colors.RESET}")
    log_warning("This will take 2-3 minutes to process the document...")
    messages = monitor_websocket(job_id, duration=180)
    
    if messages:
        results['websocket_updates'] = True
        log(f"Received {len(messages)} WebSocket messages")
        
        # Check for errors
        errors = [m for m in messages if m.get('type') == 'error']
        if errors:
            log_error("Processing errors detected:")
            for error in errors:
                log_error(f"  {error.get('data', {}).get('error_message', 'Unknown error')}")
        
        # Check for completion
        completions = [m for m in messages if m.get('type') == 'complete']
        if completions:
            log_success("Processing completed successfully!")
    else:
        log_warning("No WebSocket messages received")
    
    # Test 5: Verify Results
    print(f"\n{Colors.YELLOW}Test 5: Result Verification{Colors.RESET}")
    time.sleep(2)  # Wait a bit for DB to settle
    results['results_verified'] = verify_results(document_id)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"{Colors.BLUE}Test Summary{Colors.RESET}")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = f"{Colors.GREEN}✅ PASS{Colors.RESET}" if passed else f"{Colors.RED}❌ FAIL{Colors.RESET}"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "=" * 60)
    if all_passed:
        log_success("🎉 ALL TESTS PASSED! Railway deployment is working correctly!")
    else:
        log_error("⚠️  SOME TESTS FAILED. See details above.")
    print("=" * 60)
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.RESET}")
        sys.exit(1)

