#!/usr/bin/env python3
"""
Comprehensive Benchmark Test: Old Node.js vs New FastAPI System
Validates predicted 6.4x speedup and 4.7x caching improvements.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import psutil
import requests
import websocket
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration
OLD_SYSTEM_PORT = 3001
NEW_SYSTEM_PORT = 8000
TEST_PDF = "Transcripts/Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf"
RESULTS_FILE = "benchmark_results.json"
REPORT_FILE = "benchmark_report.md"

# Expected performance targets
EXPECTED_SPEEDUP = 6.4
EXPECTED_CACHE_SPEEDUP = 4.7
TOLERANCE = 0.2  # 20% tolerance


class Colors:
    """ANSI colors for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


class SystemMonitor:
    """Monitor system resources during processing."""
    
    def __init__(self, process_name: str):
        self.process_name = process_name
        self.samples = []
        self.monitoring = False
        self.monitor_task = None
        
    async def start(self):
        """Start monitoring resources."""
        self.monitoring = True
        self.samples = []
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
    async def stop(self) -> Dict[str, float]:
        """Stop monitoring and return statistics."""
        self.monitoring = False
        if self.monitor_task:
            await self.monitor_task
            
        if not self.samples:
            return {"cpu_avg": 0, "cpu_max": 0, "memory_avg": 0, "memory_max": 0}
            
        cpu_values = [s['cpu'] for s in self.samples]
        mem_values = [s['memory'] for s in self.samples]
        
        return {
            "cpu_avg": sum(cpu_values) / len(cpu_values),
            "cpu_max": max(cpu_values),
            "memory_avg": sum(mem_values) / len(mem_values),
            "memory_max": max(mem_values)
        }
        
    async def _monitor_loop(self):
        """Internal monitoring loop."""
        while self.monitoring:
            try:
                # Find processes
                total_cpu = 0
                total_memory = 0
                count = 0
                
                for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
                    try:
                        if self.process_name.lower() in proc.info['name'].lower():
                            total_cpu += proc.info['cpu_percent'] or 0
                            total_memory += proc.info['memory_info'].rss / (1024 * 1024)  # MB
                            count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                if count > 0:
                    self.samples.append({
                        'cpu': total_cpu,
                        'memory': total_memory,
                        'timestamp': time.time()
                    })
                    
            except Exception as e:
                print(f"Warning: Monitoring error: {e}")
                
            await asyncio.sleep(0.5)


