import cv2
import numpy as np
import os
import time
from datetime import datetime

# --- CONFIGURATION ---
CROWD_THRESHOLD = 5  # Number of people to trigger alert
MOTION_THRESHOLD = 5000  # Area of movement to trigger motion alert
ALERT_COOLDOWN = 5  # Seconds between automated snapshots
SNAPSHOT_DIR = "alerts"

# Ensure alert directory exists
if not os.path.exists(SNAPSHOT_DIR):
    os.makedirs(SNAPSHOT_DIR)

def start_netra_cv():
    # 1. Initialize Camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open laptop webcam.")
        return

    # 2. Initialize HOG Person Detector
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    # 3. Motion Detection Variables
    prev_frame = None
    last_alert_time = 0

    print(f"NETRA CV Module Started. Threshold: {CROWD_THRESHOLD} people.")
    print("Press 'q' to exit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Basic preprocessing for motion detection and detection
        original_frame = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (21, 21), 0)

        # --- PERSON DETECTION & CROWD COUNTING ---
        # Detect people in the frame
        # WinStride and padding are optimized for real-time performance on typical laptops
        (rects, weights) = hog.detectMultiScale(frame, winStride=(4, 4), padding=(8, 8), scale=1.05)
        
        person_count = len(rects)
        is_crowd_alert = person_count >= CROWD_THRESHOLD
        
        # Color based on alert status (Red for Alert, Green for Normal)
        box_color = (0, 0, 255) if is_crowd_alert else (0, 255, 0)

        # Draw Bounding Boxes
        for (x, y, w, h) in rects:
            cv2.rectangle(frame, (x, y), (x + w, y + h), box_color, 2)
            cv2.putText(frame, "Person Detected", (x, y - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1)

        # --- MOTION DETECTION ---
        motion_label = ""
        if prev_frame is not None:
            frame_delta = cv2.absdiff(prev_frame, gray_blur)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                if cv2.contourArea(contour) > MOTION_THRESHOLD:
                    motion_label = "Unusual Movement Detected"
                    break
        
        prev_frame = gray_blur

        # --- EVIDENCE CAPTURE ---
        if is_crowd_alert:
            current_time = time.time()
            if current_time - last_alert_time > ALERT_COOLDOWN:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = os.path.join(SNAPSHOT_DIR, f"alert_{timestamp}.jpg")
                cv2.imwrite(filename, original_frame)
                print(f"[ALERT] Crowd threshold exceeded! Snapshot saved: {filename}")
                last_alert_time = current_time

        # --- UI OVERLAY ---
        # Header Box
        overlay_color = (0, 30, 0) # Dark green
        if is_crowd_alert: overlay_color = (0, 0, 50) # Dark red

        # Status text
        status_text = "SYSTEM STATUS: NORMAL"
        if is_crowd_alert:
            status_text = "CROWD DENSITY ALERT!"
        
        # Draw background bar for UI
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 80), overlay_color, -1)
        
        # Text Overlays
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"NETRA | {status_text}", (20, 30), font, 0.8, (255, 255, 255), 2)
        cv2.putText(frame, f"Crowd Count: {person_count}", (20, 60), font, 0.6, (19, 236, 91), 1)
        
        # Timestamp
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (frame.shape[1] - 220, 30), font, 0.5, (200, 200, 200), 1)

        # Motion Alert Overlay
        if motion_label:
            cv2.putText(frame, motion_label, (20, 110), font, 0.6, (0, 255, 255), 2)

        # 4. Show Frame
        cv2.imshow("NETRA — Crowd Monitoring System", frame)

        # Exit on 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Cleanup
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_netra_cv()
