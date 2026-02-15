# CapMetro Austin Transit — OpenClaw Skill

Real-time Austin public transit data for your OpenClaw agent. Get vehicle positions, next arrivals, service alerts, and route info for MetroBus, MetroRapid, and MetroRail.

## Install

```bash
# Copy to your OpenClaw skills directory
cp -r capmetro-skill ~/.openclaw/skills/capmetro
# or for workspace-specific:
cp -r capmetro-skill <workspace>/skills/capmetro

# Install Node.js dependencies
cd ~/.openclaw/skills/capmetro && npm install

# Download GTFS static data (routes, stops, schedules)
node ~/.openclaw/skills/capmetro/scripts/capmetro.mjs refresh-gtfs
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
node scripts/capmetro.mjs alerts
node scripts/capmetro.mjs vehicles --route 801
node scripts/capmetro.mjs arrivals --stop 5800 --route 801
node scripts/capmetro.mjs arrivals --stop-search "lakeline" --route 550
node scripts/capmetro.mjs arrivals --stop-search "downtown" --route 550 --headsign "lakeline"
node scripts/capmetro.mjs stops --search "domain"
node scripts/capmetro.mjs stops --near 30.40,-97.72 --radius 0.3
node scripts/capmetro.mjs routes
node scripts/capmetro.mjs route-info --route 801
node scripts/capmetro.mjs refresh-gtfs
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

MIT — see [LICENSE](LICENSE).

CapMetro data is provided under CMTA's Open Data License. See [CapMetro Developer Tools](https://www.capmetro.org/developertools) for terms.