class BenchmarkRunner:
    """Main benchmark orchestrator."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "test_pdf": TEST_PDF,
            "old_system": {},
            "new_system": {},
            "comparison": {},
            "validation": {}
        }
        self.old_process = None
        self.docker_process = None
        
    def print_header(self, text: str):
        """Print formatted section header."""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text.center(70)}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}\n")
        
    def print_status(self, text: str, status: str = "info"):
        """Print colored status message."""
        color = {
            "info": Colors.BLUE,
            "success": Colors.GREEN,
            "warning": Colors.YELLOW,
            "error": Colors.RED
        }.get(status, "")
        # Use ASCII character for Windows compatibility
        print(f"{color}> {text}{Colors.END}")
        
    def check_port(self, port: int, timeout: float = 5.0) -> bool:
        """Check if a service is running on a port."""
        try:
            response = requests.get(f"http://localhost:{port}/health", timeout=timeout)
            return response.status_code == 200
        except:
            return False
            
    async def start_old_system(self) -> bool:
        """Start the old Node.js system on port 3001."""
        self.print_status("Starting old Node.js system...", "info")
        
        # Check if already running
        if self.check_port(OLD_SYSTEM_PORT, timeout=1):
            self.print_status("Old system already running!", "success")
            return True
            
        try:
            env = os.environ.copy()
            env['PORT'] = str(OLD_SYSTEM_PORT)
            
            # Start server.js
            self.old_process = subprocess.Popen(
                ['node', 'server.js'],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            # Wait for startup (up to 30 seconds)
            for i in range(60):
                await asyncio.sleep(0.5)
                if self.check_port(OLD_SYSTEM_PORT, timeout=1):
                    self.print_status("Old system started successfully!", "success")
                    return True
                    
            self.print_status("Old system failed to start (timeout)", "error")
            return False
            
        except Exception as e:
            self.print_status(f"Failed to start old system: {e}", "error")
            return False
            
    async def start_new_system(self) -> bool:
        """Start the new FastAPI system via Docker Compose."""
        self.print_status("Starting new FastAPI system...", "info")
        
        # Check if already running
        if self.check_port(NEW_SYSTEM_PORT, timeout=1):
            self.print_status("New system already running!", "success")
            return True
            
        try:
            # Start docker-compose
            subprocess.run(
                ['docker-compose', 'up', '-d'],
                check=True,
                capture_output=True
            )
            
            # Wait for services (up to 60 seconds)
            self.print_status("Waiting for services to initialize...", "info")
            for i in range(120):
                await asyncio.sleep(0.5)
                if self.check_port(NEW_SYSTEM_PORT, timeout=1):
                    # Extra time for DB/Redis initialization
                    await asyncio.sleep(5)
                    self.print_status("New system started successfully!", "success")
                    return True
                    
            self.print_status("New system failed to start (timeout)", "error")
            return False
            
        except Exception as e:
            self.print_status(f"Failed to start new system: {e}", "error")
            return False
            
    async def benchmark_old_system(self, run_number: int = 1) -> Dict[str, Any]:
        """Benchmark the old Node.js system."""
        self.print_header(f"Benchmarking Old System (Run #{run_number})")
        
        monitor = SystemMonitor("node")
        await monitor.start()
        
        try:
            # Upload and process PDF
            start_time = time.time()
            
            with open(TEST_PDF, 'rb') as f:
                files = {'file': (os.path.basename(TEST_PDF), f, 'application/pdf')}
                response = requests.post(
                    f'http://localhost:{OLD_SYSTEM_PORT}/api/extract',
                    files=files,
                    timeout=600
                )
                
            elapsed = time.time() - start_time
            
            if response.status_code != 200:
                raise Exception(f"Upload failed: {response.status_code}")
                
            data = response.json()
            
            # Extract Q&A pairs count
            qa_count = 0
            if data.get('success') and data.get('pages'):
                for page in data['pages']:
                    if 'qaItems' in page:
                        qa_count += len(page['qaItems'])
                    elif 'qa_pairs' in page:
                        qa_count += len(page['qa_pairs'])
            
            resource_stats = await monitor.stop()
            
            result = {
                "success": True,
                "elapsed_time": elapsed,
                "qa_pairs_extracted": qa_count,
                "pages_extracted": len(data.get('pages', [])),
                "resources": resource_stats
            }
            
            self.print_status(f"Completed in {elapsed:.2f}s", "success")
            self.print_status(f"  Q&A pairs: {qa_count}", "info")
            self.print_status(f"  Memory peak: {resource_stats['memory_max']:.1f} MB", "info")
            
            return result
            
        except Exception as e:
            await monitor.stop()
            self.print_status(f"Error: {e}", "error")
            return {"success": False, "error": str(e), "elapsed_time": 0}
            
    async def benchmark_new_system(self, run_number: int = 1) -> Dict[str, Any]:
        """Benchmark the new FastAPI system."""
        self.print_header(f"Benchmarking New System (Run #{run_number})")
        
        monitor = SystemMonitor("python")
        await monitor.start()
        
        try:
            start_time = time.time()
            
            # Step 1: Upload document
            with open(TEST_PDF, 'rb') as f:
                files = {'file': (os.path.basename(TEST_PDF), f, 'application/pdf')}
                upload_response = requests.post(
                    f'http://localhost:{NEW_SYSTEM_PORT}/api/documents/upload',
                    files=files,
                    timeout=60
                )
                
            if upload_response.status_code not in [200, 201]:
                raise Exception(f"Upload failed: {upload_response.status_code}")
                
            upload_data = upload_response.json()
            document_id = upload_data.get('document_id')
            
            # Step 2: Start processing job
            job_response = requests.post(
                f'http://localhost:{NEW_SYSTEM_PORT}/api/jobs/start',
                json={"document_id": document_id},
                timeout=30
            )
            
            if job_response.status_code != 201:
                raise Exception(f"Job creation failed: {job_response.status_code}")
                
            job_data = job_response.json()
            job_id = job_data.get('job_id')
            
            # Step 3: Monitor job progress via polling
            max_wait = 600  # 10 minutes
            poll_start = time.time()
            
            while time.time() - poll_start < max_wait:
                status_response = requests.get(
                    f'http://localhost:{NEW_SYSTEM_PORT}/api/jobs/{job_id}/status',
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    job_status = status_data.get('status')
                    progress = status_data.get('progress', 0)
                    
                    if job_status == 'completed':
                        break
                    elif job_status == 'failed':
                        raise Exception(f"Job failed: {status_data.get('error_message')}")
                        
                await asyncio.sleep(1)
                
            elapsed = time.time() - start_time
            
            # Step 4: Get results
            qa_response = requests.get(
                f'http://localhost:{NEW_SYSTEM_PORT}/api/documents/{document_id}/qa-items',
                timeout=30
            )
            
            qa_count = 0
            if qa_response.status_code == 200:
                qa_data = qa_response.json()
                qa_count = len(qa_data.get('qa_items', []))
            
            resource_stats = await monitor.stop()
            
            result = {
                "success": True,
                "elapsed_time": elapsed,
                "qa_pairs_extracted": qa_count,
                "document_id": document_id,
                "job_id": job_id,
                "cached": upload_data.get('cached', False),
                "resources": resource_stats
            }
            
            self.print_status(f"Completed in {elapsed:.2f}s", "success")
            self.print_status(f"  Q&A pairs: {qa_count}", "info")
            self.print_status(f"  Cached: {result['cached']}", "info")
            self.print_status(f"  Memory peak: {resource_stats['memory_max']:.1f} MB", "info")
            
            return result
            
        except Exception as e:
            await monitor.stop()
            self.print_status(f"Error: {e}", "error")
            return {"success": False, "error": str(e), "elapsed_time": 0}
            
    def validate_results(self):
        """Validate benchmark results against predictions."""
        self.print_header("Validating Results")
        
        validation = {
            "speedup_test": False,
            "cache_test": False,
            "accuracy_test": False,
            "memory_test": False,
            "overall": False
        }
        
        old_time_1 = self.results['old_system'].get('run1', {}).get('elapsed_time', 0)
        new_time_1 = self.results['new_system'].get('run1', {}).get('elapsed_time', 0)
        new_time_2 = self.results['new_system'].get('run2', {}).get('elapsed_time', 0)
        
        # Test 1: Initial speedup (6.4x expected)
        if old_time_1 > 0 and new_time_1 > 0:
            actual_speedup = old_time_1 / new_time_1
            expected_min = EXPECTED_SPEEDUP * (1 - TOLERANCE)
            
            validation['speedup_test'] = actual_speedup >= expected_min
            self.results['comparison']['speedup'] = actual_speedup
            
            status = "success" if validation['speedup_test'] else "warning"
            self.print_status(
                f"Speedup: {actual_speedup:.2f}x (expected {EXPECTED_SPEEDUP}x) - "
                f"{'PASS' if validation['speedup_test'] else 'MARGINAL'}",
                status
            )
        
        # Test 2: Cache improvement (4.7x expected)
        if new_time_1 > 0 and new_time_2 > 0:
            cache_speedup = new_time_1 / new_time_2
            expected_min = EXPECTED_CACHE_SPEEDUP * (1 - TOLERANCE)
            
            validation['cache_test'] = cache_speedup >= expected_min
            self.results['comparison']['cache_speedup'] = cache_speedup
            
            status = "success" if validation['cache_test'] else "warning"
            self.print_status(
                f"Cache speedup: {cache_speedup:.2f}x (expected {EXPECTED_CACHE_SPEEDUP}x) - "
                f"{'PASS' if validation['cache_test'] else 'MARGINAL'}",
                status
            )
        
        # Test 3: Accuracy (same Q&A count)
        old_qa = self.results['old_system'].get('run1', {}).get('qa_pairs_extracted', 0)
        new_qa = self.results['new_system'].get('run1', {}).get('qa_pairs_extracted', 0)
        
        if old_qa > 0 and new_qa > 0:
            qa_diff_pct = abs(old_qa - new_qa) / old_qa * 100
            validation['accuracy_test'] = qa_diff_pct < 10  # Within 10%
            
            status = "success" if validation['accuracy_test'] else "warning"
            self.print_status(
                f"Q&A extraction: Old={old_qa}, New={new_qa} (diff={qa_diff_pct:.1f}%) - "
                f"{'PASS' if validation['accuracy_test'] else 'CHECK'}",
                status
            )
        
        # Test 4: Memory efficiency
        old_mem = self.results['old_system'].get('run1', {}).get('resources', {}).get('memory_max', 0)
        new_mem = self.results['new_system'].get('run1', {}).get('resources', {}).get('memory_max', 0)
        
        if old_mem > 0 and new_mem > 0:
            validation['memory_test'] = True  # Just informational
            mem_ratio = new_mem / old_mem
            
            self.print_status(
                f"Memory usage: Old={old_mem:.1f}MB, New={new_mem:.1f}MB (ratio={mem_ratio:.2f}x)",
                "info"
            )
        
        # Overall validation
        validation['overall'] = (
            validation['speedup_test'] and
            validation['cache_test'] and
            validation['accuracy_test']
        )
        
        self.results['validation'] = validation
        
        print()
        if validation['overall']:
            self.print_status("ALL TESTS PASSED - Improvements verified!", "success")
        else:
            self.print_status("Some tests did not meet expectations", "warning")
            
    def generate_report(self):
        """Generate detailed markdown report."""
        self.print_status("Generating report...", "info")
        
        # Save JSON results
        with open(RESULTS_FILE, 'w') as f:
            json.dump(self.results, f, indent=2)
        self.print_status(f"Saved results to {RESULTS_FILE}", "success")
        
        # Generate markdown report
        report = self._build_markdown_report()
        with open(REPORT_FILE, 'w') as f:
            f.write(report)
        self.print_status(f"Saved report to {REPORT_FILE}", "success")
        
    def _build_markdown_report(self) -> str:
        """Build markdown report content."""
        old_1 = self.results['old_system'].get('run1', {})
        new_1 = self.results['new_system'].get('run1', {})
        new_2 = self.results['new_system'].get('run2', {})
        comp = self.results['comparison']
        val = self.results['validation']
        
        report = f"""# DepoDigest Performance Benchmark Report

