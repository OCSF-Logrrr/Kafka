FROM python:3.11-slim

# 1) 작업 디렉터리
WORKDIR /app

# 2) transform.py 복사
COPY transform.py .

# 3) kafka-python 설치
RUN pip install --no-cache-dir kafka-python

# 4) unbuffered 모드로 실행
CMD ["python", "-u", "transform.py"]
