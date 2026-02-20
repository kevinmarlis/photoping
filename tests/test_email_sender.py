"""
Tests for email_sender.py

Gmail SMTP is mocked throughout — these tests run without real credentials.
"""
import smtplib
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

import pytest

from email_sender import (
    PhotoEntry,
    _caption_html,
    _format_date,
    _intro_html,
    _label_html,
    build_message,
    load_config,
    send_photos,
)


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------


def test__format_date__converts_iso_to_long_form():
    assert _format_date("2019-03-15") == "March 15, 2019"


def test__format_date__single_digit_day():
    assert _format_date("2019-03-05") == "March 5, 2019"


def test__format_date__handles_none():
    assert _format_date(None) is None


def test__format_date__returns_input_on_invalid():
    assert _format_date("not-a-date") == "not-a-date"


# ---------------------------------------------------------------------------
# _caption_html
# ---------------------------------------------------------------------------


def test__caption_html__with_date_and_location():
    entry = PhotoEntry(path="x.jpg", date="2019-03-15", location="Paris")
    html = _caption_html(entry)
    assert "March 15, 2019" in html
    assert "Paris" in html
    assert "·" in html


def test__caption_html__date_only():
    entry = PhotoEntry(path="x.jpg", date="2019-03-15", location=None)
    html = _caption_html(entry)
    assert "March 15, 2019" in html
    assert "·" not in html


def test__caption_html__location_only():
    entry = PhotoEntry(path="x.jpg", date=None, location="London")
    html = _caption_html(entry)
    assert "London" in html


def test__caption_html__empty_when_no_fields():
    entry = PhotoEntry(path="x.jpg", date=None, location=None)
    assert _caption_html(entry) == ""


# ---------------------------------------------------------------------------
# _label_html
# ---------------------------------------------------------------------------


def test__label_html__contains_label_text():
    html = _label_html("On this day, 5 years ago")
    assert "On this day, 5 years ago" in html


def test__label_html__is_paragraph_element():
    html = _label_html("test")
    assert html.startswith("<p ")
    assert html.endswith("</p>")


# ---------------------------------------------------------------------------
# _intro_html
# ---------------------------------------------------------------------------


def test__intro_html__single_entry_with_date_and_location():
    entries = [PhotoEntry(path="x.jpg", date="2019-03-15", location="Paris")]
    html = _intro_html(entries)
    assert "March 15, 2019" in html
    assert "Paris" in html
    assert "plus a memory" not in html


def test__intro_html__two_entries_adds_memory_year():
    entry1 = PhotoEntry(path="x.jpg", date="2019-03-15", location="Paris")
    entry2 = PhotoEntry(path="y.jpg", date="2018-02-20", location=None)
    html = _intro_html([entry1, entry2])
    assert "plus a memory from 2018" in html


def test__intro_html__two_entries_no_date_on_second():
    entry1 = PhotoEntry(path="x.jpg", date="2019-03-15")
    entry2 = PhotoEntry(path="y.jpg", date=None)
    html = _intro_html([entry1, entry2])
    assert "plus a memory" in html


def test__intro_html__fallback_when_no_metadata():
    entries = [PhotoEntry(path="x.jpg", date=None, location=None)]
    html = _intro_html(entries)
    assert "from your library" in html


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config__reads_all_vars(env_vars):
    config = load_config()
    assert config["sender_email"] == "sender@gmail.com"
    assert config["sender_password"] == "app-password-1234"
    assert config["recipient_emails"] == ["recipient@example.com"]


def test_load_config__parses_multiple_recipients(monkeypatch, env_vars):
    monkeypatch.setenv("RECIPIENT_EMAIL", "a@x.com, b@x.com , c@x.com")
    config = load_config()
    assert config["recipient_emails"] == ["a@x.com", "b@x.com", "c@x.com"]


def test_load_config__formats_sender_with_name(env_vars):
    config = load_config()
    assert "Test Sender" in config["sender_formatted"]
    assert "sender@gmail.com" in config["sender_formatted"]