**Generated:** {self.results['timestamp']}  
**Test PDF:** {self.results['test_pdf']}

## Executive Summary

{':white_check_mark:' if val.get('overall') else ':warning:'} **Overall Result:** {'ALL PREDICTIONS VERIFIED' if val.get('overall') else 'NEEDS REVIEW'}

### Key Findings

| Metric | Old System | New System | Actual Improvement | Expected | Status |
|--------|-----------|------------|-------------------|----------|---------|
| **Initial Processing** | {old_1.get('elapsed_time', 0):.2f}s | {new_1.get('elapsed_time', 0):.2f}s | **{comp.get('speedup', 0):.2f}x** | {EXPECTED_SPEEDUP}x | {'✅ PASS' if val.get('speedup_test') else '⚠️ MARGINAL'} |
| **Cached Processing** | N/A | {new_2.get('elapsed_time', 0):.2f}s | **{comp.get('cache_speedup', 0):.2f}x** | {EXPECTED_CACHE_SPEEDUP}x | {'✅ PASS' if val.get('cache_test') else '⚠️ MARGINAL'} |
| **Q&A Pairs** | {old_1.get('qa_pairs_extracted', 0)} | {new_1.get('qa_pairs_extracted', 0)} | {abs(new_1.get('qa_pairs_extracted', 0) - old_1.get('qa_pairs_extracted', 0))} diff | Same | {'✅ PASS' if val.get('accuracy_test') else '⚠️ CHECK'} |

