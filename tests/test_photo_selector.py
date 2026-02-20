"""
Tests for photo_selector.py

osxphotos is mocked throughout — these tests run without macOS Photos access.
"""
import os
import pathlib
import pickle
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import photo_selector
from photo_selector import (
    CACHE_VERSION,
    MAX_PHOTO_SIZE_BYTES,
    PhotoRecord,
    _db_mtime,
    _load_cache,
    get_photos,
    list_persons,
    select_on_this_day,
    select_photo,
)

from tests.conftest import FIXED_TODAY


# ---------------------------------------------------------------------------
# _db_mtime
# ---------------------------------------------------------------------------


def test__db_mtime__returns_mtime(tmp_path):
    db_dir = tmp_path / "database"
    db_dir.mkdir()
    sqlite_file = db_dir / "Photos.sqlite"
    sqlite_file.write_bytes(b"")
    result = _db_mtime(str(tmp_path))
    assert result == sqlite_file.stat().st_mtime


def test__db_mtime__returns_none_when_missing(tmp_path):
    result = _db_mtime(str(tmp_path / "nonexistent"))
    assert result is None


# ---------------------------------------------------------------------------
# _load_cache
# ---------------------------------------------------------------------------


def test__load_cache__returns_none_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(photo_selector, "CACHE_FILE", tmp_path / "missing.pkl")
    assert _load_cache() is None


def test__load_cache__returns_none_on_version_mismatch(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.pkl"
    stale = {
        "version": CACHE_VERSION - 1,
        "library_path": "/fake",
        "db_mtime": 100.0,
        "photos": [],
    }
    cache_path.write_bytes(pickle.dumps(stale))
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    assert _load_cache() is None


def test__load_cache__returns_none_when_stale(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.pkl"
    data = {
        "version": CACHE_VERSION,
        "library_path": "/fake/Photos Library.photoslibrary",
        "db_mtime": 100.0,
        "photos": [],
    }
    cache_path.write_bytes(pickle.dumps(data))
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    # Simulate Photos.sqlite being updated since cache was built
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 200.0)
    assert _load_cache() is None


def test__load_cache__returns_cache_when_fresh(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.pkl"
    data = {
        "version": CACHE_VERSION,
        "library_path": "/fake/Photos Library.photoslibrary",
        "db_mtime": 100.0,
        "photos": [],
    }
    cache_path.write_bytes(pickle.dumps(data))
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 100.0)
    result = _load_cache()
    assert result is not None
    assert result["photos"] == []


# ---------------------------------------------------------------------------
# _build_and_save_cache
# ---------------------------------------------------------------------------


def test__build_and_save_cache__builds_correctly(monkeypatch, tmp_path, mock_db):
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 12345.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 5_000_000)

    cache = photo_selector._build_and_save_cache(mock_db)

    assert len(cache["photos"]) == 1
    rec = cache["photos"][0]
    assert rec.date == "2019-03-15"
    assert rec.location == "Paris"
    assert rec.persons == ["Alice Smith"]
    assert rec.size_bytes == 5_000_000
    assert cache_path.exists()


def test__build_and_save_cache__skips_missing_path(monkeypatch, tmp_path, mock_db):
    """Photos with path=None must be skipped."""
    mock_db.photos.return_value[0].path = None
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 1_000_000)

    cache = photo_selector._build_and_save_cache(mock_db)
    assert cache["photos"] == []


def test__build_and_save_cache__skips_screenshot(monkeypatch, tmp_path, mock_db):
    mock_db.photos.return_value[0].screenshot = True
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 1_000_000)

    cache = photo_selector._build_and_save_cache(mock_db)
    assert cache["photos"] == []


def test__build_and_save_cache__handles_missing_place(monkeypatch, tmp_path, mock_db):
    mock_db.photos.return_value[0].place = None
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 1_000_000)

    cache = photo_selector._build_and_save_cache(mock_db)
    assert cache["photos"][0].location is None


def test__build_and_save_cache__handles_getsize_oserror(monkeypatch, tmp_path, mock_db):
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: (_ for _ in ()).throw(OSError("no access")))

    cache = photo_selector._build_and_save_cache(mock_db)
    assert cache["photos"][0].size_bytes is None


