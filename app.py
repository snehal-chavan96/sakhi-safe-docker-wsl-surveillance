from flask import Flask, render_template, Response
import cv2
import threading
import time
import requests
import os

from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# -----------------------------------
# CREATE ALERTS FOLDER
# -----------------------------------

if not os.path.exists("alerts"):

    os.makedirs("alerts")

# -----------------------------------
# AI HUMAN DETECTOR
# -----------------------------------

hog = cv2.HOGDescriptor()

hog.setSVMDetector(
    cv2.HOGDescriptor_getDefaultPeopleDetector()
)

# -----------------------------------
# CAMERA RANGE CONFIGURATION
# -----------------------------------

BASE_IP = "50.0.1."

START_IP = 160
END_IP = 255

print(f"Scanning Range: {BASE_IP}{START_IP}-{END_IP}")

# -----------------------------------
# GLOBAL STORAGE
# -----------------------------------

camera_urls = []

caps = []

latest_frames = {}

camera_alerts = {}

camera_fps = {}

camera_status = {}

incident_logs = []

last_saved_time = {}

# -----------------------------------
# CAMERA READER THREAD
# -----------------------------------

def camera_reader(camera_id, cap):

    global latest_frames
    global camera_alerts
    global camera_fps
    global camera_status
    global incident_logs
    global last_saved_time

    frame_count = 0

    start_time = time.time()

    prev_gray = None

    while True:

        success, frame = cap.read()

        if not success:

            print(f"Camera {camera_id + 1} Offline")

            camera_alerts[camera_id] = "CAMERA OFFLINE"

            camera_status[camera_id] = "OFFLINE"

            time.sleep(1)

            continue

        camera_status[camera_id] = "ONLINE"

        # -----------------------------------
        # PERFORMANCE RESIZE
        # -----------------------------------

        frame = cv2.resize(frame, (320, 240))

        # -----------------------------------
        # MOTION DETECTION
        # -----------------------------------

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        motion_detected = False

        if prev_gray is not None:

            diff = cv2.absdiff(
                prev_gray,
                gray
            )

            _, thresh = cv2.threshold(
                diff,
                25,
                255,
                cv2.THRESH_BINARY
            )

            motion_score = cv2.countNonZero(
                thresh
            )

            if motion_score > 5000:

                motion_detected = True

        prev_gray = gray

        frame_count += 1

        alert = "SAFE"

        # -----------------------------------
        # RUN AI EVERY 10 FRAMES
        # -----------------------------------

        if frame_count % 10 == 0:

            boxes, weights = hog.detectMultiScale(
                frame,
                winStride=(8, 8)
            )

            for (x, y, w, h) in boxes:

                cv2.rectangle(
                    frame,
                    (x, y),
                    (x + w, y + h),
                    (0, 0, 255),
                    2
                )

                cv2.putText(
                    frame,
                    "PERSON DETECTED",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    2
                )

                alert = "PERSON DETECTED"

        # -----------------------------------
        # MOTION ALERT
        # -----------------------------------

        if motion_detected and alert == "SAFE":

            alert = "SUSPICIOUS MOVEMENT"

        # -----------------------------------
        # FPS CALCULATION
        # -----------------------------------

        elapsed = time.time() - start_time

        if elapsed > 0:

            fps = frame_count / elapsed

            camera_fps[camera_id] = int(fps)

        # -----------------------------------
        # STATUS COLORS
        # -----------------------------------

        color = (0, 255, 0)

        if alert == "PERSON DETECTED":

            color = (0, 0, 255)

        elif alert == "SUSPICIOUS MOVEMENT":

            color = (0, 255, 255)

        elif alert == "CAMERA OFFLINE":

            color = (128, 128, 128)

        # -----------------------------------
        # FRAME OVERLAYS
        # -----------------------------------

        cv2.putText(
            frame,
            f"STATUS: {alert}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

        cv2.putText(
            frame,
            f"FPS: {camera_fps.get(camera_id, 0)}",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"CAMERA {camera_id + 1}",
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            time.strftime("%H:%M:%S"),
            (10, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

        # -----------------------------------
        # SAVE ALERT DATA
        # -----------------------------------

        camera_alerts[camera_id] = alert

        latest_frames[camera_id] = frame

        # -----------------------------------
        # SAVE SNAPSHOTS
        # -----------------------------------

        current_time = time.time()

        if alert != "SAFE":

            last_time = last_saved_time.get(
                camera_id,
                0
            )

            # SAVE EVERY 10 SECONDS MAX
            if current_time - last_time > 10:

                timestamp = time.strftime(
                    "%Y%m%d_%H%M%S"
                )

                filename = (
                    f"alerts/camera_"
                    f"{camera_id + 1}_"
                    f"{alert.replace(' ', '_')}_"
                    f"{timestamp}.jpg"
                )

                cv2.imwrite(
                    filename,
                    frame
                )

                print(
                    f"Snapshot Saved: {filename}"
                )

                incident_logs.insert(0, {

                    "camera": camera_id + 1,

                    "alert": alert,

                    "time": timestamp,

                    "image": filename

                })

                last_saved_time[camera_id] = current_time

        time.sleep(0.03)

# -----------------------------------
# CONNECT NEW CAMERA
# -----------------------------------

def connect_camera(url):

    cap = cv2.VideoCapture(url)

    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    if cap.isOpened():

        print(f"Connected: {url}")

        camera_id = len(caps)

        caps.append(cap)

        threading.Thread(
            target=camera_reader,
            args=(camera_id, cap),
            daemon=True
        ).start()

    else:

        print(f"Failed: {url}")

# -----------------------------------
# CAMERA DETECTION
# -----------------------------------

def detect_camera(ip):

    try:

        response = requests.get(
            f"http://{ip}:8080",
            timeout=0.3
        )

        if response.status_code == 200:

            url = f"http://{ip}:8080/video"

            if url not in camera_urls:

                camera_urls.append(url)

                print(f"Camera Found: {url}")

                connect_camera(url)

    except Exception:

        pass

# -----------------------------------
# BACKGROUND CAMERA SCANNER
# -----------------------------------

def background_scanner():

    while True:

        print("Scanning For New Cameras...")

        with ThreadPoolExecutor(
            max_workers=50
        ) as executor:

            for i in range(
                START_IP,
                END_IP + 1
            ):

                ip = f"{BASE_IP}{i}"

                executor.submit(
                    detect_camera,
                    ip
                )

        time.sleep(30)

# -----------------------------------
# START BACKGROUND SCANNER
# -----------------------------------

threading.Thread(
    target=background_scanner,
    daemon=True
).start()

# -----------------------------------
# VIDEO GENERATOR
# -----------------------------------

def generate_frames(camera_id):

    while True:

        if camera_id not in latest_frames:

            time.sleep(0.1)

            continue

        frame = latest_frames[camera_id]

        ret, buffer = cv2.imencode(
            '.jpg',
            frame
        )

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )

        time.sleep(0.03)

# -----------------------------------
# DASHBOARD
# -----------------------------------

@app.route('/')
def index():

    cameras = []

    for i in range(len(caps)):

        cameras.append(f"/video/{i}")

    total_alerts = sum(
        1 for alert in camera_alerts.values()
        if alert != "SAFE"
    )

    return render_template(
        "index.html",
        cameras=cameras,
        alerts=camera_alerts,
        total_alerts=total_alerts,
        statuses=camera_status,
        incidents=incident_logs
    )

# -----------------------------------
# VIDEO STREAM ROUTE
# -----------------------------------

@app.route('/video/<int:camera_id>')
def video(camera_id):

    return Response(
        generate_frames(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# -----------------------------------
# START SERVER
# -----------------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True
    )