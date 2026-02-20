"""
photo_selector.py

Select a random photo from the Mac Photos library.
- With a person name: selects from photos tagged with that person.
- Without a person name: selects from the entire library.

Usage:
    python photo_selector.py                    # random from entire library
    python photo_selector.py "Alice Smith"      # random photo of Alice Smith
    python photo_selector.py --list-persons     # list all known person names
"""

import argparse
import random
import sys

import osxphotos


def load_library() -> osxphotos.PhotosDB:
    """Load the default Photos library. Requires Full Disk Access."""
    try:
        return osxphotos.PhotosDB()
    except Exception as e:
        print(f"Error: Could not open Photos library: {e}", file=sys.stderr)
        print(
            "Make sure this terminal has Full Disk Access enabled in\n"
            "System Settings → Privacy & Security → Full Disk Access.",
            file=sys.stderr,
        )
        sys.exit(1)


def list_persons(db: osxphotos.PhotosDB) -> None:
    """Print all named persons in the library with their photo counts."""
    persons = db.persons_as_dict  # {name: count}
    if not persons:
        print("No named persons found in the Photos library.")
        return
    print(f"{'Person':<40} {'Photos':>6}")
    print("-" * 48)
    for name, count in sorted(persons.items(), key=lambda x: x[0].lower()):
        print(f"{name:<40} {count:>6}")


def select_photo(db: osxphotos.PhotosDB, person: str | None = None) -> osxphotos.PhotoInfo | None:
    """
    Select a random locally-available photo.

    Args:
        db: Loaded PhotosDB instance.
        person: Person name to filter by, or None for the full library.

    Returns:
        A PhotoInfo object, or None if no eligible photos were found.
    """
    if person:
        # Validate the person name exists before querying
        known = {p.lower(): p for p in db.persons}
        canonical = known.get(person.lower())
        if canonical is None:
            print(
                f"Error: No person named '{person}' found in the library.",
                file=sys.stderr,
            )
            close_matches = [p for p in db.persons if person.lower() in p.lower()]
            if close_matches:
                print(f"Did you mean one of: {', '.join(close_matches)}?", file=sys.stderr)
            return None
        photos = db.photos(persons=[canonical])
        label = f"'{canonical}'"
    else:
        photos = db.photos()
        label = "entire library"

    # Only consider photos with a local file path (excludes iCloud-only assets)
    local_photos = [p for p in photos if p.path is not None]

    if not local_photos:
        if person:
            print(
                f"No locally available photos found for {label}.\n"
                "Photos may be stored in iCloud with 'Optimize Mac Storage' enabled.",
                file=sys.stderr,
            )
        else:
            print("No locally available photos found in the library.", file=sys.stderr)
        return None

    chosen = random.choice(local_photos)
    print(f"Selected 1 of {len(local_photos)} local photos from {label}.")
    return chosen


def print_photo_info(photo: osxphotos.PhotoInfo) -> None:
    """Print a summary of the selected photo."""
    print(f"  Path:     {photo.path}")
    print(f"  Filename: {photo.original_filename}")
    print(f"  Date:     {photo.date.strftime('%Y-%m-%d') if photo.date else 'unknown'}")
    if photo.persons:
        print(f"  Persons:  {', '.join(photo.persons)}")
    if photo.title:
        print(f"  Title:    {photo.title}")


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
    args = parser.parse_args()

    print("Loading Photos library...")
    db = load_library()

    if args.list_persons:
        list_persons(db)
        return

    photo = select_photo(db, person=args.person)
    if photo:
        print_photo_info(photo)


if __name__ == "__main__":
    main()
