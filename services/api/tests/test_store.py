"""Tests for run persistence.

Two things matter here. A finished package must survive a page refresh, because
losing it after a two minute run is indefensible. And a run id arrives from the
URL, so it must never be able to reach outside the store directory.
"""

from __future__ import annotations

import json

import pytest

from app.core.store import RunStore, summarise


@pytest.fixture
def store(tmp_path) -> RunStore:
    return RunStore(directory=str(tmp_path / "runs"))


def test_save_then_get_round_trips(store: RunStore, package: dict) -> None:
    run_id = store.save(package, searches=7, setting="Chicago, Illinois")
    document = store.get(run_id)

    assert document is not None
    assert document["run_id"] == package["run_id"]
    assert document["searches"] == 7
    assert document["setting"] == "Chicago, Illinois"
    assert document["recorded"] is False
    assert document["package"]["script"]["header"]["title"] == "The Projectionist"


def test_saved_document_records_a_timestamp(store: RunStore, package: dict) -> None:
    run_id = store.save(package, searches=0, setting="x")
    saved_at = store.get(run_id)["saved_at"]

    assert saved_at.startswith("20")
    assert "T" in saved_at


def test_get_returns_none_for_a_missing_run(store: RunStore) -> None:
    assert store.get("abcdef123456") is None


def test_delete_removes_a_run(store: RunStore, package: dict) -> None:
    run_id = store.save(package, searches=0, setting="x")

    assert store.delete(run_id) is True
    assert store.get(run_id) is None
    assert store.delete(run_id) is False


def test_list_is_newest_first(store: RunStore, package: dict) -> None:
    for i in range(3):
        store.save({**package, "run_id": f"run{i}0000000"}, searches=i, setting="x")

    listed = store.list()

    assert len(listed) == 3
    assert {s.run_id for s in listed} == {"run00000000", "run10000000", "run20000000"}


def test_list_respects_the_limit(store: RunStore, package: dict) -> None:
    for i in range(5):
        store.save({**package, "run_id": f"run{i}0000000"}, searches=0, setting="x")

    assert len(store.list(limit=2)) == 2


def test_list_skips_unreadable_files(store: RunStore, package: dict) -> None:
    """One corrupt file must not take down the whole history."""
    store.save(package, searches=0, setting="x")
    (store.dir / "garbage.json").write_text("{not json", encoding="utf-8")

    assert len(store.list()) == 1


def test_list_is_empty_on_a_fresh_store(store: RunStore) -> None:
    assert store.list() == []


@pytest.mark.parametrize(
    "bad_id",
    [
        "../secrets",
        "..",
        "a/b",
        "a\\b",
        "run id",
        "",
        "x",
        "RUNID",
        "run-0001",
        "a" * 64,
    ],
)
def test_unsafe_run_ids_are_refused(store: RunStore, bad_id: str) -> None:
    """The id comes from a URL, so it is treated as hostile."""
    with pytest.raises(ValueError):
        store.get(bad_id)
    with pytest.raises(ValueError):
        store.delete(bad_id)


def test_path_traversal_cannot_escape_the_store_directory(store: RunStore, tmp_path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"run_id": "leak"}), encoding="utf-8")

    with pytest.raises(ValueError):
        store.get("../outside")

    assert outside.exists(), "the file outside the store should be untouched"


def test_summarise_extracts_list_row_fields(package: dict) -> None:
    document = {
        "run_id": "testrun0001",
        "saved_at": "2026-01-01T00:00:00+00:00",
        "searches": 12,
        "recorded": True,
        "package": package,
    }
    summary = summarise(document)

    assert summary is not None
    assert summary.title == "The Projectionist"
    assert summary.scene_count == 3
    assert summary.shoot_days == 2
    assert summary.red_flags == 1
    assert summary.searches == 12
    assert summary.recorded is True


def test_summarise_falls_back_to_the_id_inside_the_package(package: dict) -> None:
    """A document missing the outer id is still recoverable from the package."""
    summary = summarise({"package": package})

    assert summary is not None
    assert summary.run_id == "testrun0001"


def test_summarise_rejects_a_document_with_no_id_anywhere(package: dict) -> None:
    assert summarise({"package": {**package, "run_id": None}}) is None
    assert summarise({}) is None


def test_summarise_tolerates_a_partial_package() -> None:
    """A run that failed halfway should still list rather than vanish."""
    summary = summarise({"run_id": "halfrun0001", "package": {}})

    assert summary is not None
    assert summary.title == "Untitled"
    assert summary.shoot_days == 0
    assert summary.red_flags == 0


def test_summary_serialises_to_json_safe_types(package: dict) -> None:
    store_row = summarise({"run_id": "testrun0001", "package": package}).as_dict()

    json.dumps(store_row)
    assert set(store_row) == {
        "run_id",
        "title",
        "saved_at",
        "scene_count",
        "page_count",
        "shoot_days",
        "red_flags",
        "searches",
        "recorded",
    }
