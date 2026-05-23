from flask import Flask, render_template, Response
import cv2
import threading
import time
import requests
import os
import numpy as np

from concurrent.futures import ThreadPoolExecutor

# -----------------------------------
# YOLOv8
# -----------------------------------

from ultralytics import YOLO

# -----------------------------------
# FLASK APP
# -----------------------------------

app = Flask(__name__)

# -----------------------------------
# CREATE ALERTS FOLDER
# -----------------------------------

if not os.path.exists("alerts"):

    os.makedirs("alerts")

# -----------------------------------
# AI HUMAN DETECTOR (BACKUP)
# -----------------------------------

hog = cv2.HOGDescriptor()

hog.setSVMDetector(
    cv2.HOGDescriptor_getDefaultPeopleDetector()
)

# -----------------------------------
# YOLO MODEL
# -----------------------------------

model = YOLO("yolov8n.pt")

# -----------------------------------
# WEAPON CLASSES
# -----------------------------------

WEAPON_CLASSES = [
    "knife",
    "scissors",
    "baseball bat"
]

# -----------------------------------
# CAMERA RANGE
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
# CONNECT CAMERA
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
# START SCANNER THREAD
# -----------------------------------

threading.Thread(
    target=background_scanner,
    daemon=True
).start()

# -----------------------------------
# SAVE ALERT
# -----------------------------------

def save_alert(camera_id, alert, frame):

    current_time = time.time()

    last_time = last_saved_time.get(
        camera_id,
        0
    )

    # SAVE EVERY 10 SECONDS
    if current_time - last_time < 10:

        return

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

    print(f"Snapshot Saved: {filename}")

    incident_logs.insert(0, {

        "camera": camera_id + 1,

        "alert": alert,

        "time": timestamp,

        "image": filename

    })

    last_saved_time[camera_id] = current_time

# -----------------------------------
# CAMERA READER
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

        # -----------------------------------
        # OFFLINE CAMERA
        # -----------------------------------

        if not success:

            print(f"Camera {camera_id + 1} Offline")

            camera_alerts[camera_id] = "CAMERA OFFLINE"

            camera_status[camera_id] = "OFFLINE"

            offline_frame = np.zeros(
                (240, 320, 3),
                dtype=np.uint8
            )

            cv2.putText(
                offline_frame,
                "CAMERA OFFLINE",
                (40, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )

            latest_frames[camera_id] = offline_frame

            time.sleep(1)

            continue

        # -----------------------------------
        # CAMERA ONLINE
        # -----------------------------------

        camera_status[camera_id] = "ONLINE"

        frame = cv2.resize(
            frame,
            (640, 480)
        )

        frame_count += 1

        alert = "SAFE"

        # -----------------------------------
        # YOLO AI DETECTION
        # -----------------------------------

        if frame_count % 10 == 0:

            results = model(
                frame,
                verbose=False
            )

            for result in results:

                boxes = result.boxes

                for box in boxes:

                    cls_id = int(box.cls[0])

                    class_name = (
                        model.names[cls_id]
                    )

                    x1, y1, x2, y2 = map(
                        int,
                        box.xyxy[0]
                    )

                    confidence = float(
                        box.conf[0]
                    )

                    # -----------------------------------
                    # PERSON DETECTION
                    # -----------------------------------

                    if class_name == "person":

                        alert = "PERSON DETECTED"

                        color = (0, 255, 255)

                        cv2.rectangle(
                            frame,
                            (x1, y1),
                            (x2, y2),
                            color,
                            2
                        )

                        cv2.putText(
                            frame,
                            "PERSON DETECTED",
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            color,
                            2
                        )

                    # -----------------------------------
                    # WEAPON DETECTION
                    # -----------------------------------

                    if class_name in WEAPON_CLASSES:

                        alert = "WEAPON DETECTED"

                        color = (0, 0, 255)

                        cv2.rectangle(
                            frame,
                            (x1, y1),
                            (x2, y2),
                            color,
                            3
                        )

                        cv2.putText(
                            frame,
                            f"{class_name.upper()} DETECTED",
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            color,
                            2
                        )

                        # SAVE ALERT
                        save_alert(
                            camera_id,
                            alert,
                            frame
                        )

        # -----------------------------------
        # FACE COVERED DETECTION
        # -----------------------------------

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades +
            'haarcascade_frontalface_default.xml'
        )

        faces = face_cascade.detectMultiScale(
            gray,
            1.1,
            4
        )

        if len(faces) == 0:

            if alert == "SAFE":

                alert = "FACE COVERED"

                cv2.putText(
                    frame,
                    "FACE NOT VISIBLE",
                    (20, 440),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 0, 255),
                    2
                )

        # -----------------------------------
        # FPS
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

            color = (0, 255, 255)

        elif alert == "WEAPON DETECTED":

            color = (0, 0, 255)

        elif alert == "FACE COVERED":

            color = (255, 0, 255)

        elif alert == "CAMERA OFFLINE":

            color = (128, 128, 128)

        # -----------------------------------
        # OVERLAYS
        # -----------------------------------

        cv2.putText(
            frame,
            f"STATUS: {alert}",
            (20, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            color,
            2
        )

        cv2.putText(
            frame,
            f"FPS: {camera_fps.get(camera_id, 0)}",
            (20, 65),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 0),
            2
        )

        cv2.putText(
            frame,
            f"CAMERA {camera_id + 1}",
            (20, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            time.strftime("%H:%M:%S"),
            (20, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        # -----------------------------------
        # SAVE PERSON DETECTION
        # -----------------------------------

        if alert == "PERSON DETECTED":

            save_alert(
                camera_id,
                alert,
                frame
            )

        if alert == "FACE COVERED":

            save_alert(
                camera_id,
                alert,
                frame
            )

        # -----------------------------------
        # SAVE DATA
        # -----------------------------------

        camera_alerts[camera_id] = alert

        latest_frames[camera_id] = frame

        time.sleep(0.03)

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
# VIDEO ROUTE
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