from ultralytics import YOLO
import cv2

model = YOLO("yolov8n.pt")

url = "http://50.0.1.163:8080/video"

cap = cv2.VideoCapture(
    url,
    cv2.CAP_FFMPEG
)

if not cap.isOpened():

    print("Camera cannot open")
    exit()

while True:

    success, frame = cap.read()

    if not success:

        print("Frame failed")
        break

    # Resize for speed
    frame = cv2.resize(
        frame,
        (640, 360)
    )

    # YOLO Detection
    results = model(frame)

    # Draw detections
    annotated_frame = results[0].plot()

    # SAVE OUTPUT FRAME
    cv2.imwrite(
        "output.jpg",
        annotated_frame
    )

    print("Detection working")

    break

cap.release()