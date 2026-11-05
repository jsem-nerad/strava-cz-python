"""The examples are what a new user runs first, so they must not touch a real account unasked."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from .conftest import FakeCanteen

EXAMPLES = Path(__file__).parent.parent / "examples"


def load_example(name: str):
    spec = importlib.util.spec_from_file_location(f"example_{name}", EXAMPLES / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def example(api, login_route, menu_payload, monkeypatch, capsys):
    monkeypatch.setenv("STRAVA_USERNAME", "test.user")
    monkeypatch.setenv("STRAVA_PASSWORD", "test-password")
    monkeypatch.setenv("STRAVA_CANTEEN", "1234")
    monkeypatch.delenv("STRAVA_OPRAVDU_ZAPISOVAT", raising=False)
    return FakeCanteen(api, menu_payload)


def test_the_example_only_reads_by_default(example):
    load_example("example").main()
    assert not example.routes["pridejJidloS5"].called
    assert not example.routes["saveOrders"].called


def test_it_writes_only_when_told_to(example, monkeypatch, recwarn):
    monkeypatch.setenv("STRAVA_OPRAVDU_ZAPISOVAT", "1")
    load_example("example").main()
    assert example.routes["saveOrders"].called
