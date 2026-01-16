from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file
import openpyxl
from io import BytesIO
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import mysql.connector
import smtplib
import random
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pathlib import Path

# Load credential.env from same directory
env_path = Path(__file__).resolve().parent / "credential.env"
load_dotenv(dotenv_path=env_path)
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# ---------------- EMAIL CONFIG ----------------


# ---------------- DATABASE CONNECTION ----------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="Netra"
    )

# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/landing")
def landing():
    return render_template("landing.html")
# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return render_template("register.html", error="Email already registered")

        # Determine status: Admin -> approved (or pending if strict), Officer -> pending
        status = 'pending' if role == 'officer' else 'approved'

        cur.execute(
            "INSERT INTO users (name, email, password, role, status) VALUES (%s,%s,%s,%s,%s)",
            (name, email, password, role, status)
        )
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user:
            return render_template("login.html", error="Invalid email or password")

        # Check Approval Status
        if user.get("status") == "pending":
             return render_template("login.html", error="Account pending approval. Please wait for admin verification.")
        elif user.get("status") == "rejected":
             return render_template("login.html", error="Account registration rejected. Contact admin.")
        elif user.get("status") == "blocked":
             return render_template("login.html", error="Your account has been blocked due to suspicious activity.")

        # Store session
        session["user"] = {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "status": user["status"]
        }

        # Role-based redirect
        if user["role"] == "admin":
            return redirect(url_for("dashboard_admin"))
        else:
            return redirect(url_for("dashboard_officer"))

    return render_template("login.html",client_id=GOOGLE_CLIENT_ID)


