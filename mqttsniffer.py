#!/usr/bin/env python3
import json
import os
import socket
import sys
import time
import paho.mqtt.client as mqtt

# --- Configuration (defaults or from environment variables) ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "10.0.0.228")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "doorbell/press")
MQTT_USER   = os.getenv("MQTT_USER", "homeassistant")
MQTT_PASS   = os.getenv("MQTT_PASS", "")  # Set via environment or mqttsniffer.env
# Parse DOORBELL_IP: can be 'auto', 'any', empty, a single IP, or comma-separated list
raw_doorbell_ip = os.getenv("DOORBELL_IP", "auto").strip()
if raw_doorbell_ip.lower() in ("auto", "any", ""):
    allowed_ips = []
else:
    allowed_ips = [ip.strip() for ip in raw_doorbell_ip.split(",") if ip.strip()]

UDP_PORT    = int(os.getenv("UDP_PORT", "20005"))
PULSE_TIME  = float(os.getenv("PULSE_TIME", "2.0"))  # Seconds for "on" pulse
HA_DISCOVERY = os.getenv("HA_DISCOVERY", "true").lower() in ("true", "1", "yes")
HA_DISCOVERY_PREFIX = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")


def publish_ha_discovery(client):
    """Publish Home Assistant MQTT discovery message for automatic sensor registration."""
    if not HA_DISCOVERY:
        return

    discovery_topic = f"{HA_DISCOVERY_PREFIX}/binary_sensor/tapo_d235_doorbell/config"
    discovery_payload = {
        "name": "Tapo Doorbell Press",
        "unique_id": "tapo_d235_doorbell_press",
        "state_topic": MQTT_TOPIC,
        "payload_on": "on",
        "payload_off": "off",
        "device_class": "doorbell",
        "device": {
            "identifiers": ["tapo_d235_doorbell"],
            "name": "Tapo D235 Doorbell",
            "model": "D235",
            "manufacturer": "TP-Link Tapo"
        }
    }
    try:
        client.publish(discovery_topic, payload=json.dumps(discovery_payload), qos=1, retain=True)
        print(f"[MQTT] Published Home Assistant discovery config to {discovery_topic}")
    except Exception as e:
        print(f"[MQTT] Failed to publish Home Assistant discovery config: {e}")


# --- MQTT callbacks (support both paho-mqtt v1 and v2) ---
def on_connect_v1(client, userdata, flags, rc):
    print(f"[MQTT] Connected with result code {rc}")
    publish_ha_discovery(client)
    client.publish(MQTT_TOPIC, payload="off", qos=0, retain=False)
    print(f"[MQTT] Published initial 'off' to {MQTT_TOPIC}")

def on_connect_v2(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected with result code {rc}")
    publish_ha_discovery(client)
    client.publish(MQTT_TOPIC, payload="off", qos=0, retain=False)
    print(f"[MQTT] Published initial 'off' to {MQTT_TOPIC}")

def on_disconnect_v1(client, userdata, rc):
    print(f"[MQTT] Disconnected (reason={rc}), retrying in 5 s")
    time.sleep(5)
    try:
        client.reconnect()
    except Exception as e:
        print(f"[MQTT] Reconnect failed: {e}")

def on_disconnect_v2(client, userdata, rc, properties=None, *args):
    print(f"[MQTT] Disconnected (reason={rc}), retrying in 5 s")
    time.sleep(5)
    try:
        client.reconnect()
    except Exception as e:
        print(f"[MQTT] Reconnect failed: {e}")


# --- MQTT setup ---
if hasattr(mqtt, "CallbackAPIVersion"):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect_v2
    client.on_disconnect = on_disconnect_v2
else:
    client = mqtt.Client()
    client.on_connect = on_connect_v1
    client.on_disconnect = on_disconnect_v1

if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS if MQTT_PASS else None)

print(f"[MQTT] Connecting to broker {MQTT_BROKER}:{MQTT_PORT} (user: {MQTT_USER or 'anonymous'})...")
client.connect_async(MQTT_BROKER, MQTT_PORT)
client.loop_start()

# --- UDP listener ---
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except (AttributeError, OSError):
    pass

sock.bind(("", UDP_PORT))
target_info = ", ".join(allowed_ips) if allowed_ips else "ANY (auto-detect)"
print(f"[UDP] Listening for broadcast packets on port {UDP_PORT} (Filtering for IP: {target_info})...")

try:
    while True:
        data, addr = sock.recvfrom(1024)
        sender_ip = addr[0]

        is_match = not allowed_ips or sender_ip in allowed_ips

        if is_match:
            print(f"[UDP] Packet from {addr[0]}:{addr[1]} ({len(data)} bytes) – Doorbell pressed!")
            client.publish(MQTT_TOPIC, payload="on", qos=0, retain=False)
            time.sleep(PULSE_TIME)
            client.publish(MQTT_TOPIC, payload="off", qos=0, retain=False)
        else:
            print(f"[UDP] Packet from {addr[0]}:{addr[1]} ({len(data)} bytes) – IGNORED (IP {sender_ip} not in {allowed_ips}). Tip: Set DOORBELL_IP=auto in .env to accept.")

except KeyboardInterrupt:
    print("\n[Sniffer] Exiting cleanly...")
finally:
    client.loop_stop()
    client.disconnect()
    sock.close()
