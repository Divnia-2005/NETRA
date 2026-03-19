from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, Response, make_response
import time
import requests
import os
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
import cv2
import numpy as np
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
import razorpay
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
import threading
from dotenv import load_dotenv
from pathlib import Path
import re

# Load credential.env from same directory
env_path = Path(__file__).resolve().parent / "credential.env"
load_dotenv(dotenv_path=env_path, override=True) # Force reload
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# ---------------- EMAIL CONFIG ----------------


# ---------------- DATABASE CONNECTION ----------------

# ---------------- DATABASE CONNECTION ----------------
def get_db():
    conn = mysql.connector.connect(
        host=os.getenv("MYSQLHOST", "localhost"),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("MYSQLDATABASE", "Netra"),
        port=int(os.getenv("MYSQLPORT", 3306))
    )
    # Lazy Migration: Ensure event_date exists
    try:
        cur = conn.cursor()
        cur.execute("SELECT event_date FROM public_entries LIMIT 1")
        cur.fetchall()
        cur.close()
    except:
        try:
             cur = conn.cursor()
             cur.execute("ALTER TABLE public_entries ADD COLUMN event_date VARCHAR(20) DEFAULT NULL")
             conn.commit()
             cur.close()
             print("DEBUG: Added event_date column to public_entries")
        except Exception as e:
             print(f"Migration Warning: {e}")
             
    return conn


# ---------------- APP CONFIG ----------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_dev_key_123")

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
# ---------------- RAZORPAY CONFIG ----------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder") 
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "secret_placeholder")

print(f"DEBUG: Loaded Razorpay Key: {RAZORPAY_KEY_ID}") # Verify loading

razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# ---------------- MOCK DATA STORE ----------------
MOCK_PATROL_LOGS = []  # List of {user_id, name, location, notes, time}

# ---------------- ROUTES ----------------
@app.route("/")
def home():
    return render_template("landing.html")

@app.route("/landing")
def landing():
    return render_template("landing.html")

@app.route("/help")
def help_page():
    if "user" not in session:
        return redirect(url_for("login"))
    
    # Redirect to the dashboard. The user can then click Help internally.
    # This ensures and enforces the "same URL" logic requested by the user.
    if session["user"].get("role") == "admin":
        return redirect(url_for("dashboard_admin"))
    return redirect(url_for("dashboard_officer"))

# ---------------- THREAD-SAFE CAMERA SINGLETON ----------------
# Initialize HOG detector for global use
hog_detector = cv2.HOGDescriptor()
hog_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

# Global state for crowd densities
LATEST_CROWD_DATA = {i: {"name": f"CAM-0{i+1}", "density": 0} for i in range(8)}
LAST_DB_ALERT_TIME: dict = {i: 0 for i in range(8)}  # Rate limit DB writes
CROWD_THRESHOLD = 6  # Count > 5 to alert
CAM_DISPLAY_NAMES = ["GATE-MAIN", "LOBBY-SEC", "CORRIDOR-A", "EXIT-WEST",
                     "PARKING-01", "ROOF-SOUTH", "SERVER-02", "DOCK-B"]
ALARM_MUTED_UNTIL = 0    # Timestamp until which AI alarm is disabled
LAST_BUZZER_ON_TIME = 0  # Cooldown for sending network requests to ESP32
for i, name in enumerate(CAM_DISPLAY_NAMES):
    LATEST_CROWD_DATA[i]["name"] = name

