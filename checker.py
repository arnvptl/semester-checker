"""
Semester Report Card Update Checker
====================================
Checks if examId=10 on the WIT results portal has been updated
from Sem 3 → Sem 4 for B.Tech. - CS.  When a new semester is
detected, downloads report-card PDFs for all configured USNs
and emails them.

Designed to run as a GitHub Actions cron job every 30 minutes.
GMAIL_APP_PASSWORD must be set as a repository secret.
"""

import json
import os
import time
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
PROBE_USN = "2402111144"  # USN used to detect semester changes
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

# All USNs to download report cards for when a new semester is detected
USNS = [
    "2402111144",  # Probe USN (also gets downloaded)
    "2402111004",
    "2402111084",
    "2402111151",
    "2502112015",
    "2502112016",
    "2502112003",
    "2402111135",
    "2406111010",
    "2402111072",
    "2502112005",
    "2402111024",
    "2402111007",
]

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
        "usn": PROBE_USN,
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



def download_report_card(session: requests.Session, usn: str) -> bytes | None:
    """
    Download the grade-card PDF for a given USN + examId.
    Returns raw PDF bytes or None on failure.
    """
    payload = {
        "option": "com_report",
        "task": "getReport",
        "id": "procard",
        "usn": usn,
        "examId": EXAM_ID,
    }

    try:
        resp = session.post(BASE_URL, headers=HEADERS, data=payload, verify=False, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ❌ PDF download failed for {usn}: {exc}")
        return None

    content = resp.content
    if not content.startswith(b"%PDF"):
        print(f"  ⚠️  {usn}: Response is not a valid PDF.")
        return None

    print(f"  ✅ {usn}: Downloaded ({len(content):,} bytes)")
    return content


def send_email(pdfs: dict[str, bytes], semester: str) -> bool:
    """
    Send report-card PDFs as email attachments via Gmail SMTP.
    pdfs: dict mapping USN -> PDF bytes.
    Requires GMAIL_APP_PASSWORD environment variable.
    """
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD environment variable not set!")
        return False

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"🎓 New Semester Report Cards Available — {semester} ({len(pdfs)} students)"

    usn_list = "\n".join(f"  • {usn}" for usn in pdfs)
    body = (
        f"Hi Arnav,\n\n"
        f"Good news! The WIT results portal has been updated to {semester}.\n\n"
        f"Report cards attached for {len(pdfs)} students:\n{usn_list}\n\n"
        f"  • Exam ID: {EXAM_ID}\n\n"
        f"— Semester Checker Bot 🤖"
    )
    msg.attach(MIMEText(body, "plain"))

    # Attach all PDFs
    for usn, pdf_bytes in pdfs.items():
        pdf_part = MIMEBase("application", "pdf")
        pdf_part.set_payload(pdf_bytes)
        encoders.encode_base64(pdf_part)
        pdf_part.add_header(
            "Content-Disposition",
            f'attachment; filename="{usn}_report_card.pdf"',
        )
        msg.attach(pdf_part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(SENDER_EMAIL, app_password)
            server.send_message(msg)
        print(f"📧 Email sent to {RECIPIENT_EMAIL} with {len(pdfs)} attachments")
        return True
    except smtplib.SMTPException as exc:
        print(f"❌ Failed to send email: {exc}")
        return False


def send_notification_email(semester: str, failed_usns: list[str]) -> bool:
    """
    Fallback: Send a plain notification email (no PDFs) when downloads fail.
    """
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD environment variable not set!")
        return False

    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = f"🔔 New Results Available — {semester} (PDFs failed to download)"

    failed_list = "\n".join(f"  • {usn}" for usn in failed_usns)
    body = (
        f"Hi Arnav,\n\n"
        f"The WIT results portal has been updated to {semester}!\n\n"
        f"However, the report card PDFs could not be downloaded for:\n{failed_list}\n\n"
        f"You can check the results manually at:\n"
        f"  {BASE_URL}\n\n"
        f"— Semester Checker Bot 🤖"
    )
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(SENDER_EMAIL, app_password)
            server.send_message(msg)
        print(f"📧 Notification email sent to {RECIPIENT_EMAIL}")
        return True
    except smtplib.SMTPException as exc:
        print(f"❌ Failed to send notification email: {exc}")
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

    # Step 1: Fetch current semester info (using probe USN)
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

    # Step 3: Download report cards for all USNs
    print(f"\n📋 Downloading report cards for {len(USNS)} USNs...\n")

    downloaded: dict[str, bytes] = {}
    failed: list[str] = []

    for i, usn in enumerate(USNS, 1):
        print(f"[{i}/{len(USNS)}] {usn}")
        pdf_bytes = download_report_card(session, usn)
        if pdf_bytes:
            downloaded[usn] = pdf_bytes
        else:
            failed.append(usn)
        time.sleep(1)  # Be nice to the server

    print(f"\n📊 Results: {len(downloaded)} downloaded, {len(failed)} failed")
    if failed:
        print(f"❌ Failed USNs: {', '.join(failed)}")

    # Step 4: Email results
    if downloaded:
        email_sent = send_email(downloaded, current_semester)
    else:
        # Fallback: all PDFs failed, send a notification-only email
        print("\n⚠️  All PDF downloads failed. Sending notification email instead...")
        email_sent = send_notification_email(current_semester, failed)

    # Step 5: Update state
    state["last_semester"] = current_semester
    state["last_checked"] = datetime.now(timezone.utc).isoformat()
    state["notified"] = email_sent
    save_state(state)

    if email_sent and downloaded:
        print(f"\n🎉 All done! {len(downloaded)} report cards emailed successfully.")
    elif email_sent:
        print("\n📬 Notification email sent (no PDFs could be downloaded).")
    else:
        print("\n⚠️  Email sending failed. Check GMAIL_APP_PASSWORD.")
        sys.exit(1)


if __name__ == "__main__":
    main()
