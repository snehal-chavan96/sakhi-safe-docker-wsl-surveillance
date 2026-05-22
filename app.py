import cv2
import requests
from concurrent.futures import ThreadPoolExecutor

print("Starting SakhiSafe Auto Camera Detection...")

camera_urls = []

# Scan local network
base_ip = "192.168.2."

def check_camera(ip):
    url = f"http://{ip}:8080/video"

    try:
        response = requests.get(f"http://{ip}:8080", timeout=1)

        if response.status_code == 200:
            print(f"Camera Found: {url}")
            camera_urls.append(url)

    except:
        pass

# Scan all IPs
with ThreadPoolExecutor(max_workers=50) as executor:
    for i in range(1, 255):
        ip = base_ip + str(i)
        executor.submit(check_camera, ip)

print(f"\nTotal Cameras Found: {len(camera_urls)}")

# Open all detected cameras
caps = []

for url in camera_urls:
    cap = cv2.VideoCapture(url)

    if cap.isOpened():
        print(f"Connected: {url}")
        caps.append(cap)

frame_count = 0

while True:

    for idx, cap in enumerate(caps):

        ret, frame = cap.read()

        if not ret:
            continue

        frame_count += 1

        print(f"Camera {idx+1} Frame {frame_count}")

        # Save sample frame
        if frame_count % 100 == 0:
            cv2.imwrite(f"camera_{idx+1}.jpg", frame)

print("System Running...")