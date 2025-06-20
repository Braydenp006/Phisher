from flask import Flask, request, redirect, url_for, render_template, send_file, render_template_string, response
from functools import wraps
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
UTH_USERNAME = os.environ.get("AUTH_USERNAME")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD")

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

def email_to_name(email):
    name_part = email.split("@")[0]
    if "." in name_part:
        first, last = name_part.split(".", 1)
        return f"{first.capitalize()} {last.capitalize()}"
    return email  # fallback for unexpected formats
    
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
def check_auth(username, password):
    return username == AUTH_USERNAME and password == AUTH_PASSWORD

def authenticate():
    return Response(
        "Authentication required", 401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'}
    )

def require_auth_route(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return func(*args, **kwargs)
    return wrapper
    
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


@app.route("/download_clicked")
def download_clicked():
    try:
        sheet1 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet1")
        sheet3 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet3")

        clicked_emails = set(row[0].strip().lower() for row in sheet1.get_all_values()[1:])
        all_employees = set(row[0].strip().lower() for row in sheet3.get_all_values()[1:])
        clicked = clicked_emails & all_employees

        # Convert emails to names
        def email_to_name(email):
            name_part = email.split("@")[0]
            if "." in name_part:
                first, last = name_part.split(".", 1)
                return f"{first.capitalize()} {last.capitalize()}"
            return email

        clicked_names = sorted(email_to_name(email) for email in clicked)

        # Write names to a CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Name"])
        for name in clicked_names:
            writer.writerow([name])

        mem = io.BytesIO()
        mem.write(output.getvalue().encode("utf-8"))
        mem.seek(0)
        output.close()

        return send_file(
            mem,
            as_attachment=True,
            download_name="clicked_users.csv",
            mimetype="text/csv"
        )
    except Exception as e:
        return f"An error occurred while generating the CSV: {e}", 500

@app.route("/report")
@require_auth_route
def generate_report():
    try:
        sheet1 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet1")
        sheet3 = client.open_by_key(GOOGLE_SHEET_ID).worksheet("Sheet3")

        clicked_emails = set(row[0].strip().lower() for row in sheet1.get_all_values()[1:])
        all_employees_data = sheet3.get_all_values()[1:]

        all_employees = set(row[0].strip().lower() for row in all_employees_data)
        email_to_dept = {row[0].strip().lower(): row[1].strip() if len(row) > 1 else "Unknown" for row in all_employees_data}

        clicked = clicked_emails & all_employees
        not_clicked = all_employees - clicked_emails
        clicked_names = sorted(email_to_name(email) for email in clicked)

        total = len(all_employees)
        clicked_count = len(clicked)
        not_clicked_count = len(not_clicked)

        # Generate pie chart
        sizes = [clicked_count, not_clicked_count]
        colors = ["#ff6b6b", "#4caf50"]
        explode = [0.05, 0.05]

        fig, ax = plt.subplots(figsize=(4, 4), dpi=100)
        ax.pie(sizes, colors=colors, explode=explode, startangle=90,
               textprops=dict(color="black", fontsize=12, weight="bold"),
               wedgeprops=dict(width=0.5))
        ax.axis("equal")
        ax.text(0, 1.2, f"{clicked_count/total: .1%} Clicked", ha="center", va="center", fontsize=14, weight="bold", color="#000000")
        ax.text(0, -1.2, f"{not_clicked_count/total: .1%} Didn't Click", ha="center", va="center", fontsize=14, weight="bold", color="#000000")

        plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches='tight', pad_inches=0.1, transparent=True)
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

        # Generate department pie charts
        department_stats = {}
        for email in all_employees:
            dept = email_to_dept.get(email, "Unknown")
            department_stats.setdefault(dept, {"clicked": 0, "total": 0})
            department_stats[dept]["total"] += 1
            if email in clicked:
                department_stats[dept]["clicked"] += 1

        department_charts = {}
        for dept, stats in department_stats.items():
            if stats["total"] == 0:
                continue
            clicked_val = stats["clicked"]
            not_clicked_val = stats["total"] - clicked_val
            fig, ax = plt.subplots(figsize=(3, 3), dpi=100)
            ax.pie([clicked_val, not_clicked_val],
                   colors=["#ff6b6b", "#4caf50"], explode=[0.05, 0.05], startangle=90,
                   autopct='%1.1f%%', textprops={'fontsize': 10, 'color': 'black'})
            ax.axis("equal")
            buf = io.BytesIO()
            plt.savefig(buf, format="png", bbox_inches='tight', transparent=True)
            buf.seek(0)
            department_charts[dept] = base64.b64encode(buf.read()).decode("utf-8")
            plt.close(fig)
        
        # Prepare clicked users with department for sorting/filtering
        clicked_users_with_dept = sorted(
            [(email_to_name(email), email_to_dept.get(email, "Unknown")) for email in clicked],
            key=lambda x: x[1]  # sort by department
        )
        
        # List of all departments
        departments = sorted(set(email_to_dept.get(email, "Unknown") for email in clicked))
        
        return render_template(
            "report.html",
            total=total,
            clicked_count=clicked_count,
            not_clicked_count=not_clicked_count,
            image_base64=image_base64,
            status=status,
            clicked_users=clicked_names,
            department_charts=department_charts,
            clicked_users_with_dept=clicked_users_with_dept,
            departments=departments
        )

    except Exception as e:
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
