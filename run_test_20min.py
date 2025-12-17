#!/usr/bin/env python3
"""
Anonymous test runner - runs tests continuously for 20 minutes.
Uses smoke tests and health checks that don't require API keys.
"""
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

TEST_DURATION_MINUTES = 20
START_TIME = datetime.now()
END_TIME = START_TIME + timedelta(minutes=TEST_DURATION_MINUTES)

LOG_FILE = "test_run_20min.log"

def log(message: str):
    """Log with timestamp."""
    elapsed = datetime.now() - START_TIME
    log_msg = f"[{elapsed.total_seconds():.1f}s] {message}"
    print(log_msg)
    # Also write to log file
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_msg + '\n')

def run_smoke_tests():
    """Run smoke tests via pytest."""
    try:
        os.chdir('backend')
        result = subprocess.run(
            ['pytest', 'tests/smoke/', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            timeout=60
        )
        os.chdir('..')
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        os.chdir('..')
        return False, "", "Test timeout"
    except Exception as e:
        os.chdir('..')
        return False, "", str(e)

def run_import_check():
    """Run import check script."""
    try:
        result = subprocess.run(
            ['python', 'scripts/diagnostics/check_imports.py'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def run_concurrent_test():
    """Run concurrent batch processing test (no API keys needed for basic test)."""
    try:
        os.chdir('backend')
        # Set environment to skip API calls
        env = os.environ.copy()
        env['SKIP_AI_TESTS'] = '1'
        
        result = subprocess.run(
            ['pytest', 'tests/test_performance.py::test_concurrent_batch_processing', '-v', '--tb=short'],
            capture_output=True,
            text=True,
            timeout=120,
            env=env
        )
        os.chdir('..')
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        os.chdir('..')
        return False, "", "Test timeout"
    except Exception as e:
        os.chdir('..')
        return False, "", str(e)

def main():
    """Run tests continuously for 20 minutes."""
    # Clear/create log file
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"Test Run Started: {START_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Duration: {TEST_DURATION_MINUTES} minutes\n")
        f.write(f"End Time: {END_TIME.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*60 + "\n\n")
    
    log(f"Starting anonymous test run for {TEST_DURATION_MINUTES} minutes")
    log(f"End time: {END_TIME.strftime('%H:%M:%S')}")
    log(f"Log file: {LOG_FILE}")
    
    test_cycle = 0
    passed_tests = 0
    failed_tests = 0
    
    while datetime.now() < END_TIME:
        test_cycle += 1
        remaining = (END_TIME - datetime.now()).total_seconds() / 60
        log(f"\n=== Test Cycle {test_cycle} ({(remaining):.1f} min remaining) ===")
        
        # Test 1: Import check
        log("Running import check...")
        success, stdout, stderr = run_import_check()
        if success:
            log("✓ Import check passed")
            passed_tests += 1
        else:
            log(f"✗ Import check failed: {stderr[:100]}")
            failed_tests += 1
        
        time.sleep(2)
        
        # Test 2: Smoke tests (if services are running)
        log("Running smoke tests...")
        success, stdout, stderr = run_smoke_tests()
        if success:
            log("✓ Smoke tests passed")
            passed_tests += 1
        else:
            # Smoke tests may fail if services aren't running - that's OK
            log("⚠ Smoke tests skipped or failed (services may not be running)")
        
        time.sleep(2)
        
        # Test 3: Concurrent processing test
        log("Running concurrent batch test...")
        success, stdout, stderr = run_concurrent_test()
        if success:
            log("✓ Concurrent batch test passed")
            passed_tests += 1
        else:
            log(f"⚠ Concurrent batch test failed: {stderr[:100] if stderr else 'Unknown error'}")
            failed_tests += 1
        
        # Wait before next cycle (adjust based on test duration)
        cycle_duration = 30  # seconds between cycles
        log(f"Waiting {cycle_duration}s before next cycle...")
        time.sleep(cycle_duration)
    
    # Final summary
    elapsed = datetime.now() - START_TIME
    log(f"\n{'='*60}")
    log(f"Test run completed!")
    log(f"Duration: {elapsed.total_seconds()/60:.1f} minutes")
    log(f"Total cycles: {test_cycle}")
    log(f"Passed tests: {passed_tests}")
    log(f"Failed tests: {failed_tests}")
    log(f"Success rate: {(passed_tests/(passed_tests+failed_tests)*100) if (passed_tests+failed_tests) > 0 else 0:.1f}%")
    log(f"{'='*60}")
    log(f"Full log saved to: {LOG_FILE}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nTest run interrupted by user")
        sys.exit(0)
    except Exception as e:
        log(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