# ---------------- GOOGLE LOGIN ----------------
# ---------------- GOOGLE LOGIN ----------------
@app.route("/auth/google/callback", methods=["POST"])
def google_callback():
    data = request.get_json()
    token = data.get("token")

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            grequests.Request(),
            GOOGLE_CLIENT_ID
        )

        user = {
            "google_id": idinfo["sub"],
            "name": idinfo["name"],
            "email": idinfo["email"],
            "role": "officer"
        }

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            INSERT INTO users (google_id, name, email, role, status)
            VALUES (%s,%s,%s,%s, 'pending')
            ON DUPLICATE KEY UPDATE name=%s
        """, (
            user["google_id"],
            user["name"],
            user["email"],
            user["role"],
            user["name"]
        ))
        conn.commit()

        # Fetch full user details (ID and Status)
        cur.execute("SELECT * FROM users WHERE email=%s", (user["email"],))
        db_user = cur.fetchone()
        cur.close()
        conn.close()

        if not db_user:
            return jsonify({"success": False, "error": "User creation failed"}), 500

        # Status Check
        if db_user["status"] == "pending":
            return jsonify({"success": False, "error": "Account pending approval. Please wait for admin verification."}), 403
        elif db_user["status"] == "rejected":
             return jsonify({"success": False, "error": "Account registration rejected. Contact admin."}), 403
        elif db_user["status"] == "blocked":
             return jsonify({"success": False, "error": "Your account has been blocked due to suspicious activity."}), 403

        # Update session with DB user data (includes id)
        session["user"] = db_user

        return jsonify({
            "success": True,
            "redirect_url": "/dashboard_officer"
        })

    except Exception as e:
        print("Google Login Error:", e)
        return jsonify({
            "success": False,
            "error": "Google authentication failed"
        }), 401


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- FORGOT PASSWORD ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip()

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return render_template("forgot_password.html", error="Email not registered")

        otp = str(random.randint(100000, 999999))
        expiry = datetime.now() + timedelta(minutes=5)

        cur.execute(
            "UPDATE users SET reset_otp=%s, otp_expiry=%s WHERE email=%s",
            (otp, expiry, email)
        )
        conn.commit()
        cur.close()
        conn.close()

        send_otp_email(email, otp)
        session["reset_email"] = email
        session.pop("otp_verified", None) # Clear any previous verification

        return redirect(url_for("verify_otp"))

    return render_template("forgot_password.html")

# ---------------- VERIFY OTP ----------------
@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if "reset_email" not in session:
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        entered_otp = request.form["otp"]
        email = session["reset_email"]

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT reset_otp, otp_expiry FROM users WHERE email=%s",
            (email,)
        )
        user = cur.fetchone()

        if not user or user["reset_otp"] != entered_otp:
            cur.close()
            conn.close()
            return render_template("verify_otp.html", error="Invalid OTP")

        if datetime.now() > user["otp_expiry"]:
            cur.close()
            conn.close()
            return render_template("verify_otp.html", error="OTP expired")

        cur.close()
        conn.close()
        
        # Mark session as verified
        session["otp_verified"] = True
        return redirect(url_for("reset_password"))

    return render_template("verify_otp.html")

# ---------------- RESEND OTP ----------------
@app.route("/resend-otp")
def resend_otp():
    if "reset_email" not in session:
        return redirect(url_for("forgot_password"))

    email = session["reset_email"]
    otp = str(random.randint(100000, 999999))
    expiry = datetime.now() + timedelta(minutes=5)

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET reset_otp=%s, otp_expiry=%s WHERE email=%s",
            (otp, expiry, email)
        )
        conn.commit()
        cur.close()
        conn.close()

        send_otp_email(email, otp)
        return redirect(url_for("verify_otp")) # Ideally show a flash message here but keeping it simple
    except Exception as e:
        print(f"Error resending OTP: {e}")
        return redirect(url_for("verify_otp", error="Failed to resend OTP"))

# ---------------- RESET PASSWORD ----------------
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_email" not in session or not session.get("otp_verified"):
        return redirect(url_for("verify_otp"))

    if request.method == "POST":
        pwd = request.form["password"]
        cpwd = request.form["confirm_password"]

        if pwd != cpwd:
            return render_template("reset_password.html", error="Passwords do not match")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET password=%s, reset_otp=NULL, otp_expiry=NULL WHERE email=%s",
            (pwd, session["reset_email"])
        )
        conn.commit()
        cur.close()
        conn.close()

        session.clear()
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ---------------- SEND OTP EMAIL ----------------
def send_otp_email(to_email, otp):
    msg = MIMEText(f"Your NETRA password reset OTP is: {otp}")
    msg["Subject"] = "NETRA Password Reset OTP"
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SMTP_EMAIL, SMTP_PASSWORD)
    server.send_message(msg)
    server.quit()
# ---------------- DASHBOARDS ----------------
@app.route("/dashboard_admin")
def dashboard_admin():
    if "user" not in session or session["user"]["role"] != "admin":
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Fetch pending users
    cur.execute("SELECT * FROM users WHERE status='pending'")
    pending_users = cur.fetchall()

    # Fetch active users (approved) for management
    cur.execute("SELECT * FROM users WHERE status='approved' AND role!='admin'")
    active_users = cur.fetchall()

    # Fetch blocked users
    cur.execute("SELECT * FROM users WHERE status='blocked'")
    blocked_users = cur.fetchall()

    # Fetch messages (Broadcasts OR sent by admin OR received by admin)
    cur.execute("""
        SELECT m.*, s.name as sender_name, r.name as receiver_name 
        FROM messages m 
        LEFT JOIN users s ON m.sender_id = s.id 
        LEFT JOIN users r ON m.receiver_id = r.id 
        ORDER BY m.timestamp DESC LIMIT 50
    """)
    messages = cur.fetchall()

    # Fetch active alerts
    cur.execute("SELECT * FROM alerts WHERE status != 'Resolved' ORDER BY created_at DESC")
    active_alerts = cur.fetchall()

    # Fetch resolved alerts (history)
    cur.execute("SELECT * FROM alerts WHERE status = 'Resolved' ORDER BY created_at DESC LIMIT 50")
    resolved_alerts = cur.fetchall()

    # --- DASHBOARD STATS ---
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='officer'")
    total_officers = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM alerts")
    total_cases = cur.fetchone()['cnt']
    
    pending_count = len(pending_users)
    resolved_count = len(resolved_alerts) # Approximation based on fetched limit, better to count properly if large
    
    cur.execute("SELECT COUNT(*) as cnt FROM alerts WHERE status='Resolved'")
    resolved_count_total = cur.fetchone()['cnt']

    # --- RECENT ACTIVITY ---
    # Merge Users Created & Alerts Created
    # We need a unified list: {type, text, time}
    activity_feed = []
    
    # Latest 10 users
    cur.execute("SELECT name, created_at, role FROM users ORDER BY created_at DESC LIMIT 5")
    recent_users = cur.fetchall()
    for u in recent_users:
        activity_feed.append({
            'type': 'user',
            'text': f"New {u['role']} registered: {u['name']}",
            'time': u['created_at']
        })
        
    # Latest 10 alerts
    cur.execute("SELECT message, created_at, severity FROM alerts ORDER BY created_at DESC LIMIT 5")
    recent_alerts = cur.fetchall()
    for a in recent_alerts:
        activity_feed.append({
            'type': 'alert',
            'text': f"Alert: {a['message']} ({a['severity']})",
            'time': a['created_at']
        })
        
    # Sort by time desc
    activity_feed.sort(key=lambda x: x['time'], reverse=True)
    activity_feed = activity_feed[:10]

    cur.close()
    conn.close()

    return render_template("dashboard_admin.html", 
                           pending_users=pending_users, 
                           active_users=active_users, 
                           blocked_users=blocked_users, 
                           messages=messages, 
                           active_alerts=active_alerts, 
                           resolved_alerts=resolved_alerts,
                           stats={
                               'users': total_users,
                               'officers': total_officers,
                               'cases': total_cases,
                               'pending': pending_count,
                               'resolved': resolved_count_total
                           },
                           activity_feed=activity_feed)

@app.route("/dashboard_officer")
def dashboard_officer():
    if "user" not in session or session["user"]["role"] != "officer":
        return redirect(url_for("login"))
    
    user_id = session["user"]["id"]
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    # Fetch alerts for this officer
    cur.execute("SELECT * FROM alerts WHERE assigned_officer_id=%s OR assigned_officer_id IS NULL", (user_id,))
    alerts = cur.fetchall()

    # Fetch messages (Broadcasts OR sent by this officer OR received by this officer)
    cur.execute("""
        SELECT m.*, s.name as sender_name 
        FROM messages m 
        LEFT JOIN users s ON m.sender_id = s.id 
        WHERE m.receiver_id = %s OR m.receiver_id IS NULL OR m.sender_id = %s
        ORDER BY m.timestamp DESC LIMIT 50
    """, (user_id, user_id))
    messages = cur.fetchall()

    # Fetch Recipients (Admin + All Approved Officers), excluding self
    cur.execute("SELECT id, name, role FROM users WHERE status='approved' AND id != %s ORDER BY role, name", (user_id,))
    recipients = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("dashboard_officer.html", alerts=alerts, messages=messages, recipients=recipients)

@app.route("/api/send_message", methods=["POST"])
def send_message():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    sender_id = session["user"]["id"]
    receiver_id = data.get("receiver_id") # Null for broadcast
    content = data.get("content")

    if not content:
        return jsonify({"success": False, "error": "Message content required"}), 400

    # If receiver_id is "all" or empty/null properly handling it as None for DB
    if receiver_id == "all" or receiver_id == "":
        receiver_id = None
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, %s, %s)",
        (sender_id, receiver_id, content)
    )
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"success": True})

@app.route("/api/update_alert_status", methods=["POST"])
def update_alert_status():
    if "user" not in session or session["user"]["role"] not in ["officer", "admin"]:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    data = request.get_json()
    alert_id = data.get("id")
    new_status = data.get("status")
    
    if not alert_id or not new_status:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE alerts SET status=%s WHERE id=%s", (new_status, alert_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/heatmap_data")
def heatmap_data():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    # Mock data generation centered around New Delhi (28.6139, 77.2090)
    # in a real scenario, this would come from the database 'alerts' table columns lat/lng
    heatmap_points = []
    
    # Base coords
    base_lat = 28.6139
    base_lng = 77.2090
    
    # Generate 50 random points with higher intensity for visibility
    for _ in range(50):
        # Random offset within ~3km (tighter cluster)
        lat_offset = (random.random() - 0.5) * 0.04
        lng_offset = (random.random() - 0.5) * 0.04
        intensity = random.uniform(0.5, 1.0) # Higher minimum intensity
        
        heatmap_points.append([base_lat + lat_offset, base_lng + lng_offset, intensity])
        
    return jsonify(heatmap_points)

# ---------------- EXPORT REPORTS ----------------
@app.route("/export_reports")
def export_reports():
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("""
        SELECT id, created_at, source, message, status, severity
        FROM alerts
        ORDER BY created_at DESC
    """)
    alerts = cur.fetchall()
    cur.close()
    conn.close()
    
    # Create Excel
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reports"
    
    # Headers
    headers = ["ID", "Timestamp", "Source", "Message", "Status", "Severity"]
    ws.append(headers)
    
    # Data
    for alert in alerts:
        ws.append([
            alert["id"],
            alert["created_at"].strftime("%Y-%m-%d %H:%M:%S") if alert["created_at"] else "",
            alert["source"],
            alert["message"],
            alert["status"],
            alert["severity"]
        ])
        
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'netra_reports_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    )

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    user_id = session["user"]["id"]
    new_name = data.get("name")
    
    # We could allow updating other fields, but let's start with name
    if not new_name:
        return jsonify({"success": False, "error": "Name is required"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET name=%s WHERE id=%s", (new_name, user_id))
        conn.commit()
        cur.close()
        conn.close()
        
        # Update session
        session["user"]["name"] = new_name
        session.modified = True
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/update_user_status", methods=["POST"])
def update_user_status():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    user_id = data.get("id")
    status = data.get("status")
    
    if not user_id or status not in ['approved', 'rejected', 'blocked']:
        return jsonify({"success": False, "error": "Invalid data"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE users SET status=%s WHERE id=%s", (status, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ---------------- CHATBOT ----------------
# ---------------- CHATBOT ----------------
from deep_translator import GoogleTranslator

@app.route("/api/chatbot", methods=["POST"])
def chatbot_api():
    if "user" not in session:
        return jsonify({"response": "I can only speak to authorized personnel. Please login."}), 401

    data = request.get_json()
    raw_msg = data.get("message", "").strip()
    target_lang = data.get("lang", "en") # Default to English

    # 1. Translate Input to English if needed
    msg_en = raw_msg.lower()
    if target_lang != 'en':
        try:
            msg_en = GoogleTranslator(source='auto', target='en').translate(raw_msg).lower()
        except Exception as e:
            print(f"Translation Error (Input): {e}")
            # Fallback to raw message if translation fails
            msg_en = raw_msg.lower()

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    response_en = "I didn't understand that command."
    
    # Process logic using English text (msg_en)
    if "status" in msg_en or "report" in msg_en:
        cur.execute("SELECT COUNT(*) as cnt FROM alerts WHERE status!='Resolved'")
        pending = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE status='approved'")
        officers = cur.fetchone()['cnt']
        
        severity = "Normal" if pending == 0 else "High Alert" if pending > 5 else "Elevated"
        response_en = f"System Status: {severity}. {pending} active alerts. {officers} officers registered."

    elif "alert" in msg_en:
        cur.execute("SELECT severity, message FROM alerts WHERE status!='Resolved' ORDER BY created_at DESC LIMIT 3")
        alerts = cur.fetchall()
        if not alerts:
             response_en = "No active alerts at this time."
        else:
             lines = [f"[{a['severity']}] {a['message']}" for a in alerts]
             response_en = "Recent Alerts: " + "; ".join(lines)
    
    elif "officer" in msg_en:
        cur.execute("SELECT name FROM users WHERE status='approved' LIMIT 5")
        users = cur.fetchall()
        names = ", ".join([u['name'] for u in users])
        response_en = f"Active Officers: {names}..."

    elif "message" in msg_en or "contact" in msg_en or "admin" in msg_en:
        response_en = "To contact the Admin or other officers, please use the 'Messages' section in your dashboard sidebar."

    elif "hello" in msg_en or "hi" in msg_en:
        response_en = f"Hello {session['user']['name']}. How can I assist you with security operations?"

    elif "help" in msg_en:
        response_en = "Commands: 'status', 'alerts', 'report', 'officers'"
    
    else:
        response_en = "I didn't quite catch that, Officer. Try asking for 'status' or 'alerts'."
    
    cur.close()
    conn.close()

    # 2. Translate Output to Target Language if needed
    final_response = response_en
    if target_lang != 'en':
        try:
            final_response = GoogleTranslator(source='en', target=target_lang).translate(response_en)
        except Exception as e:
            print(f"Translation Error (Output): {e}")
            # Fallback to English response
            final_response = response_en

    return jsonify({"response": final_response})


# ---------------- RUN APP ----------------
@app.route("/api/sync_state", methods=["GET"])
def sync_state():
    """Returns the latest message and alert IDs to check for updates."""
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Latest Message ID (global for admin, simple check; or filtered)
    # Ideally should be specific to user, but global max ID change is a good enough "poll trigger" 
    # and then the user can refresh or we just blink. Blinking on *any* new activity in system is acceptable for this prototype,
    # but let's try to be slightly more specific: Messages involved with user.
    # However, 'broadcast' messages have NULL receiver.
    user_id = session["user"]["id"]
    
    # Check max ID of messages relevant to user
    cur.execute("""
        SELECT MAX(id) as max_msg_id FROM messages 
        WHERE receiver_id = %s OR receiver_id IS NULL OR sender_id = %s
    """, (user_id, user_id))
    msg_res = cur.fetchone()
    
    # Check max ID of alerts (for officers/admins)
    # Officer: assigned alerts? Admin: all.
    # For now, simplistic global max alert ID or status change
    cur.execute("SELECT MAX(id) as max_alert_id FROM alerts")
    alert_res = cur.fetchone()
    
    cur.close()
    conn.close()

    return jsonify({
        "latest_msg_id": msg_res["max_msg_id"] or 0,
        "latest_alert_id": alert_res["max_alert_id"] or 0
    })

if __name__ == "__main__":
    app.run(debug=True)
