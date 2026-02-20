# photoping

Sends a random photo from your Mac Photos library to a recipient via email on a regular cadence.

## Setup

### 1. Grant Full Disk Access

`osxphotos` reads the Photos SQLite database directly and requires Full Disk Access:

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Add your terminal app (Terminal, iTerm2, etc.) or the Python binary you'll use

### 2. Create a virtual environment and install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your values:

- **`SENDER_EMAIL`** — your Gmail address
- **`SENDER_PASSWORD`** — a Gmail App Password (**not** your regular password)
  - Requires 2-Step Verification enabled on your Google account
  - Generate one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
  - It will look like `xxxx xxxx xxxx xxxx`
- **`RECIPIENT_EMAIL`** — where photos should be delivered

### 4. Test photo selection

```bash
# List all named persons in your library
python photo_selector.py --list-persons

# Pick a random photo of a specific person
python photo_selector.py "Alice Smith"

# Pick a random photo from the entire library
python photo_selector.py
```

### 5. Test sending an email

```bash
# Send a specific photo
python email_sender.py /path/to/photo.jpg

# Send with a custom subject
python email_sender.py /path/to/photo.jpg --subject "Remember this?"
```

## Project Structure

```
photoping/
├── photo_selector.py   # Select a random photo from the Photos library
├── email_sender.py     # Send a photo via Gmail SMTP
├── .env.example        # Template for credentials (copy to .env)
├── .env                # Your credentials (not committed to git)
├── requirements.txt
└── README.md
```

## Notes

- **iCloud Optimize Storage**: If you have "Optimize Mac Storage" enabled, some photos may not be stored locally. The selector filters these out automatically. To include them, you'd need to download them first via the Photos app.
- **Person names**: Names are matched case-insensitively. Use `--list-persons` to see the exact names in your library.
- **Photo cache**: The first run will be slow while the Photos library is indexed. Subsequent runs load from a local cache (`.photos_cache.pkl`) and are fast. The cache auto-refreshes when your Photos library changes. Run `python photo_selector.py --refresh-cache` to force a rebuild.
