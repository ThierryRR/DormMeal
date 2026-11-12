"""Smoke test of the Streamlit UI with Streamlit's AppTest (no browser)."""
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_plans_a_week(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = st_testing.AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    at.button[0].click().run()          # "Plan my week" with the default form
    assert not at.exception
    assert any("Total cost" in m.label for m in at.metric)
