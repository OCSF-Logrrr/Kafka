# Kafka

## 목차

* [프로젝트 개요](#프로젝트-개요)
* [사전 준비 사항](#사전-준비-사항)
* [리포지토리 클론 및 구조](#리포지토리-클론-및-구조)
* [docker-compose.yml 검토 및 수정](#docker-composeyml-검토-및-수정)
* [transform 코드 및 Dockerfile](#transform-코드-및-dockerfile)
* [실행 및 검증](#실행-및-검증)
* [외부 데이터 흐름 테스트](#외부-데이터-흐름-테스트)
* [운영 및 확장](#운영-및-확장)

## 프로젝트 개요

* **목적**: 원본 로그를 Kafka 토픽(`raw-logs`)으로 수집하고, Python `transform` 서비스가 이를 OCSF 포맷으로 변환하여 별도 토픽(`ocsf-logs`)에 전송
* **구성 요소**:

  * Kafka Broker 3대 (`kafka1`, `kafka2`, `kafka3`)
  * Python 변환 서비스 (`transform` 컨테이너)

## 사전 준비 사항

1. **운영체제**: Ubuntu 24.04
2. **필수 패키지**:

   ```bash
   sudo apt update
   sudo apt install -y apt-transport-https ca-certificates curl software-properties-common git
   ```
3. **Docker & Docker Compose 설치**:

   ```bash
   # Docker
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER
   # Docker Compose
   sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" \
     -o /usr/local/bin/docker-compose
   sudo chmod +x /usr/local/bin/docker-compose
   ```

> 설치 후 터미널 재시작 또는 `newgrp docker` 실행

## 리포지토리 클론 및 구조

```bash
cd ~/projects
git clone https://github.com/OCSF-Logrrr/Kafka.git kafka-transform-server
cd kafka-transform-server
```

```
.
├── docker-compose.yml         # 멀티 브로커 + transform 서비스 정의
└── transform/
    ├── Dockerfile             # transform 컨테이너 빌드 설정
    └── transform.py           # 로그 변환 로직
```

## docker-compose.yml 검토 및 수정

```yaml
version: '3.8'
services:
  # Broker 1
  kafka1:
    image: apache/kafka:3.9.1
    container_name: kafka1
    hostname: kafka1
    environment:
      KAFKA_ENABLE_KRAFT: "true"
      KAFKA_PROCESS_ROLES: "broker,controller"
      KAFKA_NODE_ID: "1"
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
      KAFKA_LISTENERS: "CONTROLLER://:9093,PLAINTEXT://:9092"
      KAFKA_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://<HOST_IP>:9092,CONTROLLER://kafka1:9093"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "3"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: "2"
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: "3"
    ports:
      - "9092:9092"
      - "9093:9093"
    networks:
      - kt-net

  # Broker 2
  kafka2:
    image: apache/kafka:3.9.1
    container_name: kafka2
    hostname: kafka2
    environment:
      KAFKA_ENABLE_KRAFT: "true"
      KAFKA_PROCESS_ROLES: "broker,controller"
      KAFKA_NODE_ID: "2"
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
      KAFKA_LISTENERS: "CONTROLLER://:9093,PLAINTEXT://:9092"
      KAFKA_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://<HOST_IP>:9192,CONTROLLER://kafka2:9093"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "3"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: "2"
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: "3"
    ports:
      - "9192:9092"
      - "9193:9093"
    networks:
      - kt-net

  # Broker 3
  kafka3:
    image: apache/kafka:3.9.1
    container_name: kafka3
    hostname: kafka3
    environment:
      KAFKA_ENABLE_KRAFT: "true"
      KAFKA_PROCESS_ROLES: "broker,controller"
      KAFKA_NODE_ID: "3"
      KAFKA_CONTROLLER_QUORUM_VOTERS: "1@kafka1:9093,2@kafka2:9093,3@kafka3:9093"
      KAFKA_LISTENERS: "CONTROLLER://:9093,PLAINTEXT://:9092"
      KAFKA_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
      KAFKA_ADVERTISED_LISTENERS: "PLAINTEXT://<HOST_IP>:9292,CONTROLLER://kafka3:9093"
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: "3"
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: "2"
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: "3"
    ports:
      - "9292:9092"
      - "9293:9093"
    networks:
      - kt-net

  # Python 변환 서비스
  transform:
    build: ./transform
    container_name: transformer
    restart: on-failure
    environment:
      BROKERS: "kafka1:9092,kafka2:9092,kafka3:9092"
      RAW_TOPIC: "raw-logs"
      OCSF_TOPIC: "ocsf-logs"
    depends_on:
      - kafka1
      - kafka2
      - kafka3
    networks:
      - kt-net

networks:
  kt-net:
```

* `<HOST_IP>`: 실제 호스트 IP 또는 `localhost`로 변경
* 포트 매핑(9092/9192/9292) 필요 시 수정
* 환경변수(`BROKERS`, `RAW_TOPIC`, `OCSF_TOPIC`)를 사용 환경에 맞춰 설정

## transform 코드 및 Dockerfile

### transform/Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY transform.py .
RUN pip install --no-cache-dir kafka-python
CMD ["python", "-u", "transform.py"]
```

### transform.py

```python
import os, json, time, sys
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

# 환경 변수
brokers    = os.getenv("BROKERS", "").split(",")
raw_topic  = os.getenv("RAW_TOPIC", "raw-logs")
ocsf_topic = os.getenv("OCSF_TOPIC", "ocsf-logs")

print(f"🔄 Transform service starting: {raw_topic} → {ocsf_topic}", flush=True)

# 브로커 연결 대기
while True:
    try:
        consumer = KafkaConsumer(
            raw_topic,
            bootstrap_servers=brokers,
            group_id="transformer-group",
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda b: json.loads(b)
        )
        print("✅ Connected to Kafka brokers:", brokers, flush=True)
        break
    except NoBrokersAvailable:
        print("⚠️  Kafka brokers not available, retrying in 5s...", file=sys.stderr, flush=True)
        time.sleep(5)

producer = KafkaProducer(
    bootstrap_servers=brokers,
    value_serializer=lambda o: json.dumps(o).encode()
)

for msg in consumer:
    raw = msg.value
    print("▶ [DEBUG] raw received:", raw, flush=True)

    ocfs = {
        "ecs_version": "1.12.0",
        "event": {"category": raw.get("level", ""), "dataset": raw.get("app", "")},
        "host":  {"name": raw.get("host", "")},
        "message": raw.get("message", ""),
        "timestamp": raw.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    }

    producer.send(ocsf_topic, ocfs)
    try:
        producer.flush(timeout=10)
        print("✔ [DEBUG] ocsf sent:", ocfs, flush=True)
    except Exception as e:
        print("❌ [ERROR] failed to send OCSF message:", e, flush=True)
```

## 실행 및 검증

1. 컨테이너 시작:

   ```bash
   docker-compose up -d
   ```
2. 상태 확인:

   ```bash
   docker-compose ps
   ```
3. 토픽 생성:

   ```bash
   docker exec -it kafka1 \
     kafka-topics --create --topic raw-logs --bootstrap-server kafka1:9092 --partitions 3 --replication-factor 3
   kafka-console-producer --topic raw-logs --bootstrap-server kafka1:9092

   ```
4. 로그 모니터링:

   ```bash
   docker logs -f transformer
   ```
5. 데이터 흐름 테스트:

   ```bash
   echo '{"message":"Test","level":"info","app":"demo","host":"localhost"}' \
     | docker exec -i kafka1 \
       kafka-console-producer --topic raw-logs --bootstrap-server kafka1:9092

   docker exec -it kafka1 \
     kafka-console-consumer --topic ocsf-logs --bootstrap-server kafka1:9092 --from-beginning
   ```

## 외부 데이터 흐름 테스트

Vector와 ELK(Logstash/Elasticsearch/Kibana) 환경이 이미 구축되어 있다고 가정합니다. 아래 절차를 통해 로그 변환 및 수집 흐름을 검증하세요.

1. **Vector를 통한 로그 전송**:

   ```bash
   echo '{"message":"Test Log","level":"debug","app":"demo","host":"server1"}' \
     | sudo tee -a /var/log/app/app.log
   ```

   ```bash
   docker exec -it kafka1 \
     kafka-console-consumer --topic raw-logs --bootstrap-server kafka1:9092 --from-beginning --timeout-ms 10000
   ```
2. **transform 서비스 동작 확인**:

   ```bash
   docker logs transformer
   ```
3. **Logstash를 통한 ELK 수집 확인**:

   * Kibana에서 인덱스 패턴 `ocsf-logs-*` 생성 후 Discover 확인
   * Dev Tools에서:

     ```json
     GET ocsf-logs-*/_search
     {"query":{"match":{"message":"Test Log"}}}
     ```
4. **문제 해결 팁**:

   * Kafka 전송 누락: Vector 로그`/var/log/vector/vector.log` 확인 (사용자 환경에 맞게 설정)
   * transform 오류: 컨테이너 내부 예외 메시지 확인
   * Logstash 오류: `/var/log/logstash/logstash-plain.log` 확인 (사용자 환경에 맞게 설정)

## 운영 및 확장

* **토픽 관리**: ACL, 파티션·레플리카 수 조정
* **보안**: TLS/SASL 설정
* **모니터링**: Prometheus/Grafana 연동
* **로그 수집**: Filebeat, Fluentd 등
* 
---

*작성일: 2025-05-26*
