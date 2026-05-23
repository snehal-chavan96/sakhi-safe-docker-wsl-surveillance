from flask import Flask, render_template, Response
import cv2
import requests
import threading
import time
import socket

from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# -----------------------------
# AI HUMAN DETECTOR
# -----------------------------

hog = cv2.HOGDescriptor()
hog.setSVMDetector(
    cv2.HOGDescriptor_getDefaultPeopleDetector()
)

# -----------------------------
# AUTO WIFI SUBNET DETECTION
# -----------------------------


base_ip = "172.29.0."

print(f"Scanning Network: {base_ip}0/24")

# -----------------------------
# GLOBAL STORAGE
# -----------------------------

camera_urls = []

caps = []

latest_frames = {}

camera_alerts = {}

# -----------------------------
# CAMERA AUTO DETECTION
# -----------------------------

def check_camera(ip):

    url = f"http://{ip}:8080/video"

    try:

        response = requests.get(
            f"http://{ip}:8080",
            timeout=1
        )

        if response.status_code == 200:

            print(f"Camera Found: {url}")

            camera_urls.append(url)

    except Exception:

        pass


# -----------------------------
# NETWORK SCAN
# -----------------------------

with ThreadPoolExecutor(max_workers=50) as executor:

    for i in range(1, 255):

        ip = base_ip + str(i)

        executor.submit(check_camera, ip)

print(f"Total Cameras Found: {len(camera_urls)}")

# -----------------------------
# OPEN CAMERAS
# -----------------------------

for url in camera_urls:

    cap = cv2.VideoCapture(url)

    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if cap.isOpened():

        print(f"Connected: {url}")

        caps.append(cap)

# -----------------------------
# CAMERA READER THREAD
# -----------------------------

def camera_reader(camera_id, cap):

    global latest_frames
    global camera_alerts

    while True:

        success, frame = cap.read()

        if not success:

            print(f"Camera {camera_id} disconnected")

            time.sleep(1)

            continue

        # Resize for faster AI
        small = cv2.resize(frame, (640, 480))

        # -----------------------------
        # HUMAN DETECTION
        # -----------------------------

        boxes, weights = hog.detectMultiScale(
            small,
            winStride=(8, 8)
        )

        alert = "SAFE"

        for (x, y, w, h) in boxes:

            cv2.rectangle(
                small,
                (x, y),
                (x + w, y + h),
                (0, 0, 255),
                3
            )

            alert = "PERSON DETECTED"

        # Store alert
        camera_alerts[camera_id] = alert

        # Store latest frame
        latest_frames[camera_id] = small

        time.sleep(0.03)

# -----------------------------
# START THREADS
# -----------------------------

for i, cap in enumerate(caps):

    threading.Thread(
        target=camera_reader,
        args=(i, cap),
        daemon=True
    ).start()

# -----------------------------
# VIDEO GENERATOR
# -----------------------------

def generate_frames(camera_id):

    while True:

        if camera_id not in latest_frames:

            time.sleep(0.1)

            continue

        frame = latest_frames[camera_id]

        ret, buffer = cv2.imencode('.jpg', frame)

        frame = buffer.tobytes()

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )

        time.sleep(0.03)

# -----------------------------
# DASHBOARD
# -----------------------------

@app.route('/')
def index():

    cameras = []

    for i in range(len(caps)):

        cameras.append(f"/video/{i}")

    return render_template(
        "index.html",
        cameras=cameras,
        alerts=camera_alerts
    )

# -----------------------------
# VIDEO ROUTE
# -----------------------------

@app.route('/video/<int:camera_id>')
def video(camera_id):

    return Response(
        generate_frames(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

# -----------------------------
# START SERVER
# -----------------------------

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        threaded=True
    )