## Detailed Results

### Old System (Node.js on port {OLD_SYSTEM_PORT})

**Run #1 (Initial):**
- Processing Time: {old_1.get('elapsed_time', 0):.2f}s ({old_1.get('elapsed_time', 0)/60:.2f} min)
- Q&A Pairs: {old_1.get('qa_pairs_extracted', 0)}
- Pages: {old_1.get('pages_extracted', 0)}
- Peak Memory: {old_1.get('resources', {}).get('memory_max', 0):.1f} MB
- Peak CPU: {old_1.get('resources', {}).get('cpu_max', 0):.1f}%

### New System (FastAPI on port {NEW_SYSTEM_PORT})

**Run #1 (Initial - Cold Start):**
- Processing Time: {new_1.get('elapsed_time', 0):.2f}s
- Q&A Pairs: {new_1.get('qa_pairs_extracted', 0)}
- Cached: {new_1.get('cached', False)}
- Peak Memory: {new_1.get('resources', {}).get('memory_max', 0):.1f} MB
- Peak CPU: {new_1.get('resources', {}).get('cpu_max', 0):.1f}%

**Run #2 (Cached - Warm Start):**
- Processing Time: {new_2.get('elapsed_time', 0):.2f}s
- Q&A Pairs: {new_2.get('qa_pairs_extracted', 0)}
- Cached: {new_2.get('cached', False)}
- Peak Memory: {new_2.get('resources', {}).get('memory_max', 0):.1f} MB
- Peak CPU: {new_2.get('resources', {}).get('cpu_max', 0):.1f}%

