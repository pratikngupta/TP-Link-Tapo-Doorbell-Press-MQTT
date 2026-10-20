# TP-Link Tapo D235 Doorbell Press MQTT Sniffer

Captures UDP broadcast events on port `20005` emitted when the **TP-Link Tapo D235** doorbell button is pressed, and publishes the event to an MQTT broker for instant Home Assistant integration with zero latency.

---

## Architecture & How It Works

1. When someone presses the physical doorbell button, the Tapo D235 broadcasts a UDP packet on destination port **`20005`**.
2. This service listens on UDP port `20005`, matches the doorbell's IP address (or accepts any if set to `auto`), and publishes:
   - `on` to `doorbell/press`
   - Sleeps for `PULSE_TIME` (default: 2s)
   - `off` to `doorbell/press`
3. Automatically publishes Home Assistant MQTT Discovery configuration, so Home Assistant creates a native `binary_sensor` with `device_class: doorbell` automatically.

> [!IMPORTANT]
> **Subnet / VLAN Note:**
> UDP broadcast packets do not traverse standard routers/subnets by default. If your doorbell is on an IoT VLAN (e.g. `10.0.10.112`) and your Debian server is on `10.0.0.x`, you must either:
> 1. Attach a virtual interface/VLAN on your Debian server to the IoT subnet (`10.0.10.0/24`), OR
> 2. Enable a UDP broadcast relay on your router (e.g., `udp-broadcast-relay` on UniFi, pfSense, OPNsense, or OpenWrt forwarding UDP port `20005` between VLANs).

---

## Quick Setup with Docker Compose (Recommended)

Running with Docker Compose is the easiest and cleanest way to run and manage the service on Debian/Linux.

### 1. Clone the Repository

```bash
git clone https://github.com/pratikngupta/tapo-door-bell.git
cd tapo-door-bell
```

### 2. Configure Environment

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` to set your MQTT password and settings:
```bash
nano .env
```

```ini
# MQTT Broker Details
MQTT_BROKER=10.0.0.228
MQTT_PORT=1883
MQTT_TOPIC=doorbell/press
MQTT_USER=homeassistant
MQTT_PASS=your_mqtt_password_here

# Doorbell Settings
# Tapo D235 IP address. Leave blank or set to 'auto' to accept UDP packets from any IP on port 20005
DOORBELL_IP=10.0.10.112
UDP_PORT=20005
PULSE_TIME=2.0

# Home Assistant Auto-Discovery (true/false)
HA_DISCOVERY=true
HA_DISCOVERY_PREFIX=homeassistant
```

### 3. Start the Container

```bash
docker compose up -d --build
```

> [!NOTE]
> The `docker-compose.yml` uses `network_mode: host` so the container can directly bind to port `20005` and receive physical LAN UDP broadcast packets from the doorbell without Docker NAT restrictions.

### 4. Manage Container

- **View Live Logs:**
  ```bash
  docker compose logs -f
  ```
- **Restart Container:**
  ```bash
  docker compose restart
  ```
- **Stop Container:**
  ```bash
  docker compose down
  ```
- **Update Container:**
  ```bash
  git pull
  docker compose up -d --build
  ```

---

## Alternative: Native Linux Service (systemd)

If you prefer to run it natively without Docker:

```bash
sudo bash install.sh
sudo nano /etc/mqttsniffer/mqttsniffer.env
sudo systemctl restart mqtt-sniffer
sudo journalctl -u mqtt-sniffer -f
```

---

## Home Assistant Integration

### Option 1: Automatic Discovery (Default)

With `HA_DISCOVERY=true` enabled, the sniffer automatically publishes discovery metadata to `homeassistant/binary_sensor/tapo_d235_doorbell/config`.

Home Assistant will automatically discover:
- **Entity**: `binary_sensor.tapo_doorbell_press`
- **Device Class**: `doorbell`

### Option 2: Manual YAML Configuration

If you do not use MQTT discovery, you can add this to your Home Assistant `configuration.yaml`:

```yaml
mqtt:
  binary_sensor:
    - name: "Tapo Doorbell Press"
      state_topic: "doorbell/press"
      payload_on: "on"
      payload_off: "off"
      device_class: doorbell
```

---

## Troubleshooting & Verification

1. **Verify MQTT connectivity from the host:**
   ```bash
   mosquitto_sub -h 10.0.0.228 -p 1883 -u homeassistant -P "<YOUR_PASSWORD>" -t "doorbell/#" -v
   ```
2. **Verify UDP broadcast packets are reaching your host:**
   Press the doorbell button and check if packets arrive on port 20005:
   ```bash
   sudo tcpdump -n -i any udp port 20005
   ```
   If no packets appear when pressing the button, your router is blocking UDP broadcasts across subnets/VLANs (see the [Subnet / VLAN Note](#architecture--how-it-works)).
