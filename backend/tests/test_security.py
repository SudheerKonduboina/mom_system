# tests/test_security.py

import os
import pytest
from fastapi.testclient import TestClient


class TestSecurity:
    @pytest.fixture
    def auth_client(self):
        os.environ["API_SECRET_KEY"] = "test-secret-key-123"
        os.environ["ALLOWED_ORIGINS"] = "http://localhost:3000"
        os.environ["RATE_LIMIT_PER_MIN"] = "5"

        # Reimport to pick up new env vars
        import importlib
        import app.config
        importlib.reload(app.config)
        import app.auth_middleware
        importlib.reload(app.auth_middleware)
        import app.main
        importlib.reload(app.main)

        client = TestClient(app.main.app)
        yield client

        os.environ.pop("API_SECRET_KEY", None)

    def test_health_is_public(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_file_validation(self):
        from app.auth_middleware import validate_upload
        errors = validate_upload("test.exe", 1000)
        assert len(errors) > 0

        errors = validate_upload("test.webm", 1000)
        assert len(errors) == 0

    def test_file_size_validation(self):
        from app.auth_middleware import validate_upload
        errors = validate_upload("test.webm", 200 * 1024 * 1024)  # 200MB
        assert any("large" in e.lower() for e in errors)

    def test_valid_extensions(self):
        from app.auth_middleware import validate_upload
        for ext in [".webm", ".wav", ".mp3", ".ogg"]:
            errors = validate_upload(f"test{ext}", 1000)
            assert len(errors) == 0, f"Extension {ext} should be valid"
