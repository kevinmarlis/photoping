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
from email.message import EmailMessage

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


def build_message(
    sender: str,
    recipient: str,
    photo_path: str,
    subject: str,
) -> EmailMessage:
    """Compose an EmailMessage with the photo attached and a simple HTML body."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    photo = pathlib.Path(photo_path)
    if not photo.exists():
        print(f"Error: Photo not found at {photo_path}", file=sys.stderr)
        sys.exit(1)

    # Plain text fallback
    msg.set_content("A photo for you. See attachment.")

    # HTML body with the image inlined
    cid = "photo"
    msg.add_alternative(
        f"""\
        <html>
          <body style="font-family: sans-serif; background: #f5f5f5; padding: 24px;">
            <img src="cid:{cid}"
                 style="max-width: 100%; border-radius: 8px; display: block; margin: 0 auto;"
                 alt="{photo.name}">
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


def send_photo(photo_path: str, subject: str = "A photo for you") -> None:
    """
    Send a photo to the configured recipient via Gmail SMTP.

    Args:
        photo_path: Absolute path to the image file.
        subject:    Email subject line.
    """
    config = load_config()

    msg = build_message(
        sender=config["sender_email"],
        recipient=config["recipient_email"],
        photo_path=photo_path,
        subject=subject,
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
