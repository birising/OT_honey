# WWTP ICS Honeypot

> **WARNING**: This honeypot is for research and educational purposes ONLY. NEVER add exploits or offensive capabilities. Operate only in a controlled environment with appropriate security measures.

A custom ICS honeypot simulating a small wastewater treatment plant (WWTP) for 2-8k population equivalent. Provides a realistic OT infrastructure (deception) with structured JSON logging for security research.

## Architecture

```
                    +-----------------+
  Attacker ------->|   HMI Web :80   |  (Flask + Nginx, login, P&ID, alarms, trends)
                    +--------+--------+
                             |
                    +--------v--------+
                    |  Simulator :8080|  (Process model, tag generator, alarm engine, scenarios)
                    +--------+--------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +--------v--------+
     | PLC Modbus :502  |          | SNMP Agent :161 |
     | (pymodbus TCP)   |          | (pysnmp UDP)    |
     +-----------------+          +-----------------+
```

Four Docker services:

- **simulator** - Core process simulator with tag generator, alarm engine (ISA-18.2), scenario manager, trend buffer
- **plc_modbus** - Modbus TCP server (port 502) mapping ~1030 holding registers, coils, and discrete inputs
- **snmp_agent** - SNMP agent (port 161/udp) with realistic OID values (sysDescr, uptime, cabinet temp, UPS)
- **hmi_web** - Web HMI (port 80) with light industrial theme, SVG P&ID overview, equipment faceplates, Chart.js trends

## Quick Start

### Requirements

- Docker and Docker Compose
- Python 3.11+ (for local tests)

### Launch

```bash
git clone <repo-url>
cd OT_honey
docker-compose up -d
```

### Verify

```bash
# Health check
curl http://localhost:8080/health

# Tag snapshot
curl http://localhost:8080/api/snapshot | python3 -m json.tool | head -40

# Trend data
curl http://localhost:8080/api/trends?range=1h | python3 -m json.tool

# HMI
open http://localhost  # Login: operator/operator123
```

## HMI Screens

| Screen | URL | Description |
|--------|-----|-------------|
| Login | `/` | Username/password authentication |
| Overview | `/overview` | SVG P&ID diagram with clickable equipment faceplates |
| Alarms | `/alarms` | ISA-18.2 alarm summary with acknowledge |
| Trends | `/trends` | Chart.js trend charts (DO, flow, levels, quality) |
| Maintenance | `/maintenance` | Global mode selector, kill switch, equipment status |

### Demo Users

| Username | Password | Role |
|----------|----------|------|
| operator | operator123 | Operator |
| maintenance | maint123 | Maintenance |
| engineering | eng123 | Engineering |

## Simulator API

### GET /health
Health check with mode, kill switch status, active alarms count, trend points.

### GET /api/snapshot
Returns current snapshot of all ~200 tags with value, type, unit, description.

### GET /api/alarms
Returns list of active alarms (ISA-18.2 format).

### POST /api/alarm/acknowledge
Acknowledge an alarm by ID.
```bash
curl -X POST http://localhost:8080/api/alarm/acknowledge \
  -H "Content-Type: application/json" \
  -d '{"id": "alarm-uuid-here"}'
```

### POST /api/write
Write to a whitelisted tag.
```bash
curl -X POST http://localhost:8080/api/write \
  -H "Content-Type: application/json" \
  -d '{"tag": "WWTP01:INFLUENT:PMP101.CMD", "value": true}'
```

### GET /api/trends?range=1h|8h|24h
Returns downsampled trend data (max 360 points) for 15 key process variables.

### GET /POST /api/mode
Get or set global operating mode (AUTO / MANUAL / MAINTENANCE).
```bash
# Get
curl http://localhost:8080/api/mode

# Set
curl -X POST http://localhost:8080/api/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "MANUAL"}'
```

### POST /api/killswitch
Activate or deactivate emergency stop. Activating sets mode to MAINTENANCE and stops all equipment.
```bash
curl -X POST http://localhost:8080/api/killswitch \
  -H "Content-Type: application/json" \
  -d '{"activate": true}'
```

### POST /api/scenario/start | /api/scenario/stop
Start or stop a test scenario.
```bash
curl -X POST http://localhost:8080/api/scenario/start \
  -H "Content-Type: application/json" \
  -d '{"name": "storm"}'
```

### POST /api/reset
Reset simulator to default state.

