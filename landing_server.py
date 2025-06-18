from flask import Flask, request, redirect, url_for, render_template, send_file, render_template_string
import csv
import os
import json
import re
import base64
import io
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import defaultdict

app = Flask(__name__)

GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
LANDING_PAGE = "landing_page.html"
REPORT_PAGE = "report.html"
LOG_FILE = "logs/clicked_users.csv"

# Deduplication setup
recent_clicks = defaultdict(lambda: datetime.min)
DEDUPLICATION_WINDOW = timedelta(seconds=15)

# Setup Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.environ.get("GOOGLE_CREDS")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Main user clicks sheet
sheet_user = client.open_by_key(GOOGLE_SHEET_ID).sheet1
# Bot clicks sheet
sheet_bot = client.open_by_key(GOOGLE_SHEET_ID).worksheet("BotClickData")

def is_bot(request):
    user_agent = request.user_agent.string

    # Chrome version
    match = re.search(r"Chrome/(\d+)", user_agent)
    if match:
        version = int(match.group(1))
        if version < 134:
            return True

    # Sec-Ch-Ua check
    sec_ch_ua = request.headers.get("Sec-Ch-Ua", "")
    if 'Not;A Brand' in sec_ch_ua and "Google Chrome" not in sec_ch_ua:
        return True

    # Local/internal IP check
    ip = request.headers.get("Cf-Connecting-Ip", "") or request.remote_addr or ""
    if ip.startswith("127.") or ip.startswith("192.") or ip == "":
        return True

    # User-Agent keywords
    bot_keywords = ["Microsoft", "Defender", "Outlook", "bot", "scanner", "prefetch", "curl", "wget"]
    if any(bot_kw.lower() in user_agent.lower() for bot_kw in bot_keywords):
        return True

    return False

def log_user_click(uid):
    now = datetime.now()
    if now - recent_clicks[uid] < DEDUPLICATION_WINDOW:
        return  # Skip duplicate click
    recent_clicks[uid] = now

    timestamp = now.isoformat()
    row = [uid, timestamp]

    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    try:
        sheet_user.append_row(row)
    except Exception as e:
        print(f"Error writing to user sheet: {e}")

def log_bot_click(info):
    try:
        sheet_bot.append_row(info)
    except Exception as e:
        print(f"Error writing to bot sheet: {e}")

@app.route("/report")
def generate_report():
    try:
        sheet1 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet1")
        sheet3 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet3")

        clicked_emails = set(row[0].strip().lower() for row in sheet1.get_all_values()[1:])
        all_employees = set(row[0].strip().lower() for row in sheet3.get_all_values()[1:])

        clicked = clicked_emails & all_employees
        not_clicked = all_employees - clicked_emails

        total = len(all_employees)
        clicked_count = len(clicked)
        not_clicked_count = len(not_clicked)

        # Generate pie chart
        labels = ["Clicked", "Did Not Click"]
        sizes = [clicked_count, not_clicked_count]
        colors = ["red", "green"]
        
        fig, ax = plt.subplots(figsize=(4, 4), dpi=100)  # smaller size, higher resolution
        ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        
        # Remove padding and tight layout
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        
        # Save to buffer with tight bounding box
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
                
        buf.seek(0)
        image_base64 = base64.b64encode(buf.read()).decode("utf-8")
        buf.close()


        # Hazard Rating
        danger_rating = (clicked_count / total) * 100 if total > 0 else 0
        if danger_rating > 50:
            status = "🚨 HIGH RISK"
        elif danger_rating > 25:
            status = "⚠️ MEDIUM RISK"
        else:
            status = "✅ LOW RISK"

        # Just return the rendered template
        return render_template(
            "report.html",
            total=total,
            clicked_count=clicked_count,
            not_clicked_count=not_clicked_count,
            image_base64=image_base64,
            status=status
        )

    except Exception as e:
        traceback.print_exc()
        print(f"Error in /report route: {e}")
        return f"An error occurred: {e}", 500


@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    user_agent = request.user_agent.string
    headers = request.headers

    info = [
        uid,
        datetime.now().isoformat(),
        request.remote_addr or "",
        user_agent,
        headers.get("Host", ""),
        headers.get("Cf-Connecting-Ip", ""),
        headers.get("Cf-Ipcountry", ""),
        headers.get("Cf-Ray", ""),
        headers.get("Sec-Ch-Ua", ""),
        headers.get("Sec-Fetch-Site", ""),
    ]

    if is_bot(request):
        log_bot_click(info)
    else:
        log_user_click(uid)

    return redirect(url_for("landing", uid=uid))

@app.route("/landing")
def landing():
    uid = request.args.get("uid", "UNKNOWN")
    with open(LANDING_PAGE, "r") as f:
        html = f.read()
    html = html.replace("</form>", f'<input type="hidden" name="uid" value="{uid}"></form>')
    return render_template_string(html)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