def test_load_config__formats_sender_without_name(monkeypatch, env_vars):
    monkeypatch.delenv("SENDER_NAME")
    config = load_config()
    assert config["sender_formatted"] == "sender@gmail.com"


def test_load_config__exits_when_sender_email_missing(monkeypatch, env_vars):
    monkeypatch.delenv("SENDER_EMAIL")
    with pytest.raises(SystemExit):
        load_config()


def test_load_config__exits_when_password_missing(monkeypatch, env_vars):
    monkeypatch.delenv("SENDER_PASSWORD")
    with pytest.raises(SystemExit):
        load_config()


def test_load_config__exits_when_recipient_missing(monkeypatch, env_vars):
    monkeypatch.delenv("RECIPIENT_EMAIL")
    with pytest.raises(SystemExit):
        load_config()


# ---------------------------------------------------------------------------
# build_message
# ---------------------------------------------------------------------------


def test_build_message__constructs_valid_emailmessage(env_vars, fake_photo):
    entries = [PhotoEntry(path=fake_photo, date="2019-03-15", location="Paris")]
    msg = build_message("sender@gmail.com", ["r@x.com"], entries, "Test Subject")
    assert isinstance(msg, EmailMessage)
    assert msg["Subject"] == "Test Subject"
    assert msg["From"] == "sender@gmail.com"
    assert "r@x.com" in msg["To"]


def test_build_message__contains_cid_reference(env_vars, fake_photo):
    entries = [PhotoEntry(path=fake_photo)]
    msg = build_message("s@g.com", ["r@x.com"], entries, "s")
    assert "cid:photo_0" in msg.as_string()


def test_build_message__two_photos_have_divider_and_label(env_vars, fake_photo, fake_photo2):
    entries = [
        PhotoEntry(path=fake_photo, date="2019-01-01"),
        PhotoEntry(path=fake_photo2, date="2018-01-01", label="On this day"),
    ]
    msg = build_message("s@g.com", ["r@x.com"], entries, "s")
    msg_str = msg.as_string()
    assert "cid:photo_1" in msg_str
    assert "On this day" in msg_str
    assert "border-top" in msg_str


def test_build_message__exits_when_photo_path_missing(env_vars):
    entries = [PhotoEntry(path="/nonexistent/photo.jpg")]
    with pytest.raises(SystemExit):
        build_message("s@g.com", ["r@x.com"], entries, "s")


def test_build_message__plain_text_fallback_present(env_vars, fake_photo):
    entries = [PhotoEntry(path=fake_photo, date="2019-01-01", location="NYC")]
    msg = build_message("s@g.com", ["r@x.com"], entries, "s")
    plain = msg.get_body(preferencelist=("plain",))
    assert plain is not None
    assert len(plain.get_content()) > 0


# ---------------------------------------------------------------------------
# send_photos
# ---------------------------------------------------------------------------


def test_send_photos__calls_smtp_ssl_and_sends(env_vars, fake_photo, mocker):
    mock_smtp_instance = MagicMock()
    mock_smtp_cls = mocker.patch("smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    entries = [PhotoEntry(path=fake_photo, date="2019-01-01")]
    send_photos(entries, subject="Test")

    mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 465)
    mock_smtp_instance.login.assert_called_once_with("sender@gmail.com", "app-password-1234")
    mock_smtp_instance.send_message.assert_called_once()


def test_send_photos__exits_on_auth_error(env_vars, fake_photo, mocker):
    mock_smtp_cls = mocker.patch("smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = MagicMock(
        side_effect=smtplib.SMTPAuthenticationError(535, b"Bad credentials")
    )
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        send_photos([PhotoEntry(path=fake_photo)], subject="t")
    assert exc_info.value.code == 1


def test_send_photos__exits_on_smtp_exception(env_vars, fake_photo, mocker):
    mock_smtp_cls = mocker.patch("smtplib.SMTP_SSL")
    mock_smtp_cls.return_value.__enter__ = MagicMock(
        side_effect=smtplib.SMTPException("connection failed")
    )
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

    with pytest.raises(SystemExit) as exc_info:
        send_photos([PhotoEntry(path=fake_photo)], subject="t")
    assert exc_info.value.code == 1
