# Semester Report Card Checker 🎓

Automatically checks the WIT results portal for new semester results (Sem 3 → Sem 4) and emails report card PDFs for all configured USNs.

## How It Works

1. **Probes** the portal using a probe USN to detect if results have been updated to Sem 4
2. **Downloads** report card PDFs for all 13 configured USNs
3. **Emails** all PDFs as attachments to `arnavp651@gmail.com`
4. **Falls back** to a notification-only email if PDF downloads fail
5. **Commits** updated state back to the repo to avoid duplicate notifications

Runs every 30 minutes via GitHub Actions.

## Setup (GitHub Actions)

### 1. Add Repository Secret

Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `GMAIL_APP_PASSWORD` | Your Gmail app password |

### 2. Enable the Workflow

The workflow runs automatically on push. You can also trigger it manually from **Actions → Check Semester Update → Run workflow**.

### 3. Configure USNs

Edit the `USNS` list in `checker.py` to add or remove USNs:

```python
USNS = [
    "2402111144",  # Probe USN (also gets downloaded)
    "2402111004",
    "2402111084",
    # ... add more here
]
```

## Files

| File | Purpose |
|------|---------|
| `checker.py` | Main script — detect, download, email |
| `state.json` | Tracks last known semester (auto-committed by bot) |
| `.github/workflows/check_semester.yml` | Cron job (every 30 min) |
| `requirements.txt` | Python dependencies |

## Local Testing (Optional)

```bash
# Set the env var
set GMAIL_APP_PASSWORD=your-app-password-here

# Run
python checker.py
```
