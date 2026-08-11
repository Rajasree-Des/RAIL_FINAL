"""Tests for Top-N process-only manual generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.features.reports.topn_manual import has_valid_topn_dataset, resolve_valid_topn_dataset


@pytest.fixture
def train_csv(tmp_path: Path) -> Path:
    fixtures = (
        Path(__file__).resolve().parent.parent.parent / "fixtures" / "report3" / "trainwise_raw.csv"
    )
    target = tmp_path / "train-no.csv"
    target.write_text(fixtures.read_text(encoding="utf-8"), encoding="utf-8")
    return target


@pytest.mark.asyncio
async def test_valid_dataset_without_date_in_path(train_csv: Path, monkeypatch):
    async def _resolve(_slug: str) -> Path | None:
        return train_csv

    monkeypatch.setattr(
        "app.features.reports.topn_manual.resolve_topn_dataset",
        _resolve,
    )
    path = await resolve_valid_topn_dataset("train-no")
    assert path == train_csv
    assert await has_valid_topn_dataset("train-no") is True


@pytest.mark.asyncio
async def test_missing_dataset_returns_none(monkeypatch):
    async def _resolve(_slug: str) -> Path | None:
        return None

    monkeypatch.setattr(
        "app.features.reports.topn_manual.resolve_topn_dataset",
        _resolve,
    )
    assert await resolve_valid_topn_dataset("train-no") is None
    assert await has_valid_topn_dataset("train-no") is False


@pytest.mark.asyncio
async def test_incomplete_headers_rejected(tmp_path: Path, monkeypatch):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("Train No.,Received\n1,10\n", encoding="utf-8")

    async def _resolve(_slug: str) -> Path | None:
        return bad_csv

    monkeypatch.setattr(
        "app.features.reports.topn_manual.resolve_topn_dataset",
        _resolve,
    )
    assert await resolve_valid_topn_dataset("train-no") is None
