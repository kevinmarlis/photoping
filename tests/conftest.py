"""
Shared pytest fixtures for the photoping test suite.
"""
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from photo_selector import PhotoRecord

FIXED_TODAY = date(2026, 2, 20)
FIXED_TODAY_STR = f"{FIXED_TODAY.month:02d}-{FIXED_TODAY.day:02d}"  # "02-20"


# ---------------------------------------------------------------------------
# PhotoRecord fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def photo_a():
    """Typical photo: tagged persons, location, 5 MB, Feb 20 2019."""
    return PhotoRecord(
        path="/photos/library/2019/birthday.jpg",
        original_filename="birthday.jpg",
        date="2019-02-20",
        persons=["Alice Smith", "Bob Jones"],
        title="Birthday party",
        size_bytes=5 * 1024 * 1024,
        location="New York, NY",
    )


@pytest.fixture
def photo_b():
    """Photo with no persons, no location, July 4 2020."""
    return PhotoRecord(
        path="/photos/library/2020/sunset.jpg",
        original_filename="sunset.jpg",
        date="2020-07-04",
        persons=[],
        title=None,
        size_bytes=8 * 1024 * 1024,
        location=None,
    )


@pytest.fixture
def photo_oversized():
    """Photo that exceeds the 20 MB size cap."""
    return PhotoRecord(
        path="/photos/library/2021/raw.jpg",
        original_filename="raw.jpg",
        date="2021-03-10",
        persons=["Alice Smith"],
        size_bytes=25 * 1024 * 1024,
        location=None,
    )


@pytest.fixture
def photo_no_date():
    """Photo with no date and no persons."""
    return PhotoRecord(
        path="/photos/library/unknown/scan.jpg",
        original_filename="scan.jpg",
        date=None,
        persons=[],
        size_bytes=2 * 1024 * 1024,
        location=None,
    )


@pytest.fixture
def photo_on_this_day():
    """Photo taken on Feb 20, 2018 — matches FIXED_TODAY's month/day."""
    return PhotoRecord(
        path="/photos/library/2018/anniversary.jpg",
        original_filename="anniversary.jpg",
        date="2018-02-20",
        persons=["Alice Smith"],
        size_bytes=4 * 1024 * 1024,
        location="London, UK",
    )


@pytest.fixture
def photo_on_this_day_untagged():
    """Photo taken on Feb 20, 2017 — matches FIXED_TODAY but has no person tags."""
    return PhotoRecord(
        path="/photos/library/2017/landscape.jpg",
        original_filename="landscape.jpg",
        date="2017-02-20",
        persons=[],
        size_bytes=3 * 1024 * 1024,
        location=None,
    )


@pytest.fixture
def sample_library(photo_a, photo_b, photo_oversized, photo_no_date):
    """Mixed library of four PhotoRecord objects."""
    return [photo_a, photo_b, photo_oversized, photo_no_date]


# ---------------------------------------------------------------------------
# Date mock fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fixed_today(monkeypatch):
    """Patch photo_selector.date_type so .today() returns FIXED_TODAY (2026-02-20)."""
    mock_date_type = MagicMock()
    mock_date_type.today.return_value = FIXED_TODAY
    monkeypatch.setattr("photo_selector.date_type", mock_date_type)
    return FIXED_TODAY


# ---------------------------------------------------------------------------
# Email fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_vars(monkeypatch):
    """Set required email environment variables."""
    monkeypatch.setenv("SENDER_EMAIL", "sender@gmail.com")
    monkeypatch.setenv("SENDER_PASSWORD", "app-password-1234")
    monkeypatch.setenv("RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.setenv("SENDER_NAME", "Test Sender")


@pytest.fixture
def fake_photo(tmp_path):
    """Write a minimal JPEG to tmp_path and return the path string."""
    p = tmp_path / "test.jpg"
    # Minimal JPEG header so mimetypes.guess_type returns image/jpeg
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return str(p)


@pytest.fixture
def fake_photo2(tmp_path):
    """A second minimal JPEG for multi-photo email tests."""
    p = tmp_path / "test2.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return str(p)


# ---------------------------------------------------------------------------
# osxphotos mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_photo_info():
    """A mock osxphotos PhotoInfo-like object."""
    p = MagicMock()
    p.path = "/fake/Photos Library.photoslibrary/originals/photo1.jpg"
    p.original_filename = "photo1.jpg"
    p.date = datetime(2019, 3, 15, 12, 0, 0)
    p.persons = ["Alice Smith"]
    p.title = "Party"
    p.screenshot = False
    p.screen_recording = False
    p.place = MagicMock()
    p.place.name = "Paris"
    return p


@pytest.fixture
def mock_db(mock_photo_info):
    """A mock osxphotos.PhotosDB instance with one photo."""
    db = MagicMock()
    db.library_path = "/fake/Photos Library.photoslibrary"
    db.photos.return_value = [mock_photo_info]
    return db