## Performance Visualization

### Time Comparison (seconds)

```
Old System (Initial):    {'█' * int(old_1.get('elapsed_time', 0) / 5)} {old_1.get('elapsed_time', 0):.1f}s
New System (Initial):    {'█' * int(new_1.get('elapsed_time', 0) / 5)} {new_1.get('elapsed_time', 0):.1f}s
New System (Cached):     {'█' * max(1, int(new_2.get('elapsed_time', 0) / 5))} {new_2.get('elapsed_time', 0):.1f}s
```

### Speedup Factors

- **Initial Processing:** {comp.get('speedup', 0):.2f}x faster (predicted: {EXPECTED_SPEEDUP}x)
- **With Caching:** {comp.get('cache_speedup', 0):.2f}x faster than uncached (predicted: {EXPECTED_CACHE_SPEEDUP}x)
- **Overall vs Old:** {old_1.get('elapsed_time', 1) / new_2.get('elapsed_time', 1):.2f}x faster with cache

## Validation Results

| Test | Status | Details |
|------|--------|---------|
| Initial Speedup | {'✅ PASS' if val.get('speedup_test') else '⚠️ FAIL'} | Expected ≥{EXPECTED_SPEEDUP * (1-TOLERANCE):.1f}x, Got {comp.get('speedup', 0):.2f}x |
| Cache Speedup | {'✅ PASS' if val.get('cache_test') else '⚠️ FAIL'} | Expected ≥{EXPECTED_CACHE_SPEEDUP * (1-TOLERANCE):.1f}x, Got {comp.get('cache_speedup', 0):.2f}x |
| Result Accuracy | {'✅ PASS' if val.get('accuracy_test') else '⚠️ FAIL'} | Q&A extraction consistency verified |
| Memory Usage | ℹ️ INFO | Monitored for comparison |

