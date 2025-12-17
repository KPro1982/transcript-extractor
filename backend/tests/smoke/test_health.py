import os

import httpx
import pytest

BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")


def _skip_if_not_running(path: str):
    try:
        httpx.get(path, timeout=3)
    except httpx.RequestError:
        pytest.skip(f"Backend not reachable at {path}")


@pytest.mark.smoke
def test_health_ok():
    url = f"{BASE_URL}/health"
    _skip_if_not_running(url)
    resp = httpx.get(url, timeout=10)
    assert resp.status_code in (200, 503)


@pytest.mark.smoke
def test_health_detailed():
    url = f"{BASE_URL}/health/detailed"
    _skip_if_not_running(url)
    resp = httpx.get(url, timeout=10)
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert "services" in body


