import cv2
import datetime

def start_detection():
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Dummy detection logic
        cv2.putText(frame, "Monitoring...", (20,40),
                    cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),2)

        cv2.imshow("NETRA Surveillance", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            filename = f"static/snapshots/{datetime.datetime.now()}.jpg"
            cv2.imwrite(filename, frame)
            break

    cap.release()
    cv2.destroyAllWindows()