SNAPSHOT_DIR = os.path.join("static", "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)


# --- Quick camera probe (runs once at startup, non-blocking) ---
def _probe_camera():
    """Disabled backend camera grab to prevent hardware lock. Web handles camera."""
    print("[NETRA] Backend Camera disabled. Using Web UI for Camera 0.")
    return None

CAMERA_INDEX = _probe_camera()  # None → demo mode, int → real camera index
ESP32_URL = "http://10.71.228.138" # Configure your IoT device IP here


# --- Animated demo frame generator (per virtual camera) ---
def _make_demo_frame(cam_index: int) -> np.ndarray:
    """Generate a live-animated branded placeholder frame for cam_index."""
    W, H = 640, 480
    frame = np.zeros((H, W, 3), dtype=np.uint8)

    hue_offsets = [10, 25, 40, 55, 70, 85, 100, 115]
    base_green = hue_offsets[cam_index % len(hue_offsets)]
    frame[:, :] = (0, base_green, 0)

    for x in range(0, W, 32):
        cv2.line(frame, (x, 0), (x, H), (0, base_green + 8, 0), 1)
    for y in range(0, H, 32):
        cv2.line(frame, (0, y), (W, y), (0, base_green + 8, 0), 1)

    scan_y = int((time.time() * 80) % H)
    cv2.line(frame, (0, scan_y), (W, scan_y), (0, 255, 100), 2)
    for off, alpha in [(1, 80), (3, 30), (6, 10)]:
        # Cast to int to resolve unary operator warnings
        for dy in [int(-off), int(off)]:
            sy = scan_y + dy
            if 0 <= sy < H:
                cv2.line(frame, (0, sy), (W, sy), (0, alpha, 30), 1)

    cam_name = CAM_DISPLAY_NAMES[cam_index] if cam_index < len(CAM_DISPLAY_NAMES) else f"CAM-{cam_index}"
    cv2.rectangle(frame, (0, 0), (W, 48), (0, 20, 0), -1)
    cv2.putText(frame, f"NETRA | {cam_name}", (14, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (19, 236, 91), 2)

    cv2.putText(frame, "DEMO MODE", (W // 2 - 90, H // 2 - 16),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 180, 60), 2)
    cv2.putText(frame, "No Camera Connected", (W // 2 - 130, H // 2 + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 200, 100), 1)

    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(frame, ts, (14, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (60, 200, 60), 1)

    if int(time.time() * 2) % 2 == 0:
        cv2.circle(frame, (W - 30, 24), 7, (0, 0, 200), -1)
        cv2.putText(frame, "REC", (W - 22, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

    return frame


class CameraStream:
    def __init__(self, cam_idx):
        self.current_index = cam_idx   # None = demo mode
        self.lock = threading.Lock()
        self.last_frame = None
        self.last_rects = []
        self.last_person_count = 0
        self.processed_frame = None
        self.is_running = True
        self.error_count = 0
        self.camera = None  # cv2.VideoCapture or None
        self._init_camera()
        self.thread = threading.Thread(target=self._update_frame, daemon=True)
        self.thread.start()

    def _init_camera(self):
        if self.current_index is None:
            return  # Demo mode — no physical camera
        cap = cv2.VideoCapture(self.current_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(self.current_index)
        self.camera = cap if cap.isOpened() else None
        if self.camera is None and cap:
            cap.release()

    def _update_frame(self):
        while self.is_running:
            # Explicit protection against NoneType attribute access
            current_cam = self.camera
            if current_cam is None or not current_cam.isOpened():
                time.sleep(0.5)
                continue

            success, frame = current_cam.read()
            if success:
                self.error_count = 0
                try:
                    small = cv2.resize(frame, (400, int(frame.shape[0] * 400 / frame.shape[1])))
                    (rects, _) = hog_detector.detectMultiScale(small, winStride=(8, 8),
                                                                padding=(8, 8), scale=1.05)
                    scale = frame.shape[1] / 400
                    scaled_rects = [(int(x * scale), int(y * scale), int(w * scale), int(h * scale))
                                    for (x, y, w, h) in rects]
                except Exception:
                    scaled_rects = []

                person_count = len(scaled_rects)
                is_alert = person_count >= 5

                global ALARM_MUTED_UNTIL, LAST_BUZZER_ON_TIME
                if not is_alert and time.time() < ALARM_MUTED_UNTIL:
                    ALARM_MUTED_UNTIL = 0

                display_frame = frame.copy()
                status_color = (19, 236, 91) if not is_alert else (0, 0, 255)
                for (x, y, w, h) in scaled_rects:
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), status_color, 2)
                    cv2.putText(display_frame, "HUMAN", (x, y - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, status_color, 1)

                with self.lock:
                    self.last_frame = frame.copy()
                    self.processed_frame = display_frame
                    self.last_rects = scaled_rects
                    self.last_person_count = person_count

                if is_alert:
                    current_time = time.time()
                    if current_time - LAST_DB_ALERT_TIME.get('global', 0) > 30:
                        try:
                            conn = get_db()
                            cur = conn.cursor()
                            alert_msg = f"CROWD ALERT: {person_count} tracked individuals detected by Netra AI."
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            snap_filename = f"crowd_alert_{timestamp}.jpg"
                            snap_path = os.path.join(SNAPSHOT_DIR, snap_filename)
                            cv2.imwrite(snap_path, frame)
                            cur.execute("""
                                INSERT INTO alerts (source, message, severity, status, created_at, snapshot_path)
                                VALUES ('Netra-AI', %s, 'Warning', 'Open', NOW(), %s)
                            """, (alert_msg, f"static/snapshots/{snap_filename}"))
                            conn.commit()
                            cur.close()
                            conn.close()
                            LAST_DB_ALERT_TIME['global'] = current_time
                        except Exception as e:
                            print(f"DEBUG: Alert Log Failed (Check MySQL): {e}")

                    # Only Trigger IoT if alert is active and not muted
                    if current_time > ALARM_MUTED_UNTIL and (current_time - LAST_BUZZER_ON_TIME > 5):
                        try:
                            requests.get(f"{ESP32_URL}/buzzer/on", timeout=1)
                            print(f"AI: Crowd Detected, Triggering ESP32 Alarm at {ESP32_URL}")
                            LAST_BUZZER_ON_TIME = current_time
                        except Exception as e:
                            print(f"DEBUG: Failed to reach ESP32 at {ESP32_URL}: {e}")
            else:
                # Real hardware error
                self.error_count += 1
                if self.error_count > 15:
                    if self.camera is not None:
                        self.camera.release()
                        self.camera = None
                    time.sleep(2)
                    self._init_camera()
                    self.error_count = 0
            time.sleep(0.01)

    def get_data(self):
        with self.lock:
            if self.processed_frame is not None:
                return self.processed_frame.copy(), self.last_rects, self.last_person_count
        return None, [], 0


# Global singleton
camera_stream = None

def get_camera_stream():
    global camera_stream
    if camera_stream is None:
        camera_stream = CameraStream(CAMERA_INDEX)
    return camera_stream


# ---------------- VIDEO FEED (LAPTOP CAMERA OR DEMO) ----------------
def gen_frames(camera_index=0):
    stream = get_camera_stream()
    while True:
        # CAMERA_INDEX is defined globally (0 or None)
        # We only want to show the REAL feed for Cam-01 (index 0)
        # All other virtual cams (1-7) should show the Demo Mode grid
        if camera_index != 0:
            frame = _make_demo_frame(camera_index)
        else:
            frame, rects, person_count = stream.get_data()
            if frame is None:
                frame = _make_demo_frame(camera_index)
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.08)  # ~12 fps demo
            continue

        # --- UI OVERLAY (CAM SPECIFIC) ---
        cam_name = CAM_DISPLAY_NAMES[camera_index] if camera_index < len(CAM_DISPLAY_NAMES) else f"CAM-{camera_index}"
        is_alert = person_count >= 5

        header_color = (17, 34, 16) if not is_alert else (16, 16, 50)
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), header_color, -1)

        status_text = "NOMINAL" if not is_alert else "!!! CROWDED !!!"
        status_color = (19, 236, 91) if not is_alert else (0, 0, 255)

        cv2.putText(frame, f"{cam_name}", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, status_text, (frame.shape[1] // 2 - 40, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
        cv2.putText(frame, f"COUNT: {person_count}", (frame.shape[1] - 130, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.04)  # ~25 fps

# ESP32 IP Configuration
ESP32_URL = "http://10.71.228.138"

@app.route("/api/iot/alert", methods=["POST"])
def iot_alert():
    data = request.get_json()
    if data:
        device_id = data.get("device_id")
        alert_type = data.get("alert_type")
        print(f"IoT Alert Received - Device: {device_id}, Type: {alert_type}")
        
        # Log to DB (optional)
        try:
            conn = get_db()
            cur = conn.cursor()
            alert_msg = f"IoT SENSOR ALERT: {alert_type} detected by {device_id}"
            cur.execute("""
                INSERT INTO alerts (source, message, severity, status, created_at)
                VALUES (%s, %s, 'High', 'Open', NOW())
            """, (device_id, alert_msg))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"DEBUG: IoT Alert Log Failed: {e}")
            
    return jsonify({"success": True, "message": "Alert processed"})

@app.route("/api/stop_buzzer", methods=["POST"])
def stop_buzzer():
    if "user" not in session:
        return jsonify({"success": False}), 401
        
    print(f"Manual stop: Sending OFF signal to {ESP32_URL}")
    
    global ALARM_MUTED_UNTIL
    # Increase mute to 5 mins so you have time to move
    ALARM_MUTED_UNTIL = time.time() + 300 
    
    try:
        # Send OFF command to ESP32
        requests.get(f"{ESP32_URL}/buzzer/off", timeout=3)
        print(f"Success: IoT Alarm at {ESP32_URL} is now OFF!")
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Failed to reach ESP32 at {ESP32_URL}: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/iot_test")
def iot_test():
    """Manual diagnostic tool to verify ESP32 connectivity."""
    try:
        start_time = time.time()
        res = requests.get(f"{ESP32_URL}/", timeout=2)
        diff = float(time.time() - start_time)
        latency = round(diff * 1000.0, 2)
        return jsonify({"success": True, "ip": ESP32_URL, "status": res.status_code, "latency_ms": latency})
    except Exception as e:
        return jsonify({"success": False, "ip": ESP32_URL, "error": str(e)})

@app.route('/video_feed/<int:index>')
def video_feed(index):
    if "user" not in session:
        return "Unauthorized", 401
    # Support up to 8 simulated cameras (0 to 7)
    if index < 0 or index > 7:
        return "Not Found", 404
    return Response(gen_frames(index), mimetype='multipart/x-mixed-replace; boundary=frame')

import base64

@app.route('/api/process_frame', methods=['POST'])
def process_frame():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or "image" not in data:
        return jsonify({"success": False, "error": "No image data"}), 400
        
    image_data = data["image"]
    
    # Strip base64 header if present
    if "base64," in image_data:
        image_data = image_data.split("base64,")[1]
        
    try:
        # Decode base64 to OpenCV image
        img_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({"success": False, "error": "Invalid image"}), 400
            
        # Run Detection
        small = cv2.resize(frame, (400, int(frame.shape[0] * 400 / frame.shape[1])))
        (rects, _) = hog_detector.detectMultiScale(small, winStride=(8, 8), padding=(8, 8), scale=1.05)
        
        scale = frame.shape[1] / 400
        scaled_rects = [{"x": int(x * scale), "y": int(y * scale), "w": int(w * scale), "h": int(h * scale)} for (x, y, w, h) in rects]
        
        person_count = len(scaled_rects)
        is_alert = person_count >= 5
        
        global ALARM_MUTED_UNTIL, LAST_BUZZER_ON_TIME
        if not is_alert and time.time() < ALARM_MUTED_UNTIL:
            ALARM_MUTED_UNTIL = 0
            
        # Alert Logic
        if is_alert:
            current_time = time.time()
            if current_time - LAST_DB_ALERT_TIME.get('global', 0) > 30:
                try:
                    conn = get_db()
                    cur = conn.cursor()
                    alert_msg = f"CROWD ALERT: {person_count} tracked individuals detected by Netra AI via Web."
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    snap_filename = f"crowd_alert_web_{timestamp}.jpg"
                    snap_path = os.path.join(SNAPSHOT_DIR, snap_filename)
                    cv2.imwrite(snap_path, frame)
                    cur.execute("""
                        INSERT INTO alerts (source, message, severity, status, created_at, snapshot_path)
                        VALUES ('Netra-AI-Web', %s, 'Warning', 'Open', NOW(), %s)
                    """, (alert_msg, f"static/snapshots/{snap_filename}"))
                    conn.commit()
                    cur.close()
                    conn.close()
                    LAST_DB_ALERT_TIME['global'] = current_time
                except Exception as e:
                    print(f"DEBUG: Web Alert Log Failed: {e}")

            if current_time > ALARM_MUTED_UNTIL and (current_time - LAST_BUZZER_ON_TIME > 5):
                try:
                    requests.get(f"{ESP32_URL}/buzzer/on", timeout=1)
                    print(f"WEB AI: Crowd Detected, Triggering ESP32 Alarm at {ESP32_URL}")
                    LAST_BUZZER_ON_TIME = current_time
                except Exception as e:
                    print(f"DEBUG: Failed to reach ESP32 at {ESP32_URL}: {e}")
                    
        return jsonify({
            "success": True, 
            "person_count": person_count,
            "is_alert": is_alert,
            "rects": scaled_rects
        })
    except Exception as e:
        print(f"Error processing web frame: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form.get("confirm_password")
        role = request.form["role"]

        # Backend Validations
        if not name or not email or not password or not role:
             return render_template("register.html", error="All fields are required")

        # Name Validation (Letters and Spaces only)
        if not re.match(r"^[a-zA-Z\s]+$", name) or not name.strip():
             return render_template("register.html", error="Name must contain only letters and spaces")

        # Email Validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
             return render_template("register.html", error="Invalid email format")

        # Password Complexity
        if len(password) < 8 or not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password) or not re.search(r"\d", password) or not re.search(r"[@$!%*?&]", password):
             return render_template("register.html", error="Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character")

        # Password Match
        if password != confirm_password:
             return render_template("register.html", error="Passwords do not match")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return render_template("register.html", error="Email already registered")

        # Determine status: Admin -> approved (or pending if strict), Officer -> pending
        status = 'pending' if role == 'officer' else 'approved'

        hashed_password = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (name, email, password, role, status) VALUES (%s,%s,%s,%s,%s)",
            (name, email, hashed_password, role, status)
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

        if not email or not password:
             return render_template("login.html", error="Email and password are required")
        
        email = email.strip()

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        # Fetch user first, then verify password
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        
        # Verify Password (Hash or Lazy Migration)
        valid_password = False
        if user and user.get('password'):
            if check_password_hash(user['password'], password):
                valid_password = True
            elif user['password'] == password:
                # Lazy Migration: It was plain text, update to hash now
                new_hash = generate_password_hash(password)
                # Need a fresh cursor/connection to update if previous fetch locked? No, usually fine.
                # But let's be safe and just run update.
                update_cur = conn.cursor()
                update_cur.execute("UPDATE users SET password=%s WHERE id=%s", (new_hash, user['id']))
                conn.commit()
                update_cur.close()
                valid_password = True
                print(f"Migrated password for user {user['email']} to hash.")
        
        cur.close()
        conn.close()

        if not user or not valid_password:

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
    # print(f"DEBUG: Using Google Client ID: {GOOGLE_CLIENT_ID}")

    if not GOOGLE_CLIENT_ID:
        print("❌ Error: GOOGLE_CLIENT_ID is None in app.py!")
        return jsonify({"success": False, "error": "Server Configuration Error: GOOGLE_CLIENT_ID not found."}), 500

    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            grequests.Request(),
            GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=60
        )

        name = idinfo["name"]
        
        # Validate Name from Google (Relaxed to allow . and -)
        if not re.match(r"^[a-zA-Z\s.-]+$", name) or not name.strip():
             return jsonify({"success": False, "error": "Google Account Name invalid. Name must contain only letters, spaces, dots, or hyphens."}), 400

        user = {
            "google_id": idinfo["sub"],
            "name": name,
            "email": idinfo["email"],
            "role": "officer"
        }

        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            INSERT INTO users (google_id, name, email, role, status)
            VALUES (%s,%s,%s,%s, 'pending')
            ON DUPLICATE KEY UPDATE 
                google_id = COALESCE(google_id, VALUES(google_id)),
                name = VALUES(name)
        """, (
            user["google_id"],
            user["name"],
            user["email"],
            user["role"]
        ))
        conn.commit()
        print(f"DEBUG: Database record for {user['email']} ensured.")

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

        # Update session with only serializable DB user data (id, name, email, role, status)
        session["user"] = {
            "id": db_user["id"],
            "name": db_user["name"],
            "email": db_user["email"],
            "role": db_user["role"],
            "status": db_user["status"]
        }

        return jsonify({
            "success": True,
            "redirect_url": "/dashboard_officer"
        })

    except Exception as e:
        print("❌ Google Login Error:", str(e))
        return jsonify({
            "success": False,
            "error": f"Google authentication failed: {str(e)}"
        }), 401


# ---------------- LOGOUT ----------------
@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    response = make_response(redirect(url_for("landing")))
    # Kill the session cookie explicitly
    response.delete_cookie("session")
    # Ensure this redirect is never cached
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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

        # 1. Check for empty or whitespace
        if not pwd or not pwd.strip():
             return render_template("reset_password.html", error="Password cannot be empty or spaces")

        # 2. Check Match
        if pwd != cpwd:
            return render_template("reset_password.html", error="Passwords do not match")

        # 3. Check Complexity
        if len(pwd) < 8 or not re.search(r"[a-z]", pwd) or not re.search(r"[A-Z]", pwd) or not re.search(r"\d", pwd) or not re.search(r"[@$!%*?&]", pwd):
             return render_template("reset_password.html", error="Password must be 8+ chars, with upper, lower, number, and special char")

        email = session["reset_email"]
        conn = get_db()
        cur = conn.cursor(dictionary=True) # Use dictionary cursor for easy access
        
        # 4. Fetch old password to check reuse (assuming plain text for now as per context, usually hashed)
        # 4. Fetch old password to check reuse
        cur.execute("SELECT password FROM users WHERE email=%s", (email,))
        user_row = cur.fetchone()
        
        # Check against Hash OR Plain text
        if user_row:
             stored_pw = user_row['password']
             if check_password_hash(stored_pw, pwd) or stored_pw == pwd:
                 cur.close()
                 conn.close()
                 return render_template("reset_password.html", error="Cannot reuse your old password")

        # Update Password with Hash
        hashed_pwd = generate_password_hash(pwd)
        cur.execute(
            "UPDATE users SET password=%s, reset_otp=NULL, otp_expiry=NULL WHERE email=%s",
            (hashed_pwd, email)
        )
        conn.commit()
        cur.close()
        conn.close()

        session.clear()
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ---------------- SEND OTP EMAIL ----------------
def send_otp_email(to_email, otp):
    # The original code had a syntax error and was trying to use `body` which was not defined.
    # It also had `r.send_message(msg)` which was out of place.
    # The instruction also mentioned fixing email string casting on lines 790-795,
    # which implies using os.getenv for email credentials.
    # Reconstructing based on common Flask/SMTP patterns and the provided snippet.
    body = f"Your NETRA password reset OTP is: {otp}"
    msg = MIMEText(body)
    msg['Subject'] = 'Password Reset OTP - NETRA Security'
    msg['From'] = str(os.getenv("EMAIL_USER")) # Ensure string casting
    msg['To'] = str(to_email) # Ensure string casting for recipient

    try:
        # Use SMTP_SSL for port 465, or SMTP + starttls for port 587
        # The snippet implies SMTP_SSL on 465
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(str(os.getenv("EMAIL_USER")), str(os.getenv("EMAIL_PASS"))) # Ensure string casting
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        # Optionally re-raise or handle more gracefully

@app.route("/api/verify-ticket", methods=["POST"])
def verify_ticket():
    if "user" not in session or session["user"]["role"] != "officer":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    data = request.get_json()
    ticket_id = data.get("ticket_id")
    
    if not ticket_id:
        return jsonify({"success": False, "error": "Ticket ID required"}), 400
        
    # --- FIX FOR SCANNED URLS ---
    # If scanner sends "http://localhost:5000/ticket/uuid-...", extract the uuid
    if "/ticket/" in ticket_id:
        try:
            ticket_id = ticket_id.split("/ticket/")[-1].split("?")[0]
        except:
            pass # Keep original if split fails

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    cur.execute("SELECT * FROM public_entries WHERE qr_code_path=%s", (ticket_id,))
    entry = cur.fetchone()
    
    if not entry:
        cur.close()
        conn.close()
        return jsonify({"success": False, "status": "invalid", "message": "Ticket not found"})
        
    if entry["status"] == "Entered":
        cur.close()
        conn.close()
        return jsonify({
            "success": True, 
            "status": "used", 
            "message": "Ticket already used",
            "details": entry
        })
        
    # Mark as Entered
    cur.execute("UPDATE public_entries SET status='Entered' WHERE id=%s", (entry["id"],))
    conn.commit()
    
    # Reload entry to get updated status
    entry["status"] = "Entered"
    
    cur.close()
    conn.close()
    
    return jsonify({
        "success": True, 
        "status": "valid", 
        "message": "Entry Approved", 
        "details": entry
    })

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
    
    # --- NEW: Fetch Public Entries & Stats ---
    cur.execute("SELECT * FROM public_entries ORDER BY created_at DESC")
    public_entries = cur.fetchall()
    
    cur.execute("SELECT SUM(amount) as total_revenue, SUM(count) as total_heads FROM public_entries WHERE status != 'Pending'")
    entry_stats = cur.fetchone()
    if not entry_stats['total_revenue']: entry_stats['total_revenue'] = 0
    if not entry_stats['total_heads']: entry_stats['total_heads'] = 0

    # --- DASHBOARD STATS ---
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM users WHERE role='officer'")
    total_officers = cur.fetchone()['cnt']
    
    cur.execute("SELECT COUNT(*) as cnt FROM alerts")
    total_cases = cur.fetchone()['cnt']
    
    pending_count = len(pending_users)
    resolved_count_total = 0 # Placeholder if needed
    
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

    # --- NEW: Fetch Fines Data ---
    cur.execute("SELECT * FROM challans ORDER BY created_at DESC")
    all_fines = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) as total, SUM(amount) as revenue FROM challans")
    fine_totals = cur.fetchone()
    if not fine_totals['revenue']: fine_totals['revenue'] = 0
    
    cur.execute("SELECT COUNT(*) as pending FROM challans WHERE status!='Paid'")
    pending_fines = cur.fetchone()
    
    fines_stats = {
        'total_revenue': fine_totals['revenue'],
        'total_count': fine_totals['total'],
        'pending_count': pending_fines['pending']
    }

    # --- NEW: Fetch All Cases for Management ---
    cur.execute("""
        SELECT c.*, u.name as assigned_officer_name 
        FROM cases c
        LEFT JOIN users u ON c.assigned_officer_id = u.id
        ORDER BY c.created_at DESC
    """)
    all_cases = cur.fetchall()

    cur.close()
    conn.close()

    response = make_response(render_template("dashboard_admin.html", 
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
                           activity_feed=activity_feed,
                           all_fines=all_fines,
                           fines_stats=fines_stats,
                           all_cases=all_cases,
                           public_entries=public_entries,
                           entry_stats=entry_stats))
    
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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

    # Fetch Cases for this Officer
    cur.execute("""
        SELECT * FROM cases 
        WHERE assigned_officer_id=%s 
        ORDER BY created_at DESC
    """, (user_id,))
    my_cases = cur.fetchall()

    cur.close()
    conn.close()

    response = make_response(render_template("dashboard_officer.html", alerts=alerts, messages=messages, recipients=recipients, my_cases=my_cases))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response



@app.route("/api/reassign_case", methods=["POST"])
def reassign_case():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    case_id = data.get("case_id")
    officer_id = data.get("officer_id")
    
    if not case_id or not officer_id:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE cases SET assigned_officer_id=%s WHERE id=%s", (officer_id, case_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/create_case", methods=["POST"])
def create_case():
    if "user" not in session or session["user"]["role"] != "officer":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    title = data.get("title")
    description = data.get("description")
    
    if not title:
        return jsonify({"success": False, "error": "Title is required"}), 400
        
    user_id = session["user"]["id"]
    case_id = f"NETRA-{datetime.now().year}-{random.randint(100, 999)}"
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cases (case_id, title, description, assigned_officer_id, created_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (case_id, title, description, user_id, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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

# ---------------- NEW ROUTES FOR VERIFICATION Refactor ----------------

@app.route("/api/verify_visitor", methods=["POST"])
def verify_visitor():
    if "user" not in session or session["user"]["role"] != "officer":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")

    if not name or not phone:
        return jsonify({"success": False, "error": "Name and Phone are required"}), 400

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Check for visitor in public_entries
    # Exact match for now
    cur.execute("SELECT * FROM public_entries WHERE name=%s AND phone=%s LIMIT 1", (name, phone))
    visitor = cur.fetchone()
    cur.close()
    conn.close()

    if not visitor:
        return jsonify({"success": False, "status": "denied", "message": "Visitor not found in database."})

    # Check Approval Status
    if visitor["status"] in ["Approved", "Paid", "Confirmed"]:
        return jsonify({
            "success": True,
            "status": "granted",
            "message": "Access Granted",
            "visitor": {
                "name": visitor["name"],
                "role": visitor["role"],
                "status": visitor["status"]
            }
        })
    elif visitor["status"] == "Entered":
        return jsonify({"success": False, "status": "flagged", "message": "Visitor already marked as Entered."})
    else:
        # Pending or other status
        return jsonify({"success": False, "status": "denied", "message": "Visitor found but NOT Approved by Admin."})

@app.route("/api/update_profile", methods=["POST"])
def update_profile():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    new_name = data.get("name")
    
    if not new_name:
        return jsonify({"success": False, "error": "Name is required"}), 400

    user_id = session["user"]["id"]
    
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

@app.route("/api/approve_public_entry", methods=["POST"])
def approve_public_entry():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    data = request.get_json()
    entry_id = data.get("id")
    
    if not entry_id:
        return jsonify({"success": False, "error": "ID required"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE public_entries SET status='Approved' WHERE id=%s", (entry_id,))
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

# ---------------- PUBLIC ENTRY SYSTEM ----------------
@app.route("/public-entry")
def public_entry():
    return render_template("public_entry.html", key_id=RAZORPAY_KEY_ID)

import requests

@app.route("/api/send-phone-otp", methods=["POST"])
def send_phone_otp():
    data = request.get_json()
    phone = data.get("phone")
    
    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400

    # Generate OTP
    otp = str(random.randint(1000, 9999))
    session["phone_otp"] = otp
    session["phone_number"] = phone
    
    # Fast2SMS Integration
    api_key = "gG0p14eM3Un8mwaYJ5yqTcb2lXLAzvoKtONV9xR6BCShEHfPZ7Ov6iy5pHueWGCohBqfxKbnclrazAYZ"
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = f"variables_values={otp}&route=otp&numbers={phone}"
    headers = {
        'authorization': api_key,
        'Content-Type': "application/x-www-form-urlencoded",
        'Cache-Control': "no-cache",
    }
    
    try:
        response = requests.request("POST", url, data=payload, headers=headers)
        print(f"\n[Fast2SMS RESPONSE] Status: {response.status_code}, Body: {response.text}\n")
        
        resp_json = response.json()
        if resp_json.get("return") == False:
            # API returned error (e.g. Invalid Number / DLT)
            print(f"------------ FALLBACK OTP (API ERROR): {otp} ------------")
            return jsonify({
                "success": True, 
                "message": f"OTP Sent (Dev Mode: {otp})", 
                "debug_otp": otp
            })

        return jsonify({
            "success": True, 
            "message": "OTP sent to phone via SMS (Dev Mode Active)",
            "debug_otp": otp
        })
    except Exception as e:
        print(f"SMS Failed: {e}")
        print(f"------------ FALLBACK OTP (EXCEPTION): {otp} ------------")
        return jsonify({
            "success": True, 
            "message": f"dOTP Sent (Fallback: {otp})",
            "debug_otp": otp
        })

@app.route("/api/verify-phone-otp", methods=["POST"])
def verify_phone_otp():
    data = request.get_json()
    otp = data.get("otp")
    
    if "phone_otp" not in session:
        return jsonify({"success": False, "error": "OTP expired or not requested"}), 400
        
    if otp == session["phone_otp"]:
        session["phone_verified"] = True
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Invalid OTP"}), 400

@app.route("/api/create-entry-order", methods=["POST"])
def create_entry_order():
    if not session.get("phone_verified"):
        return jsonify({"success": False, "error": "Phone verification required needed"}), 403
        
    data = request.get_json()
    role = data.get("role")
    count = int(data.get("count", 1))
    event_date = data.get("event_date")
    
    session['temp_event_date'] = event_date # Store for confirmation

    
    amount = 0
    if role == "attendee":
        amount = 500 * count # 500 per person
    elif role == "volunteer":
        amount = 1000 # Fix deposit
    elif role == "media":
        amount = 1500 # Base fee
        if count > 2:
             amount += (count - 2) * 800 # Extra chrge for >2 crew
    
    try:
        order_amount = int(amount * 100) # Paise
        order_currency = "INR"
        order_receipt = f"ENTRY-{random.randint(1000,9999)}"
        
        razorpay_order = razorpay_client.order.create({
            "amount": order_amount,
            "currency": order_currency,
            "receipt": order_receipt,
            "payment_capture": "1"
        })
        
        return jsonify({
            "success": True,
            "order_id": razorpay_order['id'],
            "amount": order_amount,
            "key_id": RAZORPAY_KEY_ID
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/ticket/<ticket_id>")
def view_ticket(ticket_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM public_entries WHERE qr_code_path=%s", (ticket_id,))
    entry = cur.fetchone()
    cur.close()
    conn.close()
    
    if not entry:
        return "Ticket Not Found", 404
        
    return render_template("ticket.html", entry=entry)

@app.route("/api/confirm-entry-payment", methods=["POST"])
def confirm_entry_payment():
    if not session.get("phone_verified"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    data = request.get_json()
    payment_id = data.get("payment_id")
    order_id = data.get("order_id")
    signature = data.get("signature")
    
    role = data.get("role")
    name = data.get("name")
    phone = session.get("phone_number")
    count = data.get("count")
    amount = data.get("amount") # In Rupees
    
    # Verify Signature
    params_dict = {
        'razorpay_order_id': order_id,
        'razorpay_payment_id': payment_id,
        'razorpay_signature': signature
    }
    
    try:
        razorpay_client.utility.verify_payment_signature({
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        })
        
        # Signature Valid - Generate Unique Ticket ID
        ticket_id = str(uuid.uuid4())
        event_date = session.get('temp_event_date')
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public_entries (name, phone, role, count, amount, status, payment_id, qr_code_path, event_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (name, phone, role, count, amount, "Paid", payment_id, ticket_id, event_date)
        )
        conn.commit()
        cur.close()
        conn.close()
        
        # Construct Ticket URL
        ticket_url = f"{request.host_url}ticket/{ticket_id}"

        return jsonify({
            "success": True, 
            "message": "Entry Confirmed",
            "ticket_id": ticket_id,
            "ticket_url": ticket_url
        })
        
    except Exception as e:
        print(f"Payment verification failed: {e}")
        return jsonify({"success": False, "error": "Payment Verification Failed"}), 400

# ---------------- EXPORT REPORTS ----------------
@app.route("/generate_case_report/<case_id>")
def generate_case_report(case_id):
    if "user" not in session:
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Fetch Case (Using string ID)
    cur.execute("""
        SELECT c.*, u.name as officer_name, 
               creator.name as creator_name
        FROM cases c 
        LEFT JOIN users u ON c.assigned_officer_id = u.id 
        LEFT JOIN users creator ON c.created_by = creator.id
        WHERE c.case_id=%s
    """, (case_id,))
    case_data = cur.fetchone()
    
    if not case_data:
        cur.close()
        conn.close()
        return "Case not found", 404

    # Fetch Evidence
    cur.execute("""
        SELECT e.*, u.name as uploader_name,
               (SELECT feedback_type FROM cv_reviews WHERE evidence_id=e.id ORDER BY created_at DESC LIMIT 1) as ai_feedback
        FROM evidence e 
        LEFT JOIN users u ON e.uploader_id = u.id 
        WHERE e.case_id=%s 
        ORDER BY e.created_at DESC
    """, (case_data['id'],))
    evidence_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return render_template("report_case.html", case=case_data, evidence=evidence_list, date=datetime.now())
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

@app.route("/api/update_user_role", methods=["POST"])
def update_user_role():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    user_id = data.get("id")
    # This expects 'sub_role' like 'Investigator', 'Supervisor', 'Analyst'
    # The main 'role' remains 'officer' (or 'admin')
    sub_role = data.get("sub_role") 
    
    if not user_id or not sub_role:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
        
    try:
        conn = get_db()
        cur = conn.cursor()
        # We updated the schema to have sub_role column in users table
        cur.execute("UPDATE users SET sub_role=%s WHERE id=%s", (sub_role, user_id))
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
    if any(k in msg_en for k in ["status", "report", "available", "online", "running"]):
        cur.execute("SELECT COUNT(*) as cnt FROM alerts WHERE status!='Resolved'")
        pending = cur.fetchone()['cnt']
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE status='approved'")
        officers = cur.fetchone()['cnt']
        
        severity = "Normal" if pending == 0 else "High Alert" if pending > 5 else "Elevated"
        response_en = f"System Status: {severity}. {pending} active alerts. {officers} officers registered."

    elif any(k in msg_en for k in ["alert", "alarm", "emergency"]):
        cur.execute("SELECT severity, message FROM alerts WHERE status!='Resolved' ORDER BY created_at DESC LIMIT 3")
        alerts = cur.fetchall()
        if not alerts:
             response_en = "No active alerts at this time."
        else:
             lines = [f"[{a['severity']}] {a['message']}" for a in alerts]
             response_en = "Recent Alerts: " + "; ".join(lines)
    
    elif any(k in msg_en for k in ["officer", "police", "offer"]):
        cur.execute("SELECT name FROM users WHERE status='approved' LIMIT 5")
        users = cur.fetchall()
        names = ", ".join([u['name'] for u in users])
        response_en = f"Active Officers: {names}..."

    elif any(k in msg_en for k in ["pay", "fine", "challan", "bill"]):
        response_en = "To pay a fine, please verify your Challan ID in the 'Fines' section or use the payment link sent to your SMS."

    elif any(k in msg_en for k in ["message", "contact", "admin"]):
        response_en = "To contact the Admin or other officers, please use the 'Messages' section in your dashboard sidebar."

    elif "hello" in msg_en or "hi" in msg_en:
        response_en = f"Hello {session['user']['name']}. How can I assist you with security operations?"

    elif "help" in msg_en:
        response_en = "Commands: 'status', 'alerts', 'officers', 'pay fine', 'contact admin'"
    
    else:
        response_en = "I didn't quite catch that. Try asking for 'status', 'alerts', or 'payment'."

    cur.close()
    conn.close()

    # 2. Translate Output to Target Language if needed
    final_response = response_en
    if target_lang != 'en':
        try:
            final_response = GoogleTranslator(source='en', target=target_lang).translate(response_en)
        except Exception as e:
            print(f"Translation Error (Output): {e}")
            final_response = response_en

    return jsonify({"response": final_response})

# ---------------- VIDEO STREAMING ----------------

@app.route('/api/system_stats')
def system_stats():
    # Simulate data due to environment restrictions
    cpu = random.randint(20, 45) + (random.random() * 10)
    memory = random.randint(40, 60) + (random.random() * 5)
    return jsonify({"cpu": cpu, "memory": memory})

# ---------------- VIDEO STREAMING ----------------
@app.route("/api/get_case_details/<case_id>")
def get_case_details(case_id):
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Fetch Case Info
    # Check updated cases table schema: id is distinct from case_id (string)
    # The route param can be the string case_id or int id. Let's assume string case_id
    cur.execute("""
        SELECT c.*, u.name as officer_name 
        FROM cases c 
        LEFT JOIN users u ON c.assigned_officer_id = u.id 
        WHERE c.case_id=%s
    """, (case_id,))
    case_data = cur.fetchone()
    
    if not case_data:
        cur.close()
        conn.close()
        return jsonify({"success": False, "error": "Case not found"}), 404

    # Fetch Evidence
    cur.execute("""
        SELECT e.*, u.name as uploader_name 
        FROM evidence e 
        LEFT JOIN users u ON e.uploader_id = u.id 
        WHERE e.case_id=%s 
        ORDER BY e.created_at DESC
    """, (case_data['id'],))
    evidence_list = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify({
        "success": True, 
        "case": case_data, 
        "evidence": evidence_list
    })

@app.route("/api/upload_evidence", methods=["POST"])
def upload_evidence():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part"}), 400
        
    file = request.files['file']
    case_db_id = request.form.get('case_db_id') # Int ID
    tags = request.form.get('tags')
    
    if file.filename == '' or not case_db_id:
        return jsonify({"success": False, "error": "Missing file or case ID"}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Save path: static/evidence/CASE_ID/filename
        # Need case_id string for folder name
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT case_id FROM cases WHERE id=%s", (case_db_id,))
        case_res = cur.fetchone()
        
        if not case_res:
             cur.close()
             conn.close()
             return jsonify({"success": False, "error": "Invalid case ID"}), 404
             
        case_str = case_res['case_id']
        save_dir = os.path.join("static", "evidence", case_str)
        os.makedirs(save_dir, exist_ok=True)
        
        save_path = os.path.join(save_dir, filename)
        # Convert backslashes to forward slashes for DB consistency
        db_path = save_path.replace("\\", "/")
        
        file.save(save_path)
        
        # Insert into DB
        user_id = session['user']['id']
        file_type = filename.rsplit('.', 1)[1].lower()
        
        cur.execute("""
            INSERT INTO evidence (case_id, uploader_id, file_path, file_type, tags, status)
            VALUES (%s, %s, %s, %s, %s, 'Pending')
        """, (case_db_id, user_id, db_path, file_type, tags))
        
        # Audit Log
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, target_id, target_type, details)
            VALUES (%s, 'Uploaded Evidence', LAST_INSERT_ID(), 'evidence', %s)
        """, (user_id, f"Uploaded {filename}"))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
        
    return jsonify({"success": False, "error": "File type not allowed"}), 400

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

@app.route("/api/get_notifications")
def get_notifications():
    # Return empty list or recent alerts to satisfy dashboard polling
    if "user" not in session:
        return jsonify([])
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT message, created_at FROM alerts WHERE status='Open' ORDER BY created_at DESC LIMIT 5")
        notes = [{"message": m, "time": str(t)} for (m, t) in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(notes)
    except Exception:
        return jsonify([])

@app.route("/api/sos_alert", methods=["POST"])
def sos_alert():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    alert_type = data.get("type")
    lat = data.get("lat")
    lng = data.get("lng")
    snapshot = data.get("snapshot") # Base64 Image string
    
    officer_name = session["user"]["name"]
    user_id = session["user"]["id"]
    
    # Construct Message
    message = f"SOS: {alert_type.upper()} reported by {officer_name}"
    if lat and lng:
        message += f" at Location {lat}, {lng}"
        
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Save snapshot if provided (mock save, normally write to file)
        snapshot_path = None
        # In real impl, decode base64 and save to static/evidence
        
        # Insert as Critical Alert
        cur.execute("""
            INSERT INTO alerts (source, message, severity, status, assigned_officer_id)
            VALUES (%s, %s, 'Critical', 'Investigating', %s)
        """, (f"SOS-{officer_name}", message, user_id))
        
        # Also broadcast to Admin inbox
        cur.execute("SELECT id FROM users WHERE role='admin'")
        admins = cur.fetchall()
        for admin in admins:
            cur.execute("""
                INSERT INTO messages (sender_id, receiver_id, content)
                VALUES (%s, %s, %s)
            """, (user_id, admin['id'], f"EMERGENCY SOS: {message}"))
            
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"SOS Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/get_recent_alerts")
def get_recent_alerts():
    if "user" not in session:
        return jsonify([]), 401
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    # Fetch last 5 open alerts
    cur.execute("""
        SELECT id, source, message, severity, status, created_at, snapshot_path
        FROM alerts 
        WHERE status != 'Resolved'
        ORDER BY created_at DESC LIMIT 5
    """)
    alerts = cur.fetchall()
    for a in alerts:
        a['created_at'] = a['created_at'].strftime("%H:%M:%S")
    
    cur.close()
    conn.close()
    return jsonify(alerts)

@app.route("/api/officer_activity")
def officer_activity():
    if "user" not in session:
        return jsonify([]), 401
    
    user_id = session["user"]["id"]
    logs = []
    
    try:
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        
        # 1. Alerts Resolved by this officer (Assuming we track who resolved it, 
        # butschema might not have 'resolved_by'. We use 'assigned_officer_id' + status='Resolved')
        cur.execute("""
            SELECT id, message, updated_at as time, 'alert' as type
            FROM alerts 
            WHERE assigned_officer_id=%s AND status='Resolved'
            ORDER BY updated_at DESC LIMIT 10
        """, (user_id,))
        resolved = cur.fetchall()
        for r in resolved:
            logs.append({
                "action": "Resolved Alert",
                "details": f"#{r['id']}: {r['message']}",
                "timestamp": r['time'].strftime("%Y-%m-%d %H:%M") if r['time'] else "Recent",
                "type": "alert"
            })
            
        # 2. Messages Sent
        cur.execute("""
            SELECT content, timestamp, 'message' as type
            FROM messages
            WHERE sender_id=%s
            ORDER BY timestamp DESC LIMIT 10
        """, (user_id,))
        msgs = cur.fetchall()
        for m in msgs:
            logs.append({
                "action": "Sent Message",
                "details": m['content'][:50] + "..." if len(m['content']) > 50 else m['content'],
                "timestamp": m['timestamp'].strftime("%Y-%m-%d %H:%M") if m['timestamp'] else "Recent",
                "type": "message"
            })
            
        # 3. Patrol Logs (Mock)
        my_patrols = [p for p in MOCK_PATROL_LOGS if p['user_id'] == user_id]
        for p in my_patrols:
            logs.append({
                "action": "Patrol Check-in",
                "details": f"{p['location']} - {p['notes']}",
                "timestamp": p['time'],
                "type": "patrol"
            })

        cur.close()
        conn.close()
        
        # Sort combined logs
        logs.sort(key=lambda x: str(x['timestamp']), reverse=True)
        return jsonify(logs[:20])
        
    except Exception as e:
        print(f"Activity Log Error: {e}")
        return jsonify([])


# ---------------- ANALYTICS API ----------------
@app.route("/api/analytics_data")
def analytics_data():
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Severity Distribution
    cur.execute("SELECT severity, COUNT(*) as count FROM alerts GROUP BY severity")
    severity_data = cur.fetchall()
    
    # Activity Trend (Last 7 days alert counts)
    cur.execute("""
        SELECT DATE(timestamp) as date, COUNT(*) as count 
        FROM alerts 
        WHERE timestamp >= DATE(NOW()) - INTERVAL 7 DAY 
        GROUP BY DATE(timestamp) 
        ORDER BY date ASC
    """)
    trend_data = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return jsonify({
        "severity": {item['severity']: item['count'] for item in severity_data},
        "trend": {str(item['date']): item['count'] for item in trend_data}
    })

# ---------------- CHALLAN / PAYMENT SYSTEM ----------------




import os
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/api/issue_challan", methods=["POST"])
def issue_challan():
    if "user" not in session or session["user"]["role"] != "officer":
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    # Handle FormData (File + Fields)
    amount = request.form.get("amount")
    reason = request.form.get("reason")
    violator_name = request.form.get("violator_name")
    
    file = request.files.get('evidence')
    evidence_path = None
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"evidence_{amount}_{file.filename}") # Simple unique naming
        os.makedirs("static/evidence", exist_ok=True)
        file.save(os.path.join("static/evidence", filename))
        evidence_path = f"static/evidence/{filename}"

    if not amount or not reason:
        return jsonify({"success": False, "error": "Amount and Reason required"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO challans (amount, reason, issued_by, violator_name, status, evidence_path)
            VALUES (%s, %s, %s, %s, 'Pending', %s)
        """, (amount, reason, session["user"]["id"], violator_name, evidence_path))
        
        challan_id = cur.lastrowid
        conn.commit()
        cur.close()
        conn.close()
        
        # Generate Payment Link
        payment_link = url_for('pay_challan_page', challan_id=challan_id, _external=True)
        
        return jsonify({
            "success": True, 
            "message": "Fine Issued Successfully",
            "challan_id": challan_id,
            "payment_link": payment_link
        })
    except Exception as e:
        print(e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/pay_challan/<int:challan_id>")
def pay_challan_page(challan_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM challans WHERE id=%s", (challan_id,))
    challan = cur.fetchone()
    cur.close()
    conn.close()
    
    if not challan:
        return "Challan not found", 404
        
    if challan["status"] == "Paid":
        return render_template("pay_challan.html", challan=challan, already_paid=True)

    # Create Razorpay Order
    amount_paisa = int(challan["amount"] * 100)
    data = {"amount": amount_paisa, "currency": "INR", "receipt": str(challan["id"])}
    try:
        order = razorpay_client.order.create(data=data)
        order_id = order["id"]
    except Exception as e:
        print(f"Razorpay Error: {e}")
        order_id = "test_order_id" # Fallback for now if keys are invalid

    return render_template("pay_challan.html", 
                           challan=challan, 
                           formatted_amount=challan["amount"],
                           order_id=order_id,
                           key_id=RAZORPAY_KEY_ID)

@app.route("/api/verify_payment", methods=["POST"])
def verify_payment():
    data = request.json
    try:
        # Verify signature
        params_dict = {
            'razorpay_order_id': data['razorpay_order_id'],
            'razorpay_payment_id': data['razorpay_payment_id'],
            'razorpay_signature': data['razorpay_signature']
        }
        # razorpay_client.utility.verify_payment_signature(params_dict) # Uncomment with valid keys
        
        # Update DB
        challan_id = data.get("challan_id") 
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE challans 
            SET status='Paid', payment_id=%s, paid_at=NOW() 
            WHERE id=%s
        """, (data['razorpay_payment_id'], challan_id))
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Payment Verification Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 400

# ---------------- RECEIPTS (PDF) ----------------
#from xhtml2pdf import pisa
from io import BytesIO

@app.route("/download_receipt/<int:challan_id>")
def download_receipt(challan_id):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM challans WHERE id=%s", (challan_id,))
    challan = cur.fetchone()
    cur.close()
    conn.close()
    
    if not challan or challan["status"] != "Paid":
        return "Receipt not available", 404

    # Render HTML for PDF
    html = render_template("receipt_template.html", challan=challan)
    
    # Generate PDF
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(html.encode("utf-8")), dest=pdf)
    
    if pisa_status.err:
        return "PDF Generation Error", 500
        
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name=f"NETRA_Receipt_{challan_id}.pdf", mimetype='application/pdf')

@app.route("/generate_case_file/<int:alert_id>")
def generate_case_file(alert_id):
    if "user" not in session or session["user"]["role"] != "admin":
        return "Unauthorized", 403

    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Fetch Alert with Officer Name
    cur.execute("""
        SELECT a.*, u.name as officer_name 
        FROM alerts a 
        LEFT JOIN users u ON a.assigned_officer_id = u.id 
        WHERE a.id=%s
    """, (alert_id,))
    alert = cur.fetchone()
    
    cur.close()
    conn.close()
    
    if not alert:
        return "Alert not found", 404

    # Fix image path for xhtml2pdf (needs absolute local path)
    if alert['snapshot_path']:
        # Assuming snapshot_path is relative like 'static/headers/...'
        # We need absolute path e.g., C:/Users/ABC/Desktop/NETRA/static/...
        alert['local_path'] = os.path.join(app.root_path, alert['snapshot_path'].replace('/', os.sep))

    from datetime import datetime
    html = render_template("case_file_template.html", alert=alert, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    pdf = BytesIO()
    pisa_status = pisa.CreatePDF(BytesIO(html.encode("utf-8")), dest=pdf)
    
    if pisa_status.err:
        return f"PDF Error: {pisa_status.err}", 500
        
    pdf.seek(0)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name=f"CASE_FILE_{alert_id}.pdf", mimetype='application/pdf')

# ---------------- OFFICER UTILS ----------------

@app.route("/api/officer_stats")
def officer_stats():
    if "user" not in session: return jsonify({})
    user_id = session["user"]["id"]
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # Fines Issued Today
    cur.execute("SELECT COUNT(*) as count FROM challans WHERE issued_by=%s AND DATE(created_at) = DATE(NOW())", (user_id,))
    fines_today = cur.fetchone()['count']
    
    # Alerts Resolved
    cur.execute("SELECT COUNT(*) as count FROM alerts WHERE assigned_officer_id=%s AND status='Resolved'", (user_id,))
    resolved_total = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    
    return jsonify({
        "fines_today": fines_today,
        "resolved_total": resolved_total
    })

@app.route("/api/log_patrol", methods=["POST"])
def log_patrol():
    if "user" not in session: return "Unauthorized", 401
    
    data = request.json
    loc = data.get("location", "Unknown Location")
    notes = data.get("notes", "")
    
    # Store in Mock Store
    log_entry = {
        "user_id": session["user"]["id"],
        "name": session["user"]["name"],
        "location": loc,
        "notes": notes,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    MOCK_PATROL_LOGS.append(log_entry)
    
    return jsonify({"success": True, "message": "Patrol Point Logged"})

@app.route("/api/report_incident", methods=["POST"])
def report_incident():
    if "user" not in session: return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.form
    inc_type = data.get("type", "General")
    location = data.get("location", "Unknown")
    description = data.get("description", "")
    
    # In a real app, save image from request.files
    
    conn = get_db()
    cur = conn.cursor()
    # Using alerts table for generic incidents for now
    msg = f"INCIDENT REPORT [{inc_type}] at {location}: {description}"
    cur.execute("INSERT INTO alerts (source, message, severity, status, assigned_officer_id) VALUES (%s, %s, 'Warning', 'Investigating', %s)",
                (f"Officer-{session['user']['name']}", msg, session['user']['id']))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"success": True})

@app.route("/api/simulate_ai_alert", methods=["POST"])
def simulate_ai_alert():
    if "user" not in session: return jsonify({"success": False}), 401
    
    data = request.json
    alert_kind = data.get("kind", "loitering")
    
    msgs = {
        "loitering": "Suspicious Loitering detected at Gate 3 (Duration: >10m)",
        "crowd_rapid": "Rapid Crowd Movement detected in Sector B - Potential Stampede Risk",
        "object": "Unattended Object detected near Lobby Elevator"
    }

    
    sev = "Critical" if alert_kind in ["crowd_rapid"] else "Warning"
    msg = msgs.get(alert_kind, "Abnormal Behavior Detected")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO alerts (source, message, severity, status, created_at) VALUES (%s, %s, %s, %s, NOW())",
                ("AI-Surveillance", msg, sev, "Open"))
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"success": True, "message": msg})




