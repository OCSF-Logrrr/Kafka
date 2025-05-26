import os, json, time
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable
import sys

brokers    = os.getenv("BROKERS").split(",")
raw_topic  = os.getenv("RAW_TOPIC", "raw-logs")
ocsf_topic = os.getenv("OCSF_TOPIC", "ocsf-logs")

print(f"🔄 Transform service starting: {raw_topic} → {ocsf_topic}")
while True:
    try:
        consumer = KafkaConsumer(
            raw_topic,
            bootstrap_servers=brokers,
            auto_offset_reset='earliest',
            value_deserializer=lambda b: json.loads(b)
        )
        print("✅ Connected to Kafka brokers:", brokers)
        break
    except NoBrokersAvailable:
        print("⚠️  Kafka brokers not available yet, retrying in 5s...", file=sys.stderr)
        time.sleep(5)

producer = KafkaProducer(
    bootstrap_servers=brokers,
    value_serializer=lambda o: json.dumps(o).encode()
)

for msg in consumer:
    raw = msg.value
    ocfs = {
        "ecs_version": "1.12.0",
        "event": {"category": raw.get("level", ""), "dataset": raw.get("app", "")},
        "host": {"name": raw.get("host", "")},
        "message": raw.get("message", ""),
        "timestamp": raw.get("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    }
    producer.send(ocsf_topic, ocfs)
