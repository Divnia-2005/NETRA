from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import mysql.connector
import smtplib
import random
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# ---------------- EMAIL CONFIG ----------------
SMTP_EMAIL = "diviniamarioantony2028@mca.ajce.in"
SMTP_PASSWORD = "jzkk gued ilto yvcj"

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
app.secret_key = "netra_secret_key_123"

GOOGLE_CLIENT_ID = "161607308272-lt5t46on0fr93kmdsa0kdpma3jr5457m.apps.googleusercontent.com"

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

        cur.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s)",
            (name, email, password, role)
        )
        conn.commit()
        cur.close()
        conn.close()

        return redirect(url_for("login"))

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login")
def login():
    return render_template("login.html", client_id=GOOGLE_CLIENT_ID)

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
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (google_id, name, email, role)
            VALUES (%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE name=%s
        """, (
            user["google_id"],
            user["name"],
            user["email"],
            user["role"],
            user["name"]
        ))
        conn.commit()
        cur.close()
        conn.close()

        session["user"] = user

        return jsonify({"success": True, "redirect_url": "/dashboard"})

    except Exception as e:
        print("Google Login Error:", e)
        return jsonify({"success": False}), 401

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", user=session["user"])

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
        return redirect(url_for("reset_password"))

    return render_template("verify_otp.html")

# ---------------- RESET PASSWORD ----------------
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    if "reset_email" not in session:
        return redirect(url_for("forgot_password"))

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

# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
