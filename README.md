# 🎓 Semester Report Card Checker

A GitHub Actions worker that checks the **WIT results portal** every 30 minutes for semester report card updates. When a new semester (Sem 4) is detected for `examId=10`, it automatically downloads the report card PDF and emails it to you.

## How It Works

1. Every 30 minutes, GitHub Actions runs `checker.py`
2. The script hits the WIT results portal with USN `2402111144` and `examId=10`
3. It parses the response to check the course field:
   - **`B.Tech. - CS, Sem 3`** → Old (no action)
   - **`B.Tech. - CS, Sem 4`** → New! Downloads PDF and sends email
4. State is tracked in `state.json` to avoid duplicate notifications

## Setup

### 1. Create a Gmail App Password

1. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
2. Sign in with `arnavp651@gmail.com`
3. Generate a new app password (select "Mail" and "Other")
4. Copy the 16-character password

### 2. Create a GitHub Repository

```bash
cd semester-checker
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/semester-checker.git
git push -u origin main
```

### 3. Add the Secret

1. Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GMAIL_APP_PASSWORD`
4. Value: The 16-character app password from step 1

### 4. Enable the Workflow

The workflow will automatically start running every 30 minutes. You can also trigger it manually:

1. Go to **Actions** tab in your GitHub repo
2. Select **Check Semester Update**
3. Click **Run workflow**

## Local Testing

```bash
# Set the app password
set GMAIL_APP_PASSWORD=your-app-password-here

# Run the checker
python checker.py
```

## Files

| File | Purpose |
|------|---------|
| `checker.py` | Main script — check, download, email |
| `state.json` | Tracks last known semester |
| `.github/workflows/check_semester.yml` | Cron job (every 30 min) |
| `requirements.txt` | Python dependencies |