## Scenarios

| # | Scenario | Duration | Trigger | Effects | Key Alarms |
|---|----------|----------|---------|---------|------------|
| 1 | `storm` | 10 min | Rainfall event | Q_IN rises to 35 m3/h, wet well level rises | HH Wet Well Level (HIGH) |
| 2 | `vfd_fault` | 10 min | VFD failure | BLW201 fault, blower stops, DO drops | VFD Fault Blower (HIGH) |
| 3 | `ph_calibration` | 15 min | Sensor drift | pH302 reads 8.5 (out of range) | pH Out of Range (LOW) |
| 4 | `bypass_risk` | 10 min | High turbidity | TUR501 rises to 15 NTU | High Effluent Turbidity (MEDIUM) |
| 5 | `screen_blockage` | 10 min | Debris blockage | SCR101 DP=0.55 bar, screen fault | Screen Blockage (MEDIUM), Screen Fault (HIGH) |
| 6 | `do_sensor_failure` | 15 min | Sensor stuck | DO stuck at 0.5 mg/L, blower overdrives to 100% | Low Dissolved Oxygen (MEDIUM) |
| 7 | `chemical_overdose` | 10 min | Dosing pump stuck | FeCl3 rate=9.5 L/h, PMP501 stuck in manual ON | Chemical Overdose (HIGH) |

### Scenario Recovery

All scenarios auto-recover after their duration expires. Manual stop is also supported via `/api/scenario/stop`.

## Modbus TCP Register Map

Port **502**, Unit ID 1.

### Holding Registers (FC 3/6) - Analog Values

| Address | Tag | Description | Scale |
|---------|-----|-------------|-------|
| 1000 | Q_IN.PV | Influent flow | x10 (m3/h) |
| 1001 | LT101.PV | Wet well level | x10 (m) |
| 1002 | LT201.PV | Aeration tank level | x10 (m) |
| 1003 | DO301.PV | Dissolved oxygen | x10 (mg/L) |
| 1004 | DO301.SP | DO setpoint | x10 (mg/L) |
| 1005 | pH302.PV | pH | x100 |
| 1006 | TEMP303.PV | Temperature | x10 (C) |
| 1007 | BLW201.SP | Blower speed setpoint | x10 (%) |
| 1008 | BLW201.PV | Blower speed actual | x10 (%) |
| 1009 | LT401.PV | Clarifier level | x10 (m) |
| 1010 | TUR501.PV | Turbidity | x10 (NTU) |
| 1011 | Q_OUT.PV | Effluent flow | x10 (m3/h) |
| 1012 | BLW201.CURRENT | Blower current | x10 (A) |
| 1013 | PMP101.RUNTIME | Pump 101 runtime | x1 (h) |
| 1014 | PMP401.RUNTIME | Pump 401 runtime | x1 (h) |
| 1015 | PMP402.RUNTIME | Pump 402 runtime | x1 (h) |
| 1016 | BLW201.RUNTIME | Blower runtime | x1 (h) |
| 1017 | pH501.PV | Effluent pH | x100 |
| 1018 | COD501.PV | Effluent COD | x10 (mg/L) |
| 1019 | SCR101.DP | Screen differential pressure | x100 (bar) |
| 1020 | GRT201.LEVEL | Grit chamber level | x10 (m) |
| 1021 | LT301.PV | Primary clarifier level | x10 (m) |
| 1022 | PMP301.RUNTIME | Primary pump runtime | x1 (h) |
| 1023 | DOSE_FECL3.PV | FeCl3 dosing rate | x10 (L/h) |
| 1024 | DOSE_FECL3.SP | FeCl3 dosing setpoint | x10 (L/h) |
| 1025 | TANK501.LEVEL | Chemical tank level | x10 (%) |
| 1026 | PMP501.RUNTIME | Dosing pump runtime | x1 (h) |
| 1027 | VLV101.POS | Inlet valve position | x10 (%) |
| 1028 | VLV501.POS | Chemical valve position | x10 (%) |
| 1029 | COD_PRI.PV | COD after primary | x10 (mg/L) |
| 1030 | DOSE_POLY.PV | Polymer dosing rate | x10 (L/h) |
| 1031 | GLOBAL_MODE.PV | Global operating mode | 0=AUTO, 1=MANUAL, 2=MAINT |

