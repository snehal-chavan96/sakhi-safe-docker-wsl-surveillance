FROM python:3.12

WORKDIR /app

COPY . .

RUN apt-get update && apt-get install -y libgl1

RUN pip install flask opencv-python numpy requests

CMD ["python", "app.py"]