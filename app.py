from flask import Flask, render_template, Response
import cv2
import threading
import time

app = Flask(__name__)

# -----------------------------------
# AI HUMAN DETECTOR
# -----------------------------------

hog = cv2.HOGDescriptor()

hog.setSVMDetector(
    cv2.HOGDescriptor_getDefaultPeopleDetector()
)

# -----------------------------------
# YOUR CAMERA URLS
# -----------------------------------

camera_urls = [

    "http://172.29.0.199:8080/video",
    "http://172.29.0.59:8080/video",
    "http://172.29.0.173:8080/video",
    "http://172.29.0.207:8080/video"

]

print(f"Total Cameras Configured: {len(camera_urls)}")

# -----------------------------------
# GLOBAL STORAGE
# -----------------------------------

caps = []

latest_frames = {}

camera_alerts = {}

# -----------------------------------
# OPEN CAMERAS
# -----------------------------------

for url in camera_urls:

    print(f"Connecting to: {url}")

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

    while True:

        success, frame = cap.read()

        if not success:

            print(f"Camera {camera_id + 1} disconnected")

            camera_alerts[camera_id] = "CAMERA OFFLINE"

            time.sleep(1)

            continue

        # Resize frame

        frame = cv2.resize(frame, (640, 480))

        # -----------------------------------
        # HUMAN DETECTION
        # -----------------------------------

        boxes, weights = hog.detectMultiScale(
            frame,
            winStride=(8, 8)
        )

        alert = "SAFE"

        for (x, y, w, h) in boxes:

            cv2.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                (0, 0, 255),
                3
            )

            cv2.putText(
                frame,
                "PERSON DETECTED",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

            alert = "PERSON DETECTED"

        # -----------------------------------
        # STATUS TEXT
        # -----------------------------------

        color = (0, 255, 0)

        if alert != "SAFE":

            color = (0, 0, 255)

        cv2.putText(
            frame,
            f"STATUS: {alert}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            color,
            3
        )

        # SAVE ALERT

        camera_alerts[camera_id] = alert

        # SAVE FRAME

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

        ret, buffer = cv2.imencode('.jpg', frame)

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

    return render_template(
        "index.html",
        cameras=cameras,
        alerts=camera_alerts
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