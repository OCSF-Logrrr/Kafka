import os
import json
import time
import sys
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

# 설정 읽기
brokers    = os.getenv("BROKERS", "").split(",")
raw_topic  = os.getenv("RAW_TOPIC", "raw-logs")
ocsf_topic = os.getenv("OCSF_TOPIC", "ocsf-logs")

print(f"🔄 Transform service starting: {raw_topic} → {ocsf_topic}", flush=True)

# 브로커 연결 재시도
while True:
    try:
        consumer = KafkaConsumer(
            raw_topic,
            bootstrap_servers=brokers,
            group_id="transformer-group",       # <-- 그룹 아이디 추가
            auto_offset_reset='earliest',
            enable_auto_commit=True,            # <-- 오프셋 자동 커밋
            value_deserializer=lambda b: json.loads(b)
        )
        print("✅ Connected to Kafka brokers:", brokers, flush=True)
        break
    except NoBrokersAvailable:
        print("⚠️  Kafka brokers not available yet, retrying in 5s...", file=sys.stderr, flush=True)
        time.sleep(5)

producer = KafkaProducer(
    bootstrap_servers=brokers,
    value_serializer=lambda o: json.dumps(o).encode()
)

# 메시지 처리 루프
for msg in consumer:
    print("▶ [DEBUG] raw received:", msg.value, flush=True)
    raw = msg.value

    # OCSF 포맷으로 매핑
    ocfs = {
        "ecs_version": "1.12.0",
        "event": {
            "category": raw.get("level", ""),
            "dataset": raw.get("app", "")
        },
        "host": {
            "name": raw.get("host", "")
        },
        "message": raw.get("message", ""),
        "timestamp": raw.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    }

    # 전송
    future = producer.send(ocsf_topic, ocfs)
    try:
        # 즉시 플러시로 전송 보장
        producer.flush(timeout=10)
        print("✔ [DEBUG] ocsf sent:", ocfs, flush=True)
    except Exception as e:
        print("❌ [ERROR] failed to send OCSF message:", e, flush=True)

