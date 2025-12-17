#!/usr/bin/env python3
"""
Baseline Benchmark: Old Node.js System Only
Establishes performance baseline for comparison.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import psutil
import requests
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

OLD_SYSTEM_PORT = 3001
TEST_PDF = "Transcripts/Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf"
RESULTS_FILE = "baseline_results.json"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


async def monitor_resources(process_name: str, duration: float):
    """Monitor CPU and memory for a duration."""
    samples = []
    start = time.time()
    
    while time.time() - start < duration:
        try:
            total_cpu = 0
            total_memory = 0
            count = 0
            
            for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_info']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        total_cpu += proc.info['cpu_percent'] or 0
                        total_memory += proc.info['memory_info'].rss / (1024 * 1024)
                        count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if count > 0:
                samples.append({'cpu': total_cpu, 'memory': total_memory})
                
        except Exception as e:
            pass
            
        await asyncio.sleep(0.5)
    
    if not samples:
        return {"cpu_avg": 0, "cpu_max": 0, "memory_avg": 0, "memory_max": 0}
    
    cpu_values = [s['cpu'] for s in samples]
    mem_values = [s['memory'] for s in samples]
    
    return {
        "cpu_avg": sum(cpu_values) / len(cpu_values),
        "cpu_max": max(cpu_values),
        "memory_avg": sum(mem_values) / len(mem_values),
        "memory_max": max(mem_values)
    }


def check_port(port: int) -> bool:
    """Check if service is running."""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


async def start_old_system():
    """Start old Node.js system."""
    print(f"\n{Colors.BLUE}> Starting old Node.js system...{Colors.END}")
    
    if check_port(OLD_SYSTEM_PORT):
        print(f"{Colors.GREEN}> Old system already running!{Colors.END}")
        return None
    
    try:
        env = os.environ.copy()
        env['PORT'] = str(OLD_SYSTEM_PORT)
        
        process = subprocess.Popen(
            ['node', 'server.js'],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        
        # Wait for startup
        for i in range(60):
            await asyncio.sleep(0.5)
            if check_port(OLD_SYSTEM_PORT):
                print(f"{Colors.GREEN}> Old system started!{Colors.END}")
                return process
        
        print(f"{Colors.RED}> Failed to start (timeout){Colors.END}")
        return None
        
    except Exception as e:
        print(f"{Colors.RED}> Error: {e}{Colors.END}")
        return None


async def benchmark_old_system():
    """Benchmark the old system."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}Benchmarking Old System (Node.js){Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    try:
        print(f"{Colors.BLUE}> Uploading PDF...{Colors.END}")
        start_time = time.time()
        
        # Start monitoring
        monitor_task = asyncio.create_task(monitor_resources("node", 600))
        
        # Upload and process
        with open(TEST_PDF, 'rb') as f:
            files = {'file': (os.path.basename(TEST_PDF), f, 'application/pdf')}
            response = requests.post(
                f'http://localhost:{OLD_SYSTEM_PORT}/api/extract',
                files=files,
                timeout=600
            )
        
        elapsed = time.time() - start_time
        
        # Cancel monitoring
        monitor_task.cancel()
        try:
            resources = await monitor_task
        except asyncio.CancelledError:
            resources = {"cpu_avg": 0, "cpu_max": 0, "memory_avg": 0, "memory_max": 0}
        
        if response.status_code != 200:
            raise Exception(f"Upload failed: {response.status_code}")
        
        data = response.json()
        
        # Extract Q&A count
        qa_count = 0
        if data.get('success') and data.get('pages'):
            for page in data['pages']:
                if 'qaItems' in page:
                    qa_count += len(page['qaItems'])
                elif 'qa_pairs' in page:
                    qa_count += len(page['qa_pairs'])
        
        result = {
            "elapsed_time": elapsed,
            "elapsed_minutes": elapsed / 60,
            "qa_pairs_extracted": qa_count,
            "pages_extracted": len(data.get('pages', [])),
            "resources": resources
        }
        
        print(f"\n{Colors.GREEN}> COMPLETED!{Colors.END}")
        print(f"{Colors.BLUE}  Time: {elapsed:.2f}s ({elapsed/60:.2f} minutes){Colors.END}")
        print(f"{Colors.BLUE}  Q&A Pairs: {qa_count}{Colors.END}")
        print(f"{Colors.BLUE}  Pages: {len(data.get('pages', []))}{Colors.END}")
        print(f"{Colors.BLUE}  Peak Memory: {resources['memory_max']:.1f} MB{Colors.END}")
        print(f"{Colors.BLUE}  Peak CPU: {resources['cpu_max']:.1f}%{Colors.END}")
        
        return result
        
    except Exception as e:
        print(f"{Colors.RED}> Error: {e}{Colors.END}")
        return {"error": str(e)}


async def main():
    """Main entry point."""
    print(f"\n{Colors.BOLD}Old System Baseline Benchmark{Colors.END}")
    print(f"{Colors.BLUE}Test PDF: {TEST_PDF}{Colors.END}")
    
    if not os.path.exists(TEST_PDF):
        print(f"{Colors.RED}Error: Test PDF not found!{Colors.END}")
        return 1
    
    # Start system
    process = await start_old_system()
    
    # Wait for stability
    await asyncio.sleep(2)
    
    # Run benchmark
    result = await benchmark_old_system()
    
    if 'error' in result:
        return 1
    
    # Save results
    output = {
        "timestamp": datetime.now().isoformat(),
        "test_pdf": TEST_PDF,
        "system": "Node.js (Old)",
        "port": OLD_SYSTEM_PORT,
        "result": result
    }
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{Colors.GREEN}> Results saved to: {RESULTS_FILE}{Colors.END}")
    
    # Show summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}BASELINE ESTABLISHED{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"\nOld System Performance:")
    print(f"  Time: {result['elapsed_time']:.2f}s ({result['elapsed_minutes']:.2f} minutes)")
    print(f"  Q&A Pairs: {result['qa_pairs_extracted']}")
    print(f"  Throughput: {result['qa_pairs_extracted'] / result['elapsed_time']:.2f} items/sec")
    print(f"\nTo achieve 6.4x speedup, new system should complete in:")
    print(f"  Target: {result['elapsed_time'] / 6.4:.2f}s ({result['elapsed_minutes'] / 6.4:.2f} minutes)")
    print(f"\n{Colors.YELLOW}Next Steps:{Colors.END}")
    print(f"  1. Install Docker Desktop")
    print(f"  2. Run: docker-compose up -d")
    print(f"  3. Run full benchmark: python benchmark_systems.py")
    print()
    
    # Cleanup
    if process:
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                             capture_output=True)
            else:
                process.terminate()
        except:
            pass
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

