from flask import Flask, render_template, Response
import cv2
import threading
import time
import requests

from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

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

            camera_urls.append(url)

            print(f"Camera Found: {url}")

    except Exception:

        pass

# -----------------------------------
# PARALLEL NETWORK SCAN
# -----------------------------------

with ThreadPoolExecutor(max_workers=100) as executor:

    for i in range(START_IP, END_IP + 1):

        ip = f"{BASE_IP}{i}"

        executor.submit(
            detect_camera,
            ip
        )

print(f"Total Cameras Found: {len(camera_urls)}")

# -----------------------------------
# OPEN ACTIVE CAMERAS ONLY
# -----------------------------------

for url in camera_urls:

    print(f"Connecting: {url}")

    cap = cv2.VideoCapture(url)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if cap.isOpened():

        print(f"Connected: {url}")

        caps.append(cap)

    else:

        print(f"Failed: {url}")

# -----------------------------------
# CAMERA READER THREAD
# -----------------------------------

def camera_reader(camera_id, cap):

    global latest_frames
    global camera_alerts
    global camera_fps
    global camera_status

    frame_count = 0

    start_time = time.time()

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
        # FPS CALCULATION
        # -----------------------------------

        elapsed = time.time() - start_time

        if elapsed > 0:

            fps = frame_count / elapsed

            camera_fps[camera_id] = int(fps)

        # -----------------------------------
        # STATUS OVERLAY
        # -----------------------------------

        color = (0, 255, 0)

        if alert != "SAFE":

            color = (0, 0, 255)

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

        # -----------------------------------
        # SAVE DATA
        # -----------------------------------

        camera_alerts[camera_id] = alert

        latest_frames[camera_id] = frame

        time.sleep(0.03)

# -----------------------------------
# START CAMERA THREADS
# -----------------------------------

for i, cap in enumerate(caps):

    threading.Thread(
        target=camera_reader,
        args=(i, cap),
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
        statuses=camera_status
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