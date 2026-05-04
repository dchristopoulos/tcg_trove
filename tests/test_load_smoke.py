from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import engine
from app.main import app


def _hit_health(client: TestClient) -> int:
    response = client.get('/health/live')
    return response.status_code


def test_parallel_health_smoke() -> None:
    # Lightweight load smoke to catch obvious thread-safety or startup regressions.
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        with ThreadPoolExecutor(max_workers=12) as pool:
            statuses = list(pool.map(lambda _: _hit_health(client), range(40)))
    assert all(code == 200 for code in statuses)
