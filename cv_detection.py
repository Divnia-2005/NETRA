import cv2
import datetime
import requests
import json
import threading

def send_alert(frame):
    # Simulate sending metadata to backend
    # In a real scenario, we would upload the image to an endpoint
    # For now, we assume the backend handles the image or uses a placeholder
    
    import random
    
    # Simulate meaningful detection types
    detection_types = [
        {"type": "Loitering", "conf": 0.92},
        {"type": "Watchlist Match", "conf": 0.88},
        {"type": "Aggressive Behavior", "conf": 0.76},
        {"type": "Unattended Bag", "conf": 0.95}
    ]
    
    # Pick a random event
    event = random.choice(detection_types)

    url = "http://localhost:5000/api/process_detection"
    payload = {
        "camera_id": "CAM-01",
        "timestamp": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "confidence": event['conf'],
        "detection_type": event['type']  # New field
    }
    
    try:
        print(f"Sending Alert: {event['type']}... {payload}")
        res = requests.post(url, json=payload)
        print("Server Response:", res.json())
    except Exception as e:
        print(f"Failed to send alert: {e}")

def start_detection():
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # UI Overlay
        cv2.putText(frame, "NETRA AI: Monitoring [CAM-01]", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
        
        cv2.putText(frame, "Press 'd' to Simulate Detection", (20,80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 1)

        cv2.imshow("NETRA Surveillance", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('d'):
            # Trigger in a thread to not block video loop
            threading.Thread(target=send_alert, args=(frame,)).start()

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    start_detection()
