"""Smoke-test publisher.

Usage:
    python scripts/mqtt_pub_sample.py <topic> <payload> [--host HOST] [--port PORT]

Example:
    python scripts/mqtt_pub_sample.py devices/hello '{"msg":"world"}'
"""
import argparse
import sys

import paho.mqtt.publish as publish


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a single MQTT message.")
    parser.add_argument("topic")
    parser.add_argument("payload")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    args = parser.parse_args()

    publish.single(
        args.topic,
        payload=args.payload,
        hostname=args.host,
        port=args.port,
        qos=args.qos,
    )
    print(f"Published to {args.topic}: {args.payload}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
