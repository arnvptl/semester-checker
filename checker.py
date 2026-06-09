"""
Semester Report Card Update Checker
====================================
Checks if examId=10 on the WIT results portal has been updated
from Sem 3 → Sem 4 for B.Tech. - CS.  When a new semester is
detected, downloads the report-card PDF and emails it.
"""

import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Fix encoding for Windows terminals (emojis in print statements)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
BASE_URL = "https://witresults.contineo.in:7074/index.php"
USN = "2402111144"
EXAM_ID = "10"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Referer": (
        "https://witresults.contineo.in:7074/index.php"
        "?option=com_examresult&task=getResult"
    ),
    "Origin": "https://witresults.contineo.in:7074",
}

# The semester string we already know about (old)
OLD_SEMESTER = "Sem 3"
# The semester string that means results are updated (new)
NEW_SEMESTER = "Sem 4"

RECIPIENT_EMAIL = "arnavp651@gmail.com"
SENDER_EMAIL = "lenibba1234@gmail.com"

STATE_FILE = Path(__file__).parent / "state.json"

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def load_state() -> dict:
    """Load persisted state from state.json."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_semester": f"B.Tech. - CS, {OLD_SEMESTER}", "last_checked": None, "notified": False}


def save_state(state: dict) -> None:
    """Write state back to state.json."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def fetch_semester_info(session: requests.Session) -> str | None:
    """
    POST to the results endpoint and extract the course/branch text.
    Returns the course string (e.g. 'B.Tech. - CS, Sem 4') or None on error.
    """
    payload = {
        "option": "com_examresult",
        "task": "getResultexam",
        "usn": USN,
        "examId": EXAM_ID,
    }

    try:
        resp = session.post(BASE_URL, headers=HEADERS, data=payload, verify=False, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"❌ Request failed: {exc}")
        return None

    html = resp.text

    # If the USN is not found at all, treat as no update
    if "Oops" in html and "could not be found" in html:
        print("ℹ️  USN not found in result database for this examId.")
        return None

    soup = BeautifulSoup(html, "html.parser")
    course_tag = soup.select_one("div.stu-data2 p")
    if course_tag:
        return course_tag.get_text(strip=True)

    print("⚠️  Could not locate course/branch in the response HTML.")
    return None


def download_report_card(session: requests.Session) -> bytes | None:
    """
    Download the grade-card PDF for the configured USN + examId.
    Returns raw PDF bytes or None on failure.
    """
    payload = {
        "option": "com_report",
        "task": "getReport",
        "id": "procard",
        "usn": USN,
        "examId": EXAM_ID,
    }

    try:
        resp = session.post(BASE_URL, headers=HEADERS, data=payload, verify=False, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"❌ PDF download failed: {exc}")
        return None

    content = resp.content
    if not content.startswith(b"%PDF"):
        print("⚠️  Downloaded content is not a valid PDF.")
        return None

    print(f"✅ Downloaded valid PDF ({len(content):,} bytes)")
    return content


def send_email(pdf_bytes: bytes, semester: str) -> bool:
    """
    Send the report-card PDF as an email attachment via Gmail SMTP.
    Requires GMAIL_APP_PASSWORD environment variable.
    """
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD environment variable not set!")
        return False

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"🎓 New Semester Report Card Available — {semester}"

    body = (
        f"Hi Arnav,\n\n"
        f"Good news! The WIT results portal has been updated.\n\n"
        f"  • USN:      {USN}\n"
        f"  • Semester:  {semester}\n"
        f"  • Exam ID:   {EXAM_ID}\n\n"
        f"Your report card PDF is attached to this email.\n\n"
        f"— Semester Checker Bot 🤖"
    )
    msg.attach(MIMEText(body, "plain"))

    # Attach the PDF
    pdf_part = MIMEBase("application", "pdf")
    pdf_part.set_payload(pdf_bytes)
    encoders.encode_base64(pdf_part)
    pdf_part.add_header(
        "Content-Disposition",
        f'attachment; filename="{USN}_report_card.pdf"',
    )
    msg.attach(pdf_part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(SENDER_EMAIL, app_password)
            server.send_message(msg)
        print(f"📧 Email sent to {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPException as exc:
        print(f"❌ Failed to send email: {exc}")
        return False


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────


def main() -> None:
    print("=" * 50)
    print("  Semester Report Card Checker")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)

    state = load_state()
    print(f"📋 Last known semester: {state['last_semester']}")
    print(f"📋 Already notified:    {state['notified']}")

    session = requests.Session()

    # Step 1: Fetch current semester info
    current_semester = fetch_semester_info(session)
    if current_semester is None:
        print("\n⏭️  Could not determine current semester. Will retry next run.")
        state["last_checked"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    print(f"\n🔍 Current semester on portal: {current_semester}")

    # Step 2: Check if it's new
    is_new = NEW_SEMESTER in current_semester and current_semester != state["last_semester"]

    if not is_new:
        print("ℹ️  No update detected (still the old semester or already notified).")
        state["last_checked"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    print(f"🆕 NEW SEMESTER DETECTED: {current_semester}")

    # Step 3: Download the report card
    pdf_bytes = download_report_card(session)
    if pdf_bytes is None:
        print("⚠️  Could not download report card. Will retry next run.")
        state["last_checked"] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    # Step 4: Email the report card
    email_sent = send_email(pdf_bytes, current_semester)

    # Step 5: Update state
    state["last_semester"] = current_semester
    state["last_checked"] = datetime.now(timezone.utc).isoformat()
    state["notified"] = email_sent
    save_state(state)

    if email_sent:
        print("\n🎉 All done! Report card downloaded and emailed successfully.")
    else:
        print("\n⚠️  Report card downloaded but email failed. Check GMAIL_APP_PASSWORD.")
        sys.exit(1)


if __name__ == "__main__":
    main()