### Coils (FC 1/5) - Digital Commands

| Address | Tag | Description |
|---------|-----|-------------|
| 2000 | PMP101.CMD | Influent pump command |
| 2001 | PMP101.AUTO | Influent pump auto mode |
| 2002 | BLW201.CMD | Blower command |
| 2003 | BLW201.AUTO | Blower auto mode |
| 2004 | PMP401.CMD | RAS pump command |
| 2005 | PMP401.AUTO | RAS pump auto mode |
| 2006 | PMP402.CMD | WAS pump command |
| 2007 | PMP402.AUTO | WAS pump auto mode |
| 2010 | SCR101.CMD | Screen clean command |
| 2011 | SCR101.AUTO | Screen auto mode |
| 2012 | PMP301.CMD | Primary pump command |
| 2013 | PMP301.AUTO | Primary pump auto mode |
| 2014 | PMP501.CMD | Dosing pump command |
| 2015 | PMP501.AUTO | Dosing pump auto mode |
| 2016 | KILL_SWITCH | Emergency stop |

### Discrete Inputs (FC 2) - Status/Feedback

| Address | Tag | Description |
|---------|-----|-------------|
| 3000 | PMP101.FB | Influent pump feedback |
| 3001 | PMP101.FAULT | Influent pump fault |
| 3002 | BLW201.FB | Blower feedback |
| 3003 | BLW201.FAULT | Blower fault |
| 3004 | PMP401.FB | RAS pump feedback |
| 3005 | PMP402.FB | WAS pump feedback |
| 3008 | SCR101.FB | Screen clean feedback |
| 3009 | SCR101.FAULT | Screen fault |
| 3010 | PMP301.FB | Primary pump feedback |
| 3011 | PMP301.FAULT | Primary pump fault |
| 3012 | PMP501.FB | Dosing pump feedback |
| 3013 | GRS201.SKIM | Grease skimmer active |

### Modbus Client Example

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('localhost', port=502)
client.connect()

# Read analog values
result = client.read_holding_registers(1000, 12)
print(f"Q_IN: {result.registers[0] / 10.0} m3/h")
print(f"DO:   {result.registers[3] / 10.0} mg/L")

# Write coil (start pump)
client.write_coil(2000, True)   # PMP101.CMD = ON

# Read discrete inputs
result = client.read_discrete_inputs(3000, 6)
print(f"PMP101.FB: {result.bits[0]}")

client.close()
```

## SNMP Agent

Port **161/udp**, community string `public_ro` (read-only).

| OID | Description |
|-----|-------------|
| 1.3.6.1.2.1.1.1.0 | sysDescr (WWTP Control System) |
| 1.3.6.1.2.1.1.3.0 | sysUpTime |
| 1.3.6.1.2.1.1.4.0 | sysContact |
| 1.3.6.1.2.1.1.5.0 | sysName |
| 1.3.6.1.2.1.1.6.0 | sysLocation |
| 1.3.6.1.4.1.9999.1.1.1.0 | Cabinet temperature |
| 1.3.6.1.4.1.9999.1.1.2.0 | UPS status |
| 1.3.6.1.4.1.9999.1.1.3.0 | CPU load |

```bash
snmpwalk -v 2c -c public_ro localhost 1.3.6.1.2.1.1
```

## Alarms (ISA-18.2)

| # | Alarm | Tag | Condition | Severity | Delay |
|---|-------|-----|-----------|----------|-------|
| 1 | HH Wet Well Level | LT101.PV | > 2.5 m | HIGH | 5s |
| 2 | Low Dissolved Oxygen | DO301.PV | < 1.5 mg/L | MEDIUM | 10s |
| 3 | VFD Fault Blower | BLW201.FAULT | = 1 | HIGH | 0s |
| 4 | High Effluent Turbidity | TUR501.PV | > 5.0 NTU | MEDIUM | 15s |
| 5 | pH Out of Range | pH302.PV | < 6.5 or > 8.0 | LOW | 20s |
| 6 | Screen Blockage | SCR101.DP | > 0.45 bar | MEDIUM | 10s |
| 7 | Screen Fault | SCR101.FAULT | = 1 | HIGH | 0s |
| 8 | Low Chemical Tank | TANK501.LEVEL | < 10% | MEDIUM | 30s |
| 9 | Chemical Overdose | DOSE_FECL3.PV | > 8.0 L/h | HIGH | 15s |
| 10 | Kill Switch Active | KILL_SWITCH.PV | = 1 | CRITICAL | 0s |

## Tag Naming Convention

`WWTP01:<AREA>:<DEVICE><ID>.<ATTR>`

- **Areas**: SYSTEM, INFLUENT, SCREENING, GRIT, PRIMARY, AERATION, CLARIFIER, CHEMICAL, EFFLUENT
- **Attributes**: PV (process value), SP (setpoint), CMD (command), FB (feedback), AUTO, FAULT, RUNTIME, DP, LEVEL, POS

Examples:
- `WWTP01:INFLUENT:LT101.PV` - Wet well level transmitter, process value
- `WWTP01:AERATION:BLW201.CMD` - Blower 201, command
- `WWTP01:SCREENING:SCR101.DP` - Screen 101, differential pressure

## Testing

### Run All Tests

```bash
cd tests
pip install requests pymodbus

