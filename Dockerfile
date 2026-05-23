FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0

RUN pip install --no-cache-dir \
    flask \
    opencv-python-headless \
    numpy \
    requests \
    ultralytics

EXPOSE 5000

CMD ["python", "app.py"]