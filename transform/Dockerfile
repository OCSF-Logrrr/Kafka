FROM python:3.11-slim

# 작업 디렉터리
WORKDIR /app

# transform.py 복사
COPY transform.py .

# kafka-python 설치
RUN pip install --no-cache-dir kafka-python

# unbuffered 모드로 실행
CMD ["python", "-u", "transform.py"]