# Start services first
docker-compose up -d
sleep 10

# Run tests
bash run_all_tests.sh
```

### Individual Tests

| Test | File | Description |
|------|------|-------------|
| Storm scenario | `test_storm.py` | Verifies increased Q_IN, LT101, HH alarm |
| VFD fault | `test_vfd_fault.py` | Verifies blower fault, DO decrease |
| Modbus whitelist | `test_modbus_write_whitelist.py` | Verifies write protection |
| New scenarios | `test_new_scenarios.py` | Screen blockage, DO sensor failure, chemical overdose |
| Trends API | `test_trends_api.py` | Trend endpoint structure and data |
| Mode/Kill switch | `test_mode_killswitch.py` | Operating mode transitions, emergency stop |
| Alarm acknowledge | `test_alarm_acknowledge.py` | Alarm acknowledgement flow |

### Deterministic Mode

For reproducible tests, set in `.env`:
```bash
DETERMINISTIC=true
RANDOM_SEED=42
```

## Logging

All operations are logged in two formats:

### Structured JSON Logs

Structured JSON logs are written to `/data/logs/` (mapped to `./logs/` on host):

- `api_YYYYMMDD.jsonl` - Simulator API operations
- `modbus_YYYYMMDD.jsonl` - Modbus read/write requests
- `snmp_YYYYMMDD.jsonl` - SNMP queries
- `hmi_YYYYMMDD.jsonl` - HMI web operations

### Application Logs

Application logs with standard Python logging format are written to:

- `simulator/simulator.log` - Simulator application logs (rotates daily)
- `hmi/hmi.log` - HMI web application logs (rotates daily)
- `modbus/modbus.log` - Modbus server logs (rotates daily)
- `snmp/snmp.log` - SNMP agent logs (rotates daily)

Logs are automatically rotated daily at midnight. Old logs are kept for 30 days with suffix `.YYYYMMDD`.

### Log Format

```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "correlation_id": "a1b2c3d4",
  "src_ip": "192.168.1.100",
  "operation": "write",
  "action": "write",
  "result": "success",
  "details": {
    "tag": "WWTP01:INFLUENT:PMP101.CMD",
    "value": true
  }
}
```

## Telegram Notifications

The honeypot can send real-time notifications to Telegram for important events. This is useful for monitoring honeypot activity and security events.

### Configuration

1. **Create a Telegram Bot:**
   - Open Telegram and search for [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow instructions to create a bot
   - Copy the bot token (e.g., `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Get Your Chat ID:**
   - Start a conversation with your bot
   - Send a message to your bot
   - Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your chat ID in the response (e.g., `123456789`)

