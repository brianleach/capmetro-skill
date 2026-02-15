# CapMetro Austin Transit — OpenClaw Skill

Real-time Austin public transit data for your OpenClaw agent. Get vehicle positions, next arrivals, service alerts, and route info for MetroBus, MetroRapid, and MetroRail.

## Install

```bash
# Copy to your OpenClaw skills directory
cp -r capmetro ~/.openclaw/skills/capmetro
# or for workspace-specific:
cp -r capmetro <workspace>/skills/capmetro

# Install Python dependencies
pip3 install gtfs-realtime-bindings requests protobuf

# Download GTFS static data (routes, stops, schedules)
python3 ~/.openclaw/skills/capmetro/scripts/capmetro.py refresh-gtfs
```

## Usage (via OpenClaw chat)

Just ask your agent naturally:

- "When's the next 801 at the Domain?"
- "Any CapMetro service alerts right now?"
- "Where are the MetroRail trains?"
- "Find bus stops near 30.267, -97.743"
- "What routes does CapMetro run?"
- "Show me the stops on route 803"

## Usage (CLI)

```bash
python3 scripts/capmetro.py alerts
python3 scripts/capmetro.py vehicles --route 801
python3 scripts/capmetro.py arrivals --stop 5800 --route 801
python3 scripts/capmetro.py stops --search "domain"
python3 scripts/capmetro.py stops --near 30.40,-97.72 --radius 0.3
python3 scripts/capmetro.py routes
python3 scripts/capmetro.py route-info --route 801
python3 scripts/capmetro.py refresh-gtfs
```

## Data Sources

All feeds are open access from the [Texas Open Data Portal](https://data.texas.gov) — no API key required.

| Feed | Update Frequency |
|------|-----------------|
| Vehicle Positions | Every 15 seconds |
| Trip Updates | Every 15 seconds |
| Service Alerts | As needed |
| GTFS Static | Quarterly / service changes |

## License

CapMetro data is provided under CMTA's Open Data License. See [CapMetro Developer Tools](https://www.capmetro.org/developertools) for terms.