# ---------------------------------------------------------------------------
# get_photos
# ---------------------------------------------------------------------------


def test_get_photos__uses_cache_when_fresh(monkeypatch, photo_a):
    monkeypatch.setattr(photo_selector, "_load_cache", lambda: {"photos": [photo_a]})
    result = get_photos()
    assert result == [photo_a]


def test_get_photos__builds_cache_on_miss(monkeypatch, mock_db, tmp_path):
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_load_cache", lambda: None)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 1_000_000)

    mock_photosdb_cls = MagicMock(return_value=mock_db)
    monkeypatch.setattr(photo_selector.osxphotos, "PhotosDB", mock_photosdb_cls)

    result = get_photos()
    mock_photosdb_cls.assert_called_once()
    assert len(result) == 1


def test_get_photos__force_refresh_bypasses_cache(monkeypatch, mock_db, tmp_path):
    cache_path = tmp_path / "cache.pkl"
    monkeypatch.setattr(photo_selector, "CACHE_FILE", cache_path)
    monkeypatch.setattr(photo_selector, "_db_mtime", lambda p: 0.0)
    monkeypatch.setattr("os.path.getsize", lambda p: 1_000_000)

    load_cache_mock = MagicMock(return_value={"photos": []})
    monkeypatch.setattr(photo_selector, "_load_cache", load_cache_mock)

    mock_photosdb_cls = MagicMock(return_value=mock_db)
    monkeypatch.setattr(photo_selector.osxphotos, "PhotosDB", mock_photosdb_cls)

    get_photos(force_refresh=True)
    load_cache_mock.assert_not_called()
    mock_photosdb_cls.assert_called_once()


def test_get_photos__exits_when_db_cannot_open(monkeypatch):
    monkeypatch.setattr(photo_selector, "_load_cache", lambda: None)
    monkeypatch.setattr(
        photo_selector.osxphotos,
        "PhotosDB",
        MagicMock(side_effect=Exception("no access")),
    )
    with pytest.raises(SystemExit) as exc_info:
        get_photos()
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# select_photo
# ---------------------------------------------------------------------------


def test_select_photo__returns_photo_from_full_library(photo_a, photo_b):
    result = select_photo([photo_a, photo_b])
    assert result in (photo_a, photo_b)


def test_select_photo__filters_by_person_case_insensitive(photo_a, photo_b):
    # photo_a has ["Alice Smith", "Bob Jones"], photo_b has []
    result = select_photo([photo_a, photo_b], person="alice smith")
    assert result is photo_a


def test_select_photo__returns_none_for_unknown_person(photo_a):
    result = select_photo([photo_a], person="Zzz Unknown")
    assert result is None


def test_select_photo__suggests_close_match_in_stderr(photo_a, capsys):
    select_photo([photo_a], person="alice")
    captured = capsys.readouterr()
    assert "Alice Smith" in captured.err


def test_select_photo__excludes_oversized(photo_oversized):
    result = select_photo([photo_oversized])
    assert result is None


def test_select_photo__allows_unknown_size(photo_no_date):
    # photo_no_date has no persons and size_bytes set; override size to None
    photo_no_date.size_bytes = None
    result = select_photo([photo_no_date])
    assert result is photo_no_date


def test_select_photo__returns_none_for_empty_library():
    assert select_photo([]) is None


def test_select_photo__never_picks_oversized_from_mixed_pool(photo_a, photo_oversized):
    # With 100 iterations, the oversized photo must never be selected
    results = [select_photo([photo_a, photo_oversized]) for _ in range(100)]
    assert photo_oversized not in results
    assert photo_a in results


# ---------------------------------------------------------------------------
# select_on_this_day
# ---------------------------------------------------------------------------


def test_select_on_this_day__matches_todays_monthday(
    fixed_today, photo_on_this_day, photo_b
):
    # photo_on_this_day has date="2018-02-20"; FIXED_TODAY = 2026-02-20
    # photo_b has date="2020-07-04" — does not match Feb 20
    result = select_on_this_day([photo_on_this_day, photo_b])
    assert result is photo_on_this_day


