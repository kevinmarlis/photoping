"""
email_sender.py

Send one or more photos via email using Gmail SMTP.

Reads configuration from a .env file in the project directory:
    SENDER_EMAIL    - Gmail address to send from
    SENDER_PASSWORD - Gmail App Password (not your regular password)
    RECIPIENT_EMAIL - One or more comma-separated addresses to deliver photos to

Usage (standalone):
    python email_sender.py /path/to/photo.jpg
    python email_sender.py /path/to/photo.jpg --subject "Throwback photo"
"""

import argparse
import mimetypes
import os
import pathlib
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


@dataclass
class PhotoEntry:
    """A single photo to include in an email, with optional metadata."""

    path: str
    date: Optional[str] = None  # 'YYYY-MM-DD'
    location: Optional[str] = None
    label: Optional[str] = None  # Section header shown above the photo


def _require_env(key: str) -> str:
    """Return an environment variable, or exit with a clear error if missing."""
    value = os.environ.get(key, "").strip()
    if not value:
        print(f"Error: {key} is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)
    return value


def load_config() -> dict:
    raw_recipients = _require_env("RECIPIENT_EMAIL")
    recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
    sender_email = _require_env("SENDER_EMAIL")
    sender_name = os.environ.get("SENDER_NAME", "").strip() or None
    return {
        "sender_email": sender_email,
        "sender_password": _require_env("SENDER_PASSWORD"),
        "recipient_emails": recipients,
        # Format as "Name <email>" if a display name is configured
        "sender_formatted": formataddr((sender_name, sender_email))
        if sender_name
        else sender_email,
    }


def _format_date(date_str: Optional[str]) -> Optional[str]:
    """Convert 'YYYY-MM-DD' to 'Month D, YYYY' (e.g. 'March 15, 2019')."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def _caption_html(entry: PhotoEntry) -> str:
    """Return the HTML caption paragraph for a photo entry, or empty string."""
    parts = [p for p in [_format_date(entry.date), entry.location] if p]
    if not parts:
        return ""
    return (
        '<p style="margin: 10px 0 0; color: #999; font-size: 13px; text-align: center;">'
        + " &nbsp;·&nbsp; ".join(parts)
        + "</p>"
    )


def _label_html(label: str) -> str:
    """Return the HTML section-header element for an 'on this day' style label."""
    return (
        '<p style="margin: 0 0 16px; font-size: 11px; font-weight: 600; '
        'text-transform: uppercase; letter-spacing: 0.08em; color: #bbb; text-align: center;">'
        + label
        + "</p>"
    )


def _intro_html(entries: List[PhotoEntry]) -> str:
    """
    Return a brief sentence to display above the first photo.
    Gives email clients text to preview and helps avoid image-only spam signals.
    """
    first = entries[0]
    date_str = _format_date(first.date)
    parts = [p for p in [date_str, first.location] if p]
    if len(entries) > 1:
        year = entries[1].date[:4] if entries[1].date else None
        tail = f", plus a memory from {year}" if year else ", plus a memory"
    else:
        tail = ""
    body = (
        "A photo from " + " in ".join(parts) if parts else "A photo from your library"
    )
    return (
        f'<p style="color: #666; font-size: 14px; line-height: 1.6; '
        f'margin: 0 0 16px; text-align: center;">{body}{tail}.</p>'
    )


def build_message(
    sender: str,
    recipients: List[str],
    entries: List[PhotoEntry],
    subject: str,
) -> EmailMessage:
    """
    Compose an EmailMessage with one or more photos inlined.
    Photos after the first are separated by a divider and an optional label.
    """
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Reply-To"] = sender
    msg["Subject"] = subject

    # Validate all paths up front
    for entry in entries:
        if not pathlib.Path(entry.path).exists():
            print(f"Error: Photo not found at {entry.path}", file=sys.stderr)
            sys.exit(1)

    # Plain-text fallback — include intro sentence so the email isn't content-free
    first = entries[0]
    first_parts = [p for p in [_format_date(first.date), first.location] if p]
    intro_text = (
        ("A photo from " + " in ".join(first_parts))
        if first_parts
        else "A photo from your library"
    )
    plain_lines = [intro_text + "."]
    for entry in entries:
        if entry.label:
            plain_lines.append("\n" + entry.label)
        parts = [p for p in [_format_date(entry.date), entry.location] if p]
        if parts:
            plain_lines.append(" · ".join(parts))
    msg.set_content("\n".join(plain_lines))

    # Build HTML photo blocks
    photo_blocks = [_intro_html(entries)]
    for i, entry in enumerate(entries):
        cid = f"photo_{i}"
        block = ""
        if i > 0:
            block += '<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 28px 0;">'
        if entry.label:
            block += _label_html(entry.label)
        block += (
            f'<img src="cid:{cid}" '
            f'style="max-width: 100%; border-radius: 8px; display: block;" '
            f'alt="{pathlib.Path(entry.path).name}">'
        )
        block += _caption_html(entry)
        photo_blocks.append(block)

    html_body = "\n".join(photo_blocks)
    msg.add_alternative(
        f"""\
        <html>
          <body style="font-family: sans-serif; background: #f5f5f5; padding: 24px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto;">
              {html_body}
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    # Attach each image as a related part linked to its CID
    html_part = msg.get_payload(1)  # index 1 is the HTML alternative
    for i, entry in enumerate(entries):
        cid = f"photo_{i}"
        mime_type, _ = mimetypes.guess_type(entry.path)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
        with open(entry.path, "rb") as f:
            image_data = f.read()
        html_part.add_related(image_data, maintype=maintype, subtype=subtype, cid=cid)

    return msg


def send_photos(entries: List[PhotoEntry], subject: str = "A photo for you") -> None:
    """
    Send one or more photos to all configured recipients via Gmail SMTP.

    Args:
        entries: List of PhotoEntry objects (in display order).
        subject: Email subject line.
    """
    config = load_config()

    msg = build_message(
        sender=config["sender_formatted"],
        recipients=config["recipient_emails"],
        entries=entries,
        subject=subject,
    )

    recipients_str = ", ".join(config["recipient_emails"])
    print(f"Sending to {recipients_str} via Gmail SMTP...")
    try:
        with smtplib.SMTP_SSL(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as smtp:
            smtp.login(config["sender_email"], config["sender_password"])
            smtp.send_message(msg)
        print("Email sent successfully.")
    except smtplib.SMTPAuthenticationError:
        print(
            "Error: Gmail authentication failed.\n"
            "Make sure SENDER_PASSWORD is a Gmail App Password, not your account password.\n"
            "Generate one at: https://myaccount.google.com/apppasswords",
            file=sys.stderr,
        )
        sys.exit(1)
    except smtplib.SMTPException as e:
        print(f"Error: Failed to send email: {e}", file=sys.stderr)
        sys.exit(1)


def send_photo(
    photo_path: str,
    subject: str = "A photo for you",
    date: Optional[str] = None,
    location: Optional[str] = None,
) -> None:
    """Single-photo convenience wrapper around send_photos. Used by the CLI."""
    send_photos(
        [PhotoEntry(path=photo_path, date=date, location=location)], subject=subject
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send a photo via Gmail.")
    parser.add_argument(
        "photo", metavar="PHOTO_PATH", help="Path to the photo to send."
    )
    parser.add_argument(
        "--subject",
        default="A photo for you",
        help='Email subject line (default: "A photo for you").',
    )
    args = parser.parse_args()
    send_photo(photo_path=args.photo, subject=args.subject)


if __name__ == "__main__":
    main()
