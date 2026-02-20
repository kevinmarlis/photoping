# photoping

Sends a random photo from your Mac Photos library to a recipient via email on a regular cadence.

## Setup

### 1. Grant Full Disk Access

`osxphotos` reads the Photos SQLite database directly and requires Full Disk Access:

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Add your terminal app (Terminal, iTerm2, etc.) or the Python binary you'll use

### 2. Create a virtual environment and install dependencies

`osxphotos` requires Python 3.13. Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if you haven't already, then:

```bash
uv venv --python 3.13
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Configure credentials and settings

```bash
cp .env.example .env
```

Edit `.env` with your values:

| Variable | Required | Description |
|---|---|---|
| `SENDER_EMAIL` | Yes | Your Gmail address |
| `SENDER_PASSWORD` | Yes | Gmail App Password (see below) |
| `RECIPIENT_EMAIL` | Yes | Where photos are delivered |
| `EMAIL_SUBJECT` | No | Subject line (default: "A photo for you") |
| `PERSON_NAME` | No | Filter to a specific person; leave blank for full library |
| `CADENCE` | Yes | `daily` or `weekly` |
| `SEND_HOUR` | Yes | Hour to send, 0–23 (e.g. `9` = 9 AM) |
| `SEND_WEEKDAY` | Weekly only | 0=Sunday … 6=Saturday |

**Gmail App Password:**
- Requires 2-Step Verification on your Google account
- Generate one at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
- It will look like `xxxx xxxx xxxx xxxx`

### 4. Test photo selection

```bash
python photo_selector.py --list-persons
python photo_selector.py "Alice Smith"
python photo_selector.py
```

### 5. Test the full flow (dry run)

```bash
python photoping.py --dry-run
```

### 6. Send a test email

```bash
python photoping.py
```

### 7. Install the schedule

```bash
python setup_schedule.py install
```

This installs a launchd job using the `CADENCE`, `SEND_HOUR`, and `SEND_WEEKDAY` values from `.env`. The job runs automatically in the background. Output is logged to `photoping.log` in the project directory.

```bash
python setup_schedule.py status
python setup_schedule.py uninstall
```

## Running tests

Dev dependencies are declared in `pyproject.toml` under `[dependency-groups] dev`. Install them and run:

```bash
uv pip install --group dev
.venv/bin/pytest -v
```

## Project Structure

```
photoping/
├── photoping.py        # Main runner — selects a photo and sends it
├── photo_selector.py   # Queries the Photos library and picks a random photo
├── email_sender.py     # Sends a photo via Gmail SMTP
├── setup_schedule.py   # Installs/uninstalls the launchd background job
├── tests/              # Test suite (68 tests, no Photos access required)
├── pyproject.toml      # Project metadata, dev dependencies, and tool config
├── requirements.txt    # Runtime dependencies
├── .env.example        # Template for credentials and settings
├── .env                # Your credentials (not committed to git)
├── photoping.log       # Log output from scheduled runs (auto-created)
└── README.md
```

## Notes

- **Python version**: `osxphotos` requires Python 3.13. Use `uv venv --python 3.13` to get it automatically.
- **iCloud Optimize Storage**: If you have "Optimize Mac Storage" enabled, some photos may not be stored locally. The selector filters these out automatically.
- **Person names**: Names are matched case-insensitively. Use `--list-persons` to see the exact names in your library.
- **Photo cache**: The first run builds a local cache (`.photos_cache.pkl`) so subsequent runs are fast. The cache auto-refreshes when your Photos library changes. Force a rebuild with:
  ```bash
  python photo_selector.py --refresh-cache
  ```
- **Logs**: When running on a schedule, all output goes to `photoping.log`. Tail it to monitor:
  ```bash
  tail -f photoping.log
  ```
