"""Smoke tests for the aggregating gateway app."""

from __future__ import annotations

from pathlib import Path

import pytest

from quant_gateway.app import PORTAL_DIST


def test_gateway_mounts_modules_and_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("ASHARE_REPORTS_DIR", str(tmp_path))
    from quant_gateway.app import create_app

    client = testclient.TestClient(create_app())

    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["modules"] == ["/api/a-share"]
    assert body["portal"] == PORTAL_DIST.is_dir()

    # The mounted a-share router answers through the gateway prefix.
    reports = client.get("/api/a-share/reports")
    assert reports.status_code == 200
    assert reports.json() == {"runs": []}


def test_root_serves_portal_or_redirects_to_docs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    testclient = pytest.importorskip("fastapi.testclient")
    monkeypatch.setenv("ASHARE_REPORTS_DIR", str(tmp_path))
    from quant_gateway.app import create_app

    client = testclient.TestClient(create_app())
    response = client.get("/", follow_redirects=False)

    if PORTAL_DIST.is_dir():
        # Built frontend present: root serves the SPA, deep links included.
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        deep = client.get("/a-share/some-run-id")
        assert deep.status_code == 200
        assert "text/html" in deep.headers["content-type"]
    else:
        # No build output: keep the old docs redirect behaviour.
        assert response.status_code in (301, 302, 307)
