#!/usr/bin/env python3
"""
Pre-flight check for benchmark_systems.py
Validates environment and dependencies without running the full benchmark.
"""

import os
import sys
import subprocess
from pathlib import Path


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def check_item(name: str, passed: bool, details: str = ""):
    """Print check result."""
    # Use ASCII characters for Windows compatibility
    status = f"{Colors.GREEN}[OK]{Colors.END}" if passed else f"{Colors.RED}[X]{Colors.END}"
    print(f"{status} {name}")
    if details:
        print(f"  {Colors.BLUE}{details}{Colors.END}")
    return passed


def main():
    print(f"\n{Colors.BOLD}DepoDigest Benchmark Pre-Flight Check{Colors.END}\n")
    
    all_checks = []
    
    # 1. Check Python version
    py_version = sys.version_info
    passed = py_version >= (3, 8)
    all_checks.append(check_item(
        "Python Version",
        passed,
        f"Found {py_version.major}.{py_version.minor}.{py_version.micro} (need 3.8+)"
    ))
    
    # 2. Check required Python packages
    packages = ['requests', 'psutil', 'websocket']
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            all_checks.append(check_item(f"Package: {package}", True))
        except ImportError:
            all_checks.append(check_item(
                f"Package: {package}",
                False,
                "Install with: pip install -r requirements-benchmark.txt"
            ))
    
    # 3. Check Node.js
    try:
        result = subprocess.run(['node', '--version'], 
                              capture_output=True, text=True, timeout=5)
        passed = result.returncode == 0
        all_checks.append(check_item(
            "Node.js",
            passed,
            f"Found {result.stdout.strip()}" if passed else "Not found"
        ))
    except:
        all_checks.append(check_item("Node.js", False, "Not found or not in PATH"))
    
    # 4. Check Docker
    try:
        result = subprocess.run(['docker', '--version'],
                              capture_output=True, text=True, timeout=5)
        passed = result.returncode == 0
        all_checks.append(check_item(
            "Docker",
            passed,
            f"Found {result.stdout.strip()}" if passed else "Not found"
        ))
    except:
        all_checks.append(check_item("Docker", False, "Not found or not in PATH"))
    
    # 5. Check Docker Compose
    try:
        result = subprocess.run(['docker-compose', '--version'],
                              capture_output=True, text=True, timeout=5)
        passed = result.returncode == 0
        all_checks.append(check_item(
            "Docker Compose",
            passed,
            f"Found {result.stdout.strip()}" if passed else "Not found"
        ))
    except:
        all_checks.append(check_item("Docker Compose", False, "Not found or not in PATH"))
    
    # 6. Check test PDF exists
    test_pdf = "Transcripts/Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf"
    exists = os.path.exists(test_pdf)
    all_checks.append(check_item(
        "Test PDF",
        exists,
        f"Found at {test_pdf}" if exists else f"Not found: {test_pdf}"
    ))
    
    # 7. Check server.js exists
    exists = os.path.exists("server.js")
    all_checks.append(check_item(
        "Old System (server.js)",
        exists,
        "Found" if exists else "Not found"
    ))
    
    # 8. Check docker-compose.yml exists
    exists = os.path.exists("docker-compose.yml")
    all_checks.append(check_item(
        "New System (docker-compose.yml)",
        exists,
        "Found" if exists else "Not found"
    ))
    
    # 9. Check backend/.env exists
    exists = os.path.exists("backend/.env")
    all_checks.append(check_item(
        "Backend Environment",
        exists,
        "backend/.env found" if exists else "backend/.env not found"
    ))
    
    # 10. Check OpenAI API key in backend/.env
    if os.path.exists("backend/.env"):
        with open("backend/.env", 'r') as f:
            content = f.read()
            has_key = 'OPENAI_API_KEY=sk-' in content
            all_checks.append(check_item(
                "OpenAI API Key",
                has_key,
                "Configured in backend/.env" if has_key else "Missing or invalid in backend/.env"
            ))
    else:
        all_checks.append(check_item("OpenAI API Key", False, "backend/.env not found"))
    
    # 11. Check if old system node_modules exist
    exists = os.path.exists("node_modules")
    all_checks.append(check_item(
        "Old System Dependencies",
        exists,
        "node_modules found" if exists else "Run 'npm install'"
    ))
    
    # 12. Check benchmark script exists
    exists = os.path.exists("benchmark_systems.py")
    all_checks.append(check_item(
        "Benchmark Script",
        exists,
        "benchmark_systems.py found" if exists else "benchmark_systems.py not found"
    ))
    
    # 13. Check requirements file exists
    exists = os.path.exists("requirements-benchmark.txt")
    all_checks.append(check_item(
        "Benchmark Requirements",
        exists,
        "requirements-benchmark.txt found" if exists else "requirements-benchmark.txt not found"
    ))
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    passed_count = sum(all_checks)
    total_count = len(all_checks)
    
    if passed_count == total_count:
        print(f"{Colors.GREEN}{Colors.BOLD}[SUCCESS] All checks passed! Ready to run benchmark.{Colors.END}")
        print(f"\n{Colors.BLUE}Run: python benchmark_systems.py{Colors.END}\n")
        return 0
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}[WARNING] {total_count - passed_count} check(s) failed.{Colors.END}")
        print(f"\n{Colors.BLUE}Fix the issues above before running the benchmark.{Colors.END}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())