def test_select_on_this_day__no_match_returns_none(fixed_today, photo_b):
    # photo_b.date = "2020-07-04", FIXED_TODAY = Feb 20 — no match
    result = select_on_this_day([photo_b])
    assert result is None


def test_select_on_this_day__excludes_same_year(fixed_today):
    same_year_photo = PhotoRecord(
        path="/p/x.jpg",
        original_filename="x.jpg",
        date="2026-02-20",  # same year as FIXED_TODAY
        persons=[],
        size_bytes=1_000_000,
        location=None,
    )
    result = select_on_this_day([same_year_photo])
    assert result is None


def test_select_on_this_day__prefers_tagged_over_untagged(
    fixed_today, photo_on_this_day, photo_on_this_day_untagged
):
    # Both match Feb 20; photo_on_this_day has persons, photo_on_this_day_untagged does not.
    results = [
        select_on_this_day([photo_on_this_day, photo_on_this_day_untagged])
        for _ in range(50)
    ]
    assert photo_on_this_day_untagged not in results


def test_select_on_this_day__falls_back_to_untagged(
    fixed_today, photo_on_this_day_untagged
):
    result = select_on_this_day([photo_on_this_day_untagged])
    assert result is photo_on_this_day_untagged


def test_select_on_this_day__filters_by_person(
    fixed_today, photo_on_this_day, photo_on_this_day_untagged
):
    # photo_on_this_day has persons=["Alice Smith"]
    result = select_on_this_day(
        [photo_on_this_day, photo_on_this_day_untagged], person="Alice Smith"
    )
    assert result is photo_on_this_day


def test_select_on_this_day__falls_through_when_person_absent_from_candidates(
    fixed_today, photo_on_this_day
):
    # When the person has no on-this-day photos, the function doesn't filter
    # (person was already validated upstream by select_photo). It returns a
    # random on-this-day photo rather than None.
    result = select_on_this_day([photo_on_this_day], person="Bob Jones")
    assert result is photo_on_this_day


def test_select_on_this_day__respects_size_cap(fixed_today):
    big = PhotoRecord(
        path="/p/big.jpg",
        original_filename="big.jpg",
        date="2018-02-20",
        persons=[],
        size_bytes=25 * 1024 * 1024,  # over cap
        location=None,
    )
    assert select_on_this_day([big]) is None


def test_select_on_this_day__skips_no_date(fixed_today, photo_no_date):
    assert select_on_this_day([photo_no_date]) is None


def test_select_on_this_day__skips_invalid_date(fixed_today):
    bad = PhotoRecord(
        path="/p/bad.jpg",
        original_filename="bad.jpg",
        date="not-a-date",
        persons=[],
        size_bytes=1_000_000,
        location=None,
    )
    assert select_on_this_day([bad]) is None


# ---------------------------------------------------------------------------
# list_persons
# ---------------------------------------------------------------------------


def test_list_persons__prints_sorted_names_with_counts(photo_a, capsys):
    # photo_a has persons=["Alice Smith", "Bob Jones"]
    # Create a duplicate photo so Alice has count 2
    photo_a_copy = PhotoRecord(
        path="/photos/library/2019/birthday2.jpg",
        original_filename="birthday2.jpg",
        date="2019-02-20",
        persons=["Alice Smith"],
        size_bytes=5 * 1024 * 1024,
        location=None,
    )
    list_persons([photo_a, photo_a_copy])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    # Alice should appear before Bob (alphabetical)
    alice_line = next(l for l in lines if "Alice Smith" in l)
    bob_line = next(l for l in lines if "Bob Jones" in l)
    assert lines.index(alice_line) < lines.index(bob_line)
    # Alice count = 2
    assert "2" in alice_line
    # Bob count = 1
    assert "1" in bob_line


def test_list_persons__empty_message_when_no_persons(photo_b, capsys):
    list_persons([photo_b])
    captured = capsys.readouterr()
    assert "No named persons" in captured.out