## Conclusion

"""
        
        if val.get('overall'):
            report += """✅ **SUCCESS:** The new FastAPI-based system successfully delivers the predicted performance improvements:

- Initial processing is significantly faster than the old system
- Caching provides substantial additional speedup on repeat uploads
- Q&A extraction accuracy is maintained
- The system is production-ready

The migration from Node.js to FastAPI with parallel processing, PyMuPDF, and Redis caching has been **validated and successful**.
"""
        else:
            report += """⚠️ **REVIEW NEEDED:** Some performance metrics did not fully meet predictions.

Possible reasons:
- Test PDF size/complexity differs from original estimates
- System resources (CPU/RAM) may be constrained
- Network or API latency affecting measurements
- Need for system optimization

**Recommendation:** Review detailed metrics above and run additional tests with different PDFs to establish actual performance characteristics.
"""
        
        report += f"""

---

*Benchmark completed at {self.results['timestamp']}*  
*Raw data: {RESULTS_FILE}*
"""
        
        return report
        
    async def run(self):
        """Run complete benchmark suite."""
        self.print_header("DepoDigest Performance Benchmark")
        
        # Check test PDF exists
        if not os.path.exists(TEST_PDF):
            self.print_status(f"Test PDF not found: {TEST_PDF}", "error")
            return False
            
        self.print_status(f"Test PDF: {TEST_PDF}", "info")
        self.print_status(f"File size: {os.path.getsize(TEST_PDF) / 1024 / 1024:.2f} MB", "info")
        
        # Step 1: Start systems
        old_started = await self.start_old_system()
        new_started = await self.start_new_system()
        
        if not old_started or not new_started:
            self.print_status("Failed to start required systems", "error")
            return False
            
        # Give systems time to stabilize
        await asyncio.sleep(5)
        
        # Step 2: Benchmark old system (1 run)
        old_result_1 = await self.benchmark_old_system(run_number=1)
        self.results['old_system']['run1'] = old_result_1
        
        if not old_result_1.get('success'):
            self.print_status("Old system benchmark failed", "error")
            return False
            
        await asyncio.sleep(3)
        
        # Step 3: Benchmark new system (2 runs for cache testing)
        new_result_1 = await self.benchmark_new_system(run_number=1)
        self.results['new_system']['run1'] = new_result_1
        
        if not new_result_1.get('success'):
            self.print_status("New system benchmark failed", "error")
            return False
            
        await asyncio.sleep(3)
        
        # Run 2: Test caching
        new_result_2 = await self.benchmark_new_system(run_number=2)
        self.results['new_system']['run2'] = new_result_2
        
        # Step 4: Validate and report
        self.validate_results()
        self.generate_report()
        
        self.print_header("Benchmark Complete!")
        self.print_status(f"View detailed report: {REPORT_FILE}", "info")
        
        return self.results['validation'].get('overall', False)
        
    def cleanup(self):
        """Cleanup started processes."""
        if self.old_process:
            try:
                self.print_status("Stopping old system...", "info")
                if sys.platform == 'win32':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.old_process.pid)],
                                 capture_output=True)
                else:
                    self.old_process.terminate()
                    self.old_process.wait(timeout=5)
            except:
                pass


async def main():
    """Main entry point."""
    runner = BenchmarkRunner()
    
    try:
        success = await runner.run()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        return 130
    except Exception as e:
        print(f"\n{Colors.RED}Benchmark failed: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        runner.cleanup()


if __name__ == "__main__":
    # Install required packages check
    try:
        import psutil
        import requests
        import websocket
    except ImportError as e:
        print(f"{Colors.RED}Missing required package: {e}{Colors.END}")
        print(f"\nInstall with: pip install -r requirements-benchmark.txt")
        sys.exit(1)
        
    sys.exit(asyncio.run(main()))