@app.route("/api/process_detection", methods=["POST"])
def process_detection():
    data = request.get_json()
    cam_id = data.get("camera_id", "CAM-UNKNOWN")
    d_type = data.get("detection_type", "General Alert")
    conf = data.get("confidence", 0.0)
    
    msg = f"AI DETECTION: {d_type} (Conf: {int(conf*100)}%)"
    
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO alerts (source, message, severity, status, created_at) VALUES (%s, %s, %s, %s, NOW())",
                    (cam_id, msg, "Warning", "Open"))
        conn.commit()
        cur.close()
        conn.close()
        print(f"DEBUG: Processed detection {d_type} from {cam_id}")
        return jsonify({"success": True})
    except Exception as e:
        print(f"Error processing detection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ---------------- OFFICER REVIEW ----------------
@app.route("/api/get_pending_reviews")
def get_pending_reviews():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    
    # For now, show all auto-detected
    cur.execute("""
        SELECT e.* 
        FROM evidence e
        WHERE e.review_status='Pending Review' 
        ORDER BY e.created_at DESC
    """)
    reviews = cur.fetchall()
    
    for r in reviews:
        r['created_at'] = str(r['created_at'])
        
    cur.close()
    conn.close()
    return jsonify(reviews)

@app.route("/api/confirm_violation", methods=["POST"])
def confirm_violation():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    data = request.get_json()
    e_id = data.get("id")
    remarks = data.get("remarks", "")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE evidence 
        SET review_status='Confirmed', 
            status='Verified', 
            tags=CONCAT(COALESCE(tags, ''), ' [Confirmed Violation]'),
            uploader_id=%s -- Assign confirming officer
        WHERE id=%s
    """, (session['user']['id'], e_id))
    
    # Log Action
    log_action(conn, session['user']['id'], 'review_confirm', f"Confirmed violation evidence #{e_id}. Remarks: {remarks}")
    
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/dismiss_violation", methods=["POST"])
def dismiss_violation():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    data = request.get_json()
    e_id = data.get("id")
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE evidence SET review_status='Dismissed', status='Rejected' WHERE id=%s", (e_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"success": True})

@app.route("/api/quick_action", methods=["POST"])
def quick_action():
    if "user" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.get_json()
    action = data.get("action")
    
    valid_actions = ['alarm', 'spotlight', 'broadcast', 'redirect']
    if action not in valid_actions:
         return jsonify({"success": False, "error": "Invalid Action"}), 400
         
    conn = get_db()
    
    # 1. Log Action
    log_action(conn, session['user']['id'], 'quick_action', f"Triggered {action.upper()}")
    
    # 2. Broadcast Message (Simulated Radio/System Alert)
    user_name = session['user']['name']
    alert_msg = ""
    if action == 'redirect':
        alert_msg = f"⚠ CROWD CONTROL ALERT: {user_name} has requested crowd redirection. All units check tactical map."
    elif action == 'alarm':
        alert_msg = f"🚨 EMERGENCY ALARM triggered by {user_name}. Report to HQ immediately."
    elif action == 'spotlight':
        alert_msg = f"🔦 SPOTLIGHT ACTIVATED by {user_name}. Visual confirmation in progress."
    elif action == 'broadcast':
        alert_msg = f"📢 GENERAL BROADCAST initiated by {user_name}."

    if alert_msg:
        # Insert into messages table with sender_id=NULL (System) or User? Let's use User.
        # Or better, sender_id = session['user']['id']
        cur = conn.cursor()
        # Sender: Self, Receiver: NULL (Broadcast to all)
        cur.execute("INSERT INTO messages (sender_id, receiver_id, content) VALUES (%s, NULL, %s)", 
                    (session['user']['id'], alert_msg))
        conn.commit()
        cur.close()

    conn.close()
    
    return jsonify({"success": True, "message": alert_msg})


# ---------------- SYSTEM CONFIG ----------------
@app.route("/api/get_system_config")
def get_system_config():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT config_key, config_value FROM system_config")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    config = {row['config_key']: row['config_value'] for row in rows}
    # Ensure keys exist for frontend
    defaults = {'ai_scan': 'true', 'lockdown': 'false', 'alert_msg': 'System Alert: Please remain calm.'}
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
            
    return jsonify(config)

@app.route("/api/update_system_config", methods=["POST"])
def update_system_config():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    
    data = request.get_json()
    conn = get_db()
    cur = conn.cursor()
    
    try:
        for key, value in data.items():
            cur.execute("""
                INSERT INTO system_config (config_key, config_value) 
                VALUES (%s, %s) 
                ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
            """, (key, str(value)))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


# ---------------- UTILS ----------------
def log_action(user_id, action, target_type=None, target_id=None):
    """Utility to log administrative or security actions to the database."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO logs (user_id, action, target_type, target_id, timestamp)
            VALUES (%s, %s, %s, %s, NOW())
        """, (user_id, action, target_type, target_id))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DEBUG: log_action failed: {e}")

if __name__ == "__main__":
    # Disable reloader and debug for stable camera hardware access on Windows
    app.run(debug=False, host='0.0.0.0', use_reloader=False)

