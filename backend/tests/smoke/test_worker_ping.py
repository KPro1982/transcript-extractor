import os

import pytest
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL")


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(not REDIS_URL, reason="REDIS_URL not set"),
]


def test_worker_ping():
    app = Celery("smoke", broker=REDIS_URL, backend=REDIS_URL)
    resp = app.control.ping(timeout=5)
    assert resp, "No worker responses"