3. **Configure Environment Variables:**
   
   Create or edit `.env` file in the project root:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   TELEGRAM_CHAT_ID=123456789
   ```

4. **Restart Services:**
   ```bash
   docker-compose restart simulator hmi_web
   ```

### Notification Events

The following events trigger Telegram notifications:

| Event | Description | Emoji |
|-------|-------------|-------|
| **Alarm Activated** | When any alarm is triggered (HH/LL levels, DO, faults, etc.) | ⚠️🔴🚨 |
| **Alarm Cleared** | When an alarm condition clears | ✅ |
| **Emergency Stop** | Kill switch activated/deactivated | 🚨✅ |
| **Honeypot Login** | Successful honeypot authentication (after failed attempts) | 🔐 |
| **Honeypot Write** | Tag write operation from honeypot account | ✍️ |
| **Tag Write** | Any tag write via API | 📝 |
| **Scenario Start** | Test scenario activation | 🎬 |

### Notification Format

Notifications are sent in HTML format with structured information:

**Example - Alarm Activated:**
```
🚨 ALARM ACTIVATED
Alarm: HH Wet Well Level
Tag: WWTP01:INFLUENT:LT101.PV
Value: 2.65
Severity: HIGH
Time: 2024-02-07 14:30:45
```

**Example - Honeypot Login:**
```
🔐 HONEYPOT LOGIN
IP: 192.168.1.100
User: admin
Pass: password123
Attempts: 5/5
```

### Troubleshooting

- **No notifications received:**
  - Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`
  - Verify bot token is correct
  - Ensure you've sent at least one message to the bot
  - Check container logs: `docker-compose logs simulator | grep -i telegram`

- **Notifications not working:**
  - Check network connectivity (containers need internet access)
  - Verify chat ID is correct (must be numeric)
  - Check logs for errors: `docker-compose logs simulator hmi_web`

### Disabling Notifications

To disable Telegram notifications, simply remove or comment out the environment variables in `.env`:
```bash
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
```

## Security Notes

### Write Whitelist

Only the following 23 tags accept writes (via HTTP API and Modbus):

- Equipment commands: PMP101/BLW201/PMP301/PMP401/PMP402/PMP501/SCR101 `.CMD` and `.AUTO`
- Setpoints: BLW201.SP, DO301.SP, DO301.CTRL_EN, DO301.CTRL_MODE, DOSE_FECL3.SP
- Valves: VLV101.CMD, VLV501.CMD
- System: GLOBAL_MODE.PV, KILL_SWITCH.PV

All writes are logged with source IP and correlation ID.

### Docker Hardening

Containers run with:
- `read_only: true` - Read-only filesystem
- `cap_drop: ALL` - All capabilities dropped
- `cap_add: NET_BIND_SERVICE` - Only port binding allowed
- `security_opt: no-new-privileges:true` - No privilege escalation
- `tmpfs` for /tmp and /app/logs
- Non-root user (appuser)

### Network Recommendations

```bash
# Block outbound (except DNS)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
iptables -A OUTPUT -j DROP
```

Or use Docker network with `internal: true`.

## Project Structure

```
OT_honey/
├── simulator/              # Core process simulator
│   ├── main.py             # Flask API, trend buffer, endpoints
│   ├── process_model.py    # Process physics, PID controllers, equipment
│   ├── tag_generator.py    # Tag naming, 200+ tags
│   ├── alarm_engine.py     # ISA-18.2 alarm management (10 alarms)
│   └── scenario_manager.py # 7 test scenarios with auto-recovery
├── plc_modbus/             # Modbus TCP server
│   └── main.py             # Register mapping, write whitelist, jitter
├── snmp_agent/             # SNMP agent
│   └── main.py             # Standard + custom OIDs
├── hmi_web/                # Web HMI interface
│   ├── app.py              # Flask routes, API proxying, auth
│   └── templates/
│       ├── base.html       # Light industrial theme, safety banner, nav
│       ├── login.html      # Authentication page
│       ├── overview.html   # SVG P&ID with equipment faceplates
│       ├── alarms.html     # ISA-18.2 alarm summary with ACK
│       ├── trends.html     # Chart.js trend charts (4 panels)
│       └── maintenance.html # Mode selector, kill switch, equipment status
├── tests/                  # Integration test suite (7 tests)
├── replay/                 # Trace recording and replay
│   ├── record_trace.py
│   └── replay_trace.py
├── docker-compose.yml
└── README.md
```

## Pre-Deployment Checklist

- [ ] Change all default passwords (HMI users)
- [ ] Change SECRET_KEY in `hmi_web/app.py`
- [ ] Configure firewall (block outbound)
- [ ] Verify Docker security options
- [ ] Set up log monitoring (ELK, Splunk, etc.)
- [ ] Set up log rotation and disk monitoring
- [ ] Run all integration tests
- [ ] Test all 7 scenarios
- [ ] Verify Modbus read/write operations
- [ ] Verify SNMP queries
- [ ] Document network topology and IP addresses
- [ ] Verify compliance with local regulations

## License

This project is intended for research and educational purposes only. Honeypot operation must comply with local laws and regulations.
