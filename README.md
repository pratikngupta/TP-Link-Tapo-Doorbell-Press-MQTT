# TP-Link Tapo Doorbell Press MQTT Sniffer

[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](docker-compose.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-MQTT%20Discovery-41BDF5.svg)](https://www.home-assistant.io/)
[![Scrypted](https://img.shields.io/badge/Scrypted-HomeKit%20Chime-9b59b6.svg)](https://www.scrypted.app/)

Local MQTT event bridge for **TP-Link Tapo Video Doorbells** (Tapo D130, D235, and companion chimes).

Inspired by the original concept from [debian-D235-Doorbell-Press-MQTT](https://github.com/AriaGen/debian-D235-Doorbell-Press-MQTT) by AriaGen.

Captures the local UDP broadcast on port `20005` transmitted when the physical button is pressed and publishes instantaneous MQTT events for **Home Assistant** automations and **Scrypted / Apple HomeKit** doorbell chimes and camera popups.

> [!TIP]
> For a deep dive into the packets, debouncing, and process flow, see [**ARCHITECTURE.md**](./ARCHITECTURE.md).

---

## Quick Start (Docker Compose)

### 1. Clone the Repository

```bash
git clone https://github.com/pratikngupta/tapo-door-bell.git
cd tapo-door-bell
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
nano .env
```

Set your MQTT broker and password:

```ini
# MQTT Broker Settings
MQTT_BROKER=10.0.0.1
MQTT_PORT=1883
MQTT_TOPIC=doorbell/press
MQTT_USER=homeassistant
MQTT_PASS=your_mqtt_password_here

# Doorbell Settings (auto accepts packets from any device/relay on port 20005)
DOORBELL_IP=auto
UDP_PORT=20005
PULSE_TIME=2.0
COOLDOWN_TIME=5.0

# Home Assistant Auto-Discovery
HA_DISCOVERY=true
HA_DISCOVERY_PREFIX=homeassistant
```

### 3. Start the Container

```bash
docker compose up -d --build
```

> [!NOTE]
> The container uses `network_mode: host` to bind directly to the host's network interfaces, allowing it to receive local UDP broadcast packets without Docker NAT restrictions.

### 4. View Live Logs

```bash
docker compose logs -f
```

You should see:

```text
[MQTT] Connecting to broker YOUR_BROKER_IP:1883 (user: homeassistant)...
[MQTT] Connected with result code 0
[MQTT] Published Home Assistant discovery config to homeassistant/binary_sensor/tapo_doorbell/press/config
[MQTT] Published initial 'off' to doorbell/press
[UDP] Listening for broadcast packets on port 20005 (Filtering for IP: ANY (auto-detect))...
```

---

## Container Management

| Action | Command |
| :--- | :--- |
| **View logs** | `docker compose logs -f` |
| **Restart** | `docker compose restart` |
| **Stop** | `docker compose down` |
| **Update** | `git pull && docker compose up -d --build` |

---

## Cross-Subnet / VLAN Setup

If your doorbell is on a **separate IoT network** and your Docker host is on your **main LAN**, the router needs to relay UDP broadcasts between subnets. See [ARCHITECTURE.md](./ARCHITECTURE.md) for router-specific instructions.

---

## Home Assistant Integration

With `HA_DISCOVERY=true`, Home Assistant automatically detects the doorbell:

1. Go to **Settings** → **Devices & Services** → **MQTT** → **Devices**.
2. Look for **Tapo Doorbell**.
3. **Entity:** `binary_sensor.tapo_doorbell_press`
   * State: `off` (Clear)
   * State when pressed: `on` (Detected) for 2.0 seconds.

---

## Scrypted (Apple HomeKit) Integration

To trigger Apple TV doorbell video popups, HomePod chimes, and iPhone notifications:

1. In Scrypted, install the **MQTT** plugin and click **Add Device** (select `button.ts`).
2. Under **General Settings**:
   * **Subscription URL:** `mqtt://YOUR_BROKER_IP:1883/doorbell`
   * **Username:** `homeassistant`
   * **Password:** *(your MQTT password)*
3. Under the **EDIT** tab, verify the script:

   ```typescript
   mqtt.subscribe({
       'press': value => {
           device.binaryState = value.text === "on";
       }
   });
   mqtt.handleTypes(ScryptedInterface.BinarySensor);
   ```

4. In Scrypted, go to your **Doorbell Camera** (Tapo D130) → **Extensions** (or **Doorbell**) → set **Linked Doorbell Button** to this device.

---

## Configuration Reference

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `MQTT_BROKER` | `10.0.0.1` | MQTT broker IP or hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `doorbell/press` | Topic where press state is published |
| `MQTT_USER` | `homeassistant` | MQTT username |
| `MQTT_PASS` | `""` | MQTT password |
| `DOORBELL_IP` | `auto` | Target IP, comma-separated list, or `auto` for any sender |
| `UDP_PORT` | `20005` | Port the Tapo doorbell broadcasts to |
| `PULSE_TIME` | `2.0` | Seconds to hold `"on"` before returning to `"off"` |
| `COOLDOWN_TIME` | `5.0` | Seconds to ignore duplicate burst packets from a single press |
| `HA_DISCOVERY` | `true` | Publish Home Assistant MQTT auto-discovery metadata |
| `HA_DISCOVERY_PREFIX` | `homeassistant` | Home Assistant MQTT discovery prefix |
