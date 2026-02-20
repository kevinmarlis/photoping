# photoping

Sends a random photo from your Mac Photos library to a recipient via email on a regular cadence.

## Setup

### 1. Grant Full Disk Access

`osxphotos` reads the Photos SQLite database directly and requires Full Disk Access:

1. Open **System Settings → Privacy & Security → Full Disk Access**
2. Add your terminal app (Terminal, iTerm2, etc.) or the Python binary you'll use

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Test photo selection

```bash
# List all named persons in your library
python photo_selector.py --list-persons

# Pick a random photo of a specific person
python photo_selector.py "Alice Smith"

# Pick a random photo from the entire library
python photo_selector.py
```

## Project Structure

```
photoping/
├── photo_selector.py   # Select a random photo from the Photos library
├── requirements.txt
└── README.md
```

## Notes

- **iCloud Optimize Storage**: If you have "Optimize Mac Storage" enabled, some photos may not be stored locally. The selector filters these out automatically. To include them, you'd need to download them first via the Photos app.
- **Person names**: Names are matched case-insensitively. Use `--list-persons` to see the exact names in your library.
