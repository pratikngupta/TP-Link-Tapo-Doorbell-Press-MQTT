#!/usr/bin/env python3
import json
import os
import socket
import time
import paho.mqtt.client as mqtt

# --- Configuration (defaults or from environment variables) ---
MQTT_BROKER = os.getenv("MQTT_BROKER", "10.0.0.1")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC  = os.getenv("MQTT_TOPIC", "doorbell/press")
MQTT_USER   = os.getenv("MQTT_USER", "homeassistant")
MQTT_PASS   = os.getenv("MQTT_PASS", "")
AVAILABILITY_TOPIC = os.getenv("AVAILABILITY_TOPIC", "doorbell/status")

# Parse DOORBELL_IP: can be 'auto', 'any', empty, a single IP, or comma-separated list
raw_doorbell_ip = os.getenv("DOORBELL_IP", "auto").strip()
if raw_doorbell_ip.lower() in ("auto", "any", ""):
    allowed_ips = set()
else:
    allowed_ips = {ip.strip() for ip in raw_doorbell_ip.split(",") if ip.strip()}

UDP_PORT      = int(os.getenv("UDP_PORT", "20005"))
PULSE_TIME    = float(os.getenv("PULSE_TIME", "2.0"))      # Seconds for "on" pulse
COOLDOWN_TIME = float(os.getenv("COOLDOWN_TIME", "5.0"))  # Seconds to ignore repeated burst packets
HA_DISCOVERY  = os.getenv("HA_DISCOVERY", "true").lower() in ("true", "1", "yes")
HA_DISCOVERY_PREFIX = os.getenv("HA_DISCOVERY_PREFIX", "homeassistant")


# Precompute discovery payload — only needed once per run
HA_DISCOVERY_TOPIC = f"{HA_DISCOVERY_PREFIX}/binary_sensor/tapo_doorbell/press/config"
HA_DISCOVERY_PAYLOAD = json.dumps({
    "name": "Tapo Doorbell Press",
    "unique_id": "tapo_doorbell_press",
    "object_id": "tapo_doorbell_press",
    "state_topic": MQTT_TOPIC,
    "payload_on": "on",
    "payload_off": "off",
    "icon": "mdi:bell",
    "availability_topic": AVAILABILITY_TOPIC,
    "payload_available": "online",
    "payload_not_available": "offline",
    "device": {
        "identifiers": ["tapo_doorbell_device"],
        "name": "Tapo Doorbell",
        "model": "D130",
        "manufacturer": "TP-Link Tapo",
        "sw_version": "1.0.0"
    }
})


# --- Unified MQTT callbacks (paho-mqtt v1 & v2 compatible) ---
def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Connected with result code {rc}")
    client.publish(AVAILABILITY_TOPIC, payload="online", qos=1, retain=True)
    if HA_DISCOVERY:
        client.publish(HA_DISCOVERY_TOPIC, payload=HA_DISCOVERY_PAYLOAD, qos=1, retain=True)
        print(f"[MQTT] Published Home Assistant discovery config to {HA_DISCOVERY_TOPIC}")
    client.publish(MQTT_TOPIC, payload="off", qos=1, retain=True)
    print(f"[MQTT] Published initial 'off' to {MQTT_TOPIC}")


def on_disconnect(client, userdata, rc, properties=None, *args):
    print(f"[MQTT] Disconnected (reason={rc}), retrying in 5s")
    time.sleep(5)
    try:
        client.reconnect()
    except Exception as e:
        print(f"[MQTT] Reconnect failed: {e}")


# --- Color output helpers ---
def _print(text: str, color: str = "") -> None:
    colors = {
        "red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
        "blue": "\033[94m", "magenta": "\033[95m", "cyan": "\033[96m",
        "white": "\033[97m", "reset": "\033[0m",
    }
    if color in colors:
        print(f"{colors[color]}{text}{colors['reset']}")
    else:
        print(text)


def banner() -> None:
    _print("╔══════════════════════════════════════════╗", "cyan")
    _print("║  Tapo Doorbell MQTT Sniffer v1.0.0      ║", "cyan")
    _print("║  Local UDP to MQTT bridge   ║", "cyan")
    _print("╚══════════════════════════════════════════╝", "cyan")
    _print()

    width = 46
    def _line(label: str, value: str, color: str = "yellow") -> None:
        padded_value = value.ljust(width - len(label) - 2)
        _print(f"  {label}: {padded_value}", color)

    _line("Broker", f"{MQTT_BROKER}:{MQTT_PORT}")
    _line("User", f"{MQTT_USER or 'anonymous'}")
    _line("Event topic", MQTT_TOPIC)
    _line("UDP port", str(UDP_PORT))
    _line("Pulse duration", f"{PULSE_TIME}s")
    _line("Cooldown", f"{COOLDOWN_TIME}s")
    if allowed_ips:
        _line("Filter IPs", ", ".join(sorted(allowed_ips)))
    else:
        _line("Filter IPs", "ANY (auto-detect)")
    _line("HA Discovery", "Enabled" if HA_DISCOVERY else "Disabled")
    _print()


# --- MQTT setup ---
if hasattr(mqtt, "CallbackAPIVersion"):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
else:
    client = mqtt.Client()

client.on_connect = on_connect
client.on_disconnect = on_disconnect

if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS if MQTT_PASS else None)

client.will_set(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)

banner()
print(f"[MQTT] Connecting to broker {MQTT_BROKER}:{MQTT_PORT} (user: {MQTT_USER or 'anonymous'})...")
client.connect_async(MQTT_BROKER, MQTT_PORT)
client.loop_start()

# --- UDP listener ---
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
except (AttributeError, OSError):
    pass

sock.bind(("", UDP_PORT))
target_info = ", ".join(sorted(allowed_ips)) if allowed_ips else "ANY (auto-detect)"
print(f"[UDP] Listening for broadcast packets on port {UDP_PORT} (Filtering for IP: {target_info})...")
_print(f"  Status: ✓ Running (PID {os.getpid()})", "green")
_print()

last_press_time = 0.0

try:
    while True:
        data, addr = sock.recvfrom(1024)
        sender_ip = addr[0]

        if allowed_ips and sender_ip not in allowed_ips:
            print(f"[UDP] Packet from {addr[0]}:{addr[1]} ({len(data)} bytes) – IGNORED (IP {sender_ip} not in {allowed_ips}). Tip: Set DOORBELL_IP=auto in .env to accept.")
            continue

        now = time.time()
        if now - last_press_time < COOLDOWN_TIME:
            continue

        last_press_time = now
        _print(f"  ✓ Doorbell detected at {sender_ip}:{addr[1]}", "green")
        print(f"[UDP] Packet from {addr[0]}:{addr[1]} ({len(data)} bytes) – Doorbell pressed!")

        # 1. Trigger ON state
        client.publish(MQTT_TOPIC, payload="on", qos=1, retain=False)
        time.sleep(PULSE_TIME)

        # 2. Reset to OFF state
        client.publish(MQTT_TOPIC, payload="off", qos=1, retain=True)

        # 3. Drain OS kernel socket buffer (catches burst packets that queued during sleep)
        sock.setblocking(False)
        try:
            while True:
                sock.recvfrom(1024)
        except (BlockingIOError, socket.error):
            pass
        finally:
            sock.setblocking(True)

except KeyboardInterrupt:
    print("\n[Sniffer] Exiting cleanly...")
finally:
    try:
        client.publish(AVAILABILITY_TOPIC, payload="offline", qos=1, retain=True)
    except Exception:
        pass
    client.loop_stop()
    client.disconnect()
    sock.close()
