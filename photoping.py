"""
photoping.py

Main entry point. Selects a random photo (and an "on this day" photo if one
exists) and emails them to the recipient(s).

Person and schedule settings are read from .env. Command-line arguments
override the .env values for one-off runs.

Usage:
    python photoping.py                    # uses PERSON_NAME from .env (or full library)
    python photoping.py "Alice Smith"      # override person for this run
    python photoping.py --dry-run          # select photos but don't send the email
"""

import argparse
import logging
import os
import sys
from datetime import date as date_type, datetime

from dotenv import load_dotenv

import email_sender
import photo_selector

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _years_ago_label(date_str: str) -> str:
    """Return a label like 'On this day, 5 years ago' from a 'YYYY-MM-DD' string."""
    try:
        photo_year = datetime.strptime(date_str, "%Y-%m-%d").year
    except ValueError:
        return "On this day"
    years = date_type.today().year - photo_year
    unit = "year" if years == 1 else "years"
    return f"On this day, {years} {unit} ago"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send a random photo from your Mac Photos library via email."
    )
    parser.add_argument(
        "person",
        nargs="?",
        metavar="PERSON_NAME",
        help=(
            "Person to select a photo of. "
            "Overrides PERSON_NAME in .env. "
            "Omit both to draw from the entire library."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Select photos and log what would be sent, but do not send the email.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Rebuild the photo cache before selecting.",
    )
    args = parser.parse_args()

    # Resolve person: CLI arg > .env > None (full library)
    person = args.person or os.environ.get("PERSON_NAME", "").strip() or None

    log.info(
        "Loading photo library%s...",
        " (refreshing cache)" if args.refresh_cache else "",
    )
    photos = photo_selector.get_photos(force_refresh=args.refresh_cache)

    # --- Random photo (required) ---
    log.info(
        "Selecting a random photo%s.",
        f" of '{person}'" if person else " from the full library",
    )
    photo = photo_selector.select_photo(photos, person=person)

    if photo is None:
        log.error("No photo selected. Exiting.")
        sys.exit(1)

    log.info("Random:     %s (%s)", photo.original_filename, photo.date or "no date")

    # --- On this day photo (optional) ---
    on_this_day = photo_selector.select_on_this_day(photos, person=person)
    if on_this_day:
        log.info(
            "On this day: %s (%s)",
            on_this_day.original_filename,
            on_this_day.date or "no date",
        )
    else:
        log.info("On this day: no matching photo found for today's date.")

    if args.dry_run:
        log.info("Dry run — email not sent.")
        return

    # --- Build email entries ---
    entries = [
        email_sender.PhotoEntry(
            path=photo.path,
            date=photo.date,
            location=photo.location,
        )
    ]
    if on_this_day:
        entries.append(
            email_sender.PhotoEntry(
                path=on_this_day.path,
                date=on_this_day.date,
                location=on_this_day.location,
                label=_years_ago_label(on_this_day.date)
                if on_this_day.date
                else "On this day",
            )
        )

    # --- Subject line ---
    subject = os.environ.get("EMAIL_SUBJECT", "").strip()
    if not subject:
        if on_this_day and on_this_day.date:
            year = on_this_day.date[:4]
            subject = f"A photo for you + a memory from {year}"
        else:
            subject = "A photo for you"

    email_sender.send_photos(entries, subject=subject)


if __name__ == "__main__":
    main()
