"""Shared pytest fixtures for DrillDown Unified."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MODEL_PROVIDER", "mock")

from backend.app.dependencies import get_history_repository  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.core.factory import reset_service_factory  # noqa: E402


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_application_state() -> Generator[None, None, None]:
    reset_service_factory()
    get_history_repository().clear()
    yield
    reset_service_factory()
