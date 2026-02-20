"""
photo_selector.py

Select a random photo from the Mac Photos library.
- With a person name: selects from photos tagged with that person.
- Without a person name: selects from the entire library.

Photo data is cached to disk and only rebuilt when the Photos library changes.

Usage:
    python photo_selector.py                    # random from entire library
    python photo_selector.py "Alice Smith"      # random photo of Alice Smith
    python photo_selector.py --list-persons     # list all known person names
    python photo_selector.py --refresh-cache    # force a cache rebuild
"""

import argparse
import os
import pickle
import pathlib
import random
import sys
from dataclasses import dataclass, field
from typing import Optional

import osxphotos

CACHE_FILE = pathlib.Path(__file__).parent / ".photos_cache.pkl"
CACHE_VERSION = 2  # increment when PhotoRecord fields change
MAX_PHOTO_SIZE_MB = 20
MAX_PHOTO_SIZE_BYTES = MAX_PHOTO_SIZE_MB * 1024 * 1024


@dataclass
class PhotoRecord:
    """Lightweight snapshot of a photo's metadata, used in place of PhotoInfo after caching."""

    path: str
    original_filename: str
    date: Optional[str]
    persons: list = field(default_factory=list)
    title: Optional[str] = None
    size_bytes: Optional[int] = None
    location: Optional[str] = None


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def _db_mtime(library_path: str) -> Optional[float]:
    """Return the mtime of the Photos SQLite file, or None if not found."""
    sqlite_path = pathlib.Path(library_path) / "database" / "Photos.sqlite"
    try:
        return sqlite_path.stat().st_mtime
    except FileNotFoundError:
        return None


def _load_cache() -> Optional[dict]:
    """Load the cache if it exists, is still fresh, and matches the current schema version."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "rb") as f:
            cache = pickle.load(f)
        if cache.get("version") != CACHE_VERSION:
            return None  # schema changed, rebuild
        current_mtime = _db_mtime(cache["library_path"])
        if current_mtime is not None and cache["db_mtime"] == current_mtime:
            return cache
    except Exception:
        pass
    return None


def _build_and_save_cache(db: osxphotos.PhotosDB) -> dict:
    """Extract photo records from the library, save to disk, and return the cache dict."""
    print("Building photo cache (this runs once, then stays fast)...")
    photos = []
    for p in db.photos():
        if p.path is None:
            continue

        try:
            size_bytes = os.path.getsize(p.path)
        except OSError:
            size_bytes = None

        location = None
        try:
            if p.place:
                location = p.place.name
        except Exception:
            pass

        photos.append(
            PhotoRecord(
                path=p.path,
                original_filename=p.original_filename,
                date=p.date.strftime("%Y-%m-%d") if p.date else None,
                persons=p.persons or [],
                title=p.title or None,
                size_bytes=size_bytes,
                location=location,
            )
        )

    cache = {
        "version": CACHE_VERSION,
        "library_path": db.library_path,
        "db_mtime": _db_mtime(db.library_path),
        "photos": photos,
    }
    with open(CACHE_FILE, "wb") as f:
        pickle.dump(cache, f)
    print(f"Cached {len(photos)} local photos.")
    return cache


def get_photos(force_refresh: bool = False) -> list:
    """
    Return a list of PhotoRecord objects, using the on-disk cache when possible.
    Rebuilds the cache if it is missing, stale, or force_refresh is True.
    """
    if not force_refresh:
        cache = _load_cache()
        if cache:
            return cache["photos"]

    # Cache miss — load osxphotos, build cache
    try:
        db = osxphotos.PhotosDB()
    except Exception as e:
        print(f"Error: Could not open Photos library: {e}", file=sys.stderr)
        print(
            "Make sure this terminal has Full Disk Access enabled in\n"
            "System Settings → Privacy & Security → Full Disk Access.",
            file=sys.stderr,
        )
        sys.exit(1)

    cache = _build_and_save_cache(db)
    return cache["photos"]


# ---------------------------------------------------------------------------
# Selection logic
# ---------------------------------------------------------------------------


def list_persons(photos: list) -> None:
    """Print all named persons and their photo counts."""
    counts: dict = {}
    for p in photos:
        for name in p.persons:
            counts[name] = counts.get(name, 0) + 1

    if not counts:
        print("No named persons found in the Photos library.")
        return

    print(f"{'Person':<40} {'Photos':>6}")
    print("-" * 48)
    for name, count in sorted(counts.items(), key=lambda x: x[0].lower()):
        print(f"{name:<40} {count:>6}")


def select_photo(photos: list, person: Optional[str] = None) -> Optional[PhotoRecord]:
    """
    Select a random photo from the cached photo list.

    Args:
        photos: Full list of PhotoRecord objects.
        person: Person name to filter by, or None to use the entire library.

    Returns:
        A PhotoRecord, or None if no eligible photos were found.
    """
    if person:
        # Build a case-insensitive name index from available photos
        known: dict = {}
        for p in photos:
            for name in p.persons:
                known.setdefault(name.lower(), name)

        canonical = known.get(person.lower())
        if canonical is None:
            print(
                f"Error: No person named '{person}' found in the library.",
                file=sys.stderr,
            )
            close = [n for n in known.values() if person.lower() in n.lower()]
            if close:
                print(f"Did you mean one of: {', '.join(close)}?", file=sys.stderr)
            return None

        pool = [p for p in photos if canonical in p.persons]
        label = f"'{canonical}'"
    else:
        pool = photos
        label = "entire library"

    if not pool:
        print(f"No locally available photos found for {label}.", file=sys.stderr)
        return None

    # Filter out photos over the size cap (skip check if size is unknown)
    sized_pool = [
        p for p in pool
        if p.size_bytes is None or p.size_bytes <= MAX_PHOTO_SIZE_BYTES
    ]
    if not sized_pool:
        print(
            f"All photos for {label} exceed the {MAX_PHOTO_SIZE_MB} MB size cap.",
            file=sys.stderr,
        )
        return None
    if len(sized_pool) < len(pool):
        print(
            f"Skipped {len(pool) - len(sized_pool)} photo(s) over {MAX_PHOTO_SIZE_MB} MB."
        )

    chosen = random.choice(sized_pool)
    print(f"Selected 1 of {len(sized_pool)} eligible photos from {label}.")
    return chosen


def print_photo_info(photo: PhotoRecord) -> None:
    """Print a summary of the selected photo."""
    print(f"  Path:     {photo.path}")
    print(f"  Filename: {photo.original_filename}")
    print(f"  Date:     {photo.date or 'unknown'}")
    if photo.location:
        print(f"  Location: {photo.location}")
    if photo.size_bytes is not None:
        print(f"  Size:     {photo.size_bytes / (1024 * 1024):.1f} MB")
    if photo.persons:
        print(f"  Persons:  {', '.join(photo.persons)}")
    if photo.title:
        print(f"  Title:    {photo.title}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select a random photo from your Mac Photos library."
    )
    parser.add_argument(
        "person",
        nargs="?",
        metavar="PERSON_NAME",
        help="Name of the person to filter by (optional). Use quotes for full names.",
    )
    parser.add_argument(
        "--list-persons",
        action="store_true",
        help="List all named persons in the library and exit.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Force a rebuild of the photo cache, then exit.",
    )
    args = parser.parse_args()

    photos = get_photos(force_refresh=args.refresh_cache)

    if args.refresh_cache:
        print("Cache refreshed.")
        return

    if args.list_persons:
        list_persons(photos)
        return

    photo = select_photo(photos, person=args.person)
    if photo:
        print_photo_info(photo)


if __name__ == "__main__":
    main()
