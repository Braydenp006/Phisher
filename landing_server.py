from flask import Flask, request, redirect, url_for, render_template_string
import csv
import os
import json
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

app = Flask(__name__)

GOOGLE_SHEET_ID = "1hALSUrXjg_qcru93HeSjlbalYr04sFMtLz6xzGR8nvU"
LANDING_PAGE = "landing_page.html"
LOG_FILE = "logs/clicked_users.csv"

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

    # Check Chrome version from User-Agent
    match = re.search(r"Chrome/(\d+)", user_agent)
    if match:
        version = int(match.group(1))
        if version < 134:
            return True

    # Check Sec-Ch-Ua header format
    sec_ch_ua = request.headers.get("Sec-Ch-Ua", "")
    if 'Not;A Brand' in sec_ch_ua or sec_ch_ua.count('"') < 4:
        return True

    # Suspicious Sec-Fetch-Site
    if request.headers.get("Sec-Fetch-Site", "") == "none":
        return True

    # IP checks (local/internal)
    ip = request.headers.get("Cf-Connecting-Ip", "") or request.remote_addr or ""
    if ip.startswith("127.") or ip.startswith("192.") or ip == "":
        return True

    # Add any more heuristic checks here if needed

    # Basic bot keywords in UA (your original list)
    bot_keywords = ["Microsoft", "Defender", "Outlook", "bot", "scanner", "prefetch", "curl", "wget"]
    if any(bot_kw.lower() in user_agent.lower() for bot_kw in bot_keywords):
        return True

    return False

def log_user_click(uid, info):
    # Log locally
    timestamp = datetime.now().isoformat()
    row = [uid, timestamp]
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)

    # Append to user clicks sheet
    try:
        sheet_user.append_row(row)
    except Exception as e:
        print(f"Error writing to user sheet: {e}")

def log_bot_click(uid, info):
    # Append all bot click info as a row in BotClickData
    try:
        sheet_bot.append_row(info)
    except Exception as e:
        print(f"Error writing to bot sheet: {e}")

@app.route("/track")
def track():
    uid = request.args.get("uid", "UNKNOWN")
    user_agent = request.user_agent.string
    headers = request.headers

    # Collect detailed info for logging
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
        log_bot_click(uid, info)
    else:
        log_user_click(uid, info)

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
