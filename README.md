# Personal Finance Tracker

Track income and expenses locally. Use the CLI, a Streamlit dashboard, or a
desktop window (Streamlit + pywebview). Optional Gemini chat explains your
spending using a short summary of your data — not a full dump of the JSON file.

## Features

- Add / list / delete income and expense transactions
- Financial summary and category breakdown
- Stable record IDs and Decimal amounts (no float money math)
- European (`1.250,50`, `10.000`) and US (`1,250.50`, `10,000`) number formats
- Corrupt data files are backed up instead of silently wiped
- Streamlit dashboard with Pandas tables and charts
- Gemini AI assistant (API key via `.env`)
- Desktop launcher without a browser chrome

## Requirements

- Python 3.10+

## Setup

```bash
pip install -r requirements.txt
```

For development tests:

```bash
pip install -r requirements-dev.txt
```

Copy the env template and add your Gemini key locally (never commit `.env`):

```bash
copy .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.8-flash
```

Get a key from [Google AI Studio](https://aistudio.google.com/apikey).

## Usage

### Desktop window (recommended)

```bash
python desktop_app.py
```

### Windows .exe

Build a folder app (not a single-file zip of Python):

```bash
build_exe.bat
```

Output:

```text
dist\PersonalFinanceTracker\PersonalFinanceTracker.exe
```

Put `.env` next to that `.exe` (the build script copies yours if present).  
`finance_data.json` is also created next to the exe.

### Streamlit in the browser (debug)

```bash
streamlit run streamlit_app.py
```

### CLI

```bash
python personel_finance_tracker.py
```

Custom data file:

```bash
python personel_finance_tracker.py --data path/to/my_data.json
```

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

## License

MIT — see [LICENSE](LICENSE).
