"""
photoping.py

Main entry point. Selects a random photo and emails it to the recipient.

Person and schedule settings are read from .env. Command-line arguments
override the .env values for one-off runs.

Usage:
    python photoping.py                    # uses PERSON_NAME from .env (or full library)
    python photoping.py "Alice Smith"      # override person for this run
    python photoping.py --dry-run          # select a photo but don't send the email
"""

import argparse
import logging
import os
import sys

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
        help="Select a photo and log what would be sent, but do not send the email.",
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

    log.info(
        "Selecting a photo%s.",
        f" of '{person}'" if person else " from the full library",
    )
    photo = photo_selector.select_photo(photos, person=person)

    if photo is None:
        log.error("No photo selected. Exiting.")
        sys.exit(1)

    log.info("Selected: %s (%s)", photo.original_filename, photo.date or "no date")

    if args.dry_run:
        log.info("Dry run — email not sent.")
        return

    subject = os.environ.get("EMAIL_SUBJECT", "").strip() or "A photo for you"
    email_sender.send_photo(
        photo_path=photo.path,
        subject=subject,
        date=photo.date,
        location=photo.location,
    )


if __name__ == "__main__":
    main()
