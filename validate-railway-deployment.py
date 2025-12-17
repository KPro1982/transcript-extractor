#!/usr/bin/env python3
"""
Railway Deployment Validation Script
Tests all deployed services to ensure they're working correctly
"""

import sys
import asyncio
import httpx
import argparse
from typing import Dict, Any
from datetime import datetime


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.RESET}")
    print("=" * len(text))


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.RESET}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.RESET}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.RESET}")


async def check_backend_health(backend_url: str) -> Dict[str, Any]:
    """Check backend health endpoint"""
    print_header("Checking Backend Health")
    
    results = {
        "basic_health": False,
        "detailed_health": False,
        "database": False,
        "cache": False,
        "response_time": None
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Basic health check
        try:
            start_time = datetime.now()
            response = await client.get(f"{backend_url}/health")
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds() * 1000
            results["response_time"] = response_time
            
            if response.status_code == 200:
                data = response.json()
                print_success(f"Basic health check passed ({response_time:.0f}ms)")
                print_info(f"Service: {data.get('service')}, Version: {data.get('version')}")
                results["basic_health"] = True
            else:
                print_error(f"Basic health check failed: HTTP {response.status_code}")
        except Exception as e:
            print_error(f"Basic health check failed: {e}")
            return results
        
        # Detailed health check
        try:
            response = await client.get(f"{backend_url}/health/detailed")
            
            if response.status_code == 200:
                data = response.json()
                print_success("Detailed health check passed")
                
                services = data.get("services", {})
                
                # Check each service
                if services.get("database") == "healthy":
                    print_success("Database connection: OK")
                    results["database"] = True
                else:
                    print_error(f"Database connection: {services.get('database')}")
                
                if services.get("cache") == "healthy":
                    print_success("Redis cache connection: OK")
                    results["cache"] = True
                else:
                    print_error(f"Redis cache connection: {services.get('cache')}")
                
                results["detailed_health"] = True
            else:
                print_error(f"Detailed health check failed: HTTP {response.status_code}")
                print_info(f"Response: {response.text}")
        except Exception as e:
            print_error(f"Detailed health check failed: {e}")
    
    return results


async def check_frontend(frontend_url: str) -> bool:
    """Check if frontend is accessible"""
    print_header("Checking Frontend")
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        try:
            start_time = datetime.now()
            response = await client.get(frontend_url)
            end_time = datetime.now()
            
            response_time = (end_time - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                print_success(f"Frontend is accessible ({response_time:.0f}ms)")
                
                # Check if it's actually Next.js content
                if "<!DOCTYPE html>" in response.text or "<html" in response.text:
                    print_success("HTML content detected")
                    return True
                else:
                    print_warning("Received response but no HTML content found")
                    return False
            else:
                print_error(f"Frontend returned HTTP {response.status_code}")
                return False
        except Exception as e:
            print_error(f"Frontend check failed: {e}")
            return False


async def check_cors(backend_url: str, frontend_url: str) -> bool:
    """Check CORS configuration"""
    print_header("Checking CORS Configuration")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Simulate a preflight request
            response = await client.options(
                f"{backend_url}/health",
                headers={
                    "Origin": frontend_url,
                    "Access-Control-Request-Method": "GET"
                }
            )
            
            cors_headers = {
                "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
                "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
                "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers")
            }
            
            if cors_headers["Access-Control-Allow-Origin"]:
                print_success(f"CORS is configured")
                print_info(f"Allowed Origin: {cors_headers['Access-Control-Allow-Origin']}")
                return True
            else:
                print_warning("CORS headers not found in response")
                print_info("This might cause issues with frontend-backend communication")
                return False
        except Exception as e:
            print_error(f"CORS check failed: {e}")
            return False


async def check_websocket(backend_url: str) -> bool:
    """Check WebSocket endpoint"""
    print_header("Checking WebSocket Connection")
    
    # Convert HTTP to WS URL
    ws_url = backend_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_endpoint = f"{ws_url}/ws"
    
    try:
        # We can't easily test WebSocket without websockets library
        # Just verify the endpoint exists via HTTP
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{backend_url}/ws")
            # WebSocket endpoints typically return 426 when accessed via HTTP
            if response.status_code in [426, 400]:
                print_success("WebSocket endpoint exists")
                print_info(f"WebSocket URL: {ws_endpoint}")
                return True
            else:
                print_warning(f"WebSocket endpoint returned unexpected status: {response.status_code}")
                return False
    except Exception as e:
        print_error(f"WebSocket check failed: {e}")
        return False


async def check_api_endpoints(backend_url: str) -> Dict[str, bool]:
    """Check if main API endpoints are accessible"""
    print_header("Checking API Endpoints")
    
    results = {}
    endpoints = [
        "/api/documents",
        "/api/jobs"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for endpoint in endpoints:
            try:
                response = await client.get(f"{backend_url}{endpoint}")
                # Any response (even 401/403) means endpoint exists
                if response.status_code < 500:
                    print_success(f"{endpoint}: Accessible (HTTP {response.status_code})")
                    results[endpoint] = True
                else:
                    print_error(f"{endpoint}: Server error (HTTP {response.status_code})")
                    results[endpoint] = False
            except Exception as e:
                print_error(f"{endpoint}: {e}")
                results[endpoint] = False
    
    return results


def print_summary(all_results: Dict[str, Any]):
    """Print deployment validation summary"""
    print_header("Deployment Validation Summary")
    
    backend_health = all_results.get("backend_health", {})
    frontend_ok = all_results.get("frontend", False)
    cors_ok = all_results.get("cors", False)
    websocket_ok = all_results.get("websocket", False)
    api_endpoints = all_results.get("api_endpoints", {})
    
    total_checks = 0
    passed_checks = 0
    
    # Backend checks
    backend_checks = [
        ("Basic health", backend_health.get("basic_health")),
        ("Detailed health", backend_health.get("detailed_health")),
        ("Database connection", backend_health.get("database")),
        ("Cache connection", backend_health.get("cache"))
    ]
    
    for check_name, passed in backend_checks:
        total_checks += 1
        if passed:
            passed_checks += 1
            print_success(check_name)
        else:
            print_error(check_name)
    
    # Other checks
    other_checks = [
        ("Frontend accessible", frontend_ok),
        ("CORS configured", cors_ok),
        ("WebSocket endpoint", websocket_ok)
    ]
    
    for check_name, passed in other_checks:
        total_checks += 1
        if passed:
            passed_checks += 1
            print_success(check_name)
        else:
            print_error(check_name)
    
    # API endpoints
    for endpoint, passed in api_endpoints.items():
        total_checks += 1
        if passed:
            passed_checks += 1
    
    # Final score
    print()
    score_percentage = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    
    if score_percentage == 100:
        print_success(f"All checks passed! ({passed_checks}/{total_checks})")
        print_success("🎉 Your deployment is ready for production!")
    elif score_percentage >= 75:
        print_warning(f"Most checks passed ({passed_checks}/{total_checks} - {score_percentage:.0f}%)")
        print_info("Review the failed checks above and fix any issues")
    else:
        print_error(f"Many checks failed ({passed_checks}/{total_checks} - {score_percentage:.0f}%)")
        print_info("Your deployment needs attention. Review logs and configuration.")
    
    # Performance info
    if backend_health.get("response_time"):
        print()
        print_info(f"Backend response time: {backend_health['response_time']:.0f}ms")
        if backend_health["response_time"] < 1000:
            print_success("Response time is good")
        else:
            print_warning("Response time is high - consider scaling resources")
    
    return score_percentage == 100


async def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(
        description="Validate Railway deployment for DepoDigest"
    )
    parser.add_argument(
        "--backend",
        required=True,
        help="Backend URL (e.g., https://backend-production-xxxx.up.railway.app)"
    )
    parser.add_argument(
        "--frontend",
        required=True,
        help="Frontend URL (e.g., https://frontend-production-xxxx.up.railway.app)"
    )
    
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}🚂 Railway Deployment Validation{Colors.RESET}")
    print(f"{Colors.CYAN}==================================={Colors.RESET}\n")
    print_info(f"Backend URL:  {args.backend}")
    print_info(f"Frontend URL: {args.frontend}")
    
    all_results = {}
    
    # Run all checks
    all_results["backend_health"] = await check_backend_health(args.backend)
    all_results["frontend"] = await check_frontend(args.frontend)
    all_results["cors"] = await check_cors(args.backend, args.frontend)
    all_results["websocket"] = await check_websocket(args.backend)
    all_results["api_endpoints"] = await check_api_endpoints(args.backend)
    
    # Print summary
    success = print_summary(all_results)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

