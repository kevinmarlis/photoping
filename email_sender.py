"""
email_sender.py

Send a photo via email using Gmail SMTP.

Reads configuration from a .env file in the project directory:
    SENDER_EMAIL    - Gmail address to send from
    SENDER_PASSWORD - Gmail App Password (not your regular password)
    RECIPIENT_EMAIL - Address to deliver photos to

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
from datetime import datetime
from email.message import EmailMessage
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 465  # SSL


def _require_env(key: str) -> str:
    """Return an environment variable, or exit with a clear error if missing."""
    value = os.environ.get(key, "").strip()
    if not value:
        print(f"Error: {key} is not set. Add it to your .env file.", file=sys.stderr)
        sys.exit(1)
    return value


def load_config() -> dict:
    return {
        "sender_email": _require_env("SENDER_EMAIL"),
        "sender_password": _require_env("SENDER_PASSWORD"),
        "recipient_email": _require_env("RECIPIENT_EMAIL"),
    }


def _format_date(date_str: Optional[str]) -> Optional[str]:
    """Convert 'YYYY-MM-DD' to 'Month D, YYYY' (e.g. 'March 15, 2019')."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return date_str


def build_message(
    sender: str,
    recipient: str,
    photo_path: str,
    subject: str,
    date: Optional[str] = None,
    location: Optional[str] = None,
) -> EmailMessage:
    """Compose an EmailMessage with the photo inlined and optional metadata caption."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    photo = pathlib.Path(photo_path)
    if not photo.exists():
        print(f"Error: Photo not found at {photo_path}", file=sys.stderr)
        sys.exit(1)

    # Build plain-text fallback
    meta_parts = [p for p in [_format_date(date), location] if p]
    plain_meta = f"\n{' · '.join(meta_parts)}" if meta_parts else ""
    msg.set_content(f"A photo for you.{plain_meta}")

    # Build metadata caption for the HTML body
    formatted_date = _format_date(date)
    caption_parts = [p for p in [formatted_date, location] if p]
    caption_html = (
        f'<p style="margin: 12px 0 0; color: #888; font-size: 13px; text-align: center;">'
        f'{" &nbsp;·&nbsp; ".join(caption_parts)}</p>'
        if caption_parts else ""
    )

    cid = "photo"
    msg.add_alternative(
        f"""\
        <html>
          <body style="font-family: sans-serif; background: #f5f5f5; padding: 24px; margin: 0;">
            <div style="max-width: 600px; margin: 0 auto;">
              <img src="cid:{cid}"
                   style="max-width: 100%; border-radius: 8px; display: block;"
                   alt="{photo.name}">
              {caption_html}
            </div>
          </body>
        </html>
        """,
        subtype="html",
    )

    # Attach the image and link it to the CID used above
    mime_type, _ = mimetypes.guess_type(photo_path)
    maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)
    with open(photo_path, "rb") as f:
        image_data = f.read()

    # Add the inline image to the HTML part
    html_part = msg.get_payload(1)  # index 1 is the HTML alternative
    html_part.add_related(image_data, maintype=maintype, subtype=subtype, cid=cid)

    return msg


def send_photo(
    photo_path: str,
    subject: str = "A photo for you",
    date: Optional[str] = None,
    location: Optional[str] = None,
) -> None:
    """
    Send a photo to the configured recipient via Gmail SMTP.

    Args:
        photo_path: Absolute path to the image file.
        subject:    Email subject line.
        date:       Photo date string ('YYYY-MM-DD'), shown in the email caption.
        location:   Human-readable location string, shown in the email caption.
    """
    config = load_config()

    msg = build_message(
        sender=config["sender_email"],
        recipient=config["recipient_email"],
        photo_path=photo_path,
        subject=subject,
        date=date,
        location=location,
    )

    print(f"Sending to {config['recipient_email']} via Gmail SMTP...")
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
