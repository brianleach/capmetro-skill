#!/usr/bin/env python3
"""
CapMetro Austin Transit - OpenClaw Skill
Real-time vehicle positions, arrivals, alerts, and route info.
All data from Texas Open Data Portal (no API key required).
"""

import argparse
import csv
import io
import json
import math
import os
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Feed URLs (Texas Open Data Portal — open access, no key)
# ---------------------------------------------------------------------------
FEEDS = {
    "vehicle_positions_json": "https://data.texas.gov/download/cuc7-ywmd/text%2Fplain",
    "vehicle_positions_pb": "https://data.texas.gov/download/eiei-9rpf/application%2Foctet-stream",
    "trip_updates_pb": "https://data.texas.gov/download/rmk2-acnw/application%2Foctet-stream",
    "service_alerts_pb": "https://data.texas.gov/download/nusn-7fcn/application%2Foctet-stream",
    "gtfs_static": "https://data.texas.gov/download/r4v4-vz24/application%2Fx-zip-compressed",
}

GTFS_DIR = Path.home() / ".capmetro" / "gtfs"
CST = timezone(timedelta(hours=-6))  # Central Standard Time
CDT = timezone(timedelta(hours=-5))  # Central Daylight Time

# Use CDT Mar-Nov, CST Nov-Mar (simplified — good enough for display)
def local_tz():
    now = datetime.now(timezone.utc)
    month = now.month
    if 3 <= month < 11:
        return CDT
    return CST

def local_now():
    return datetime.now(local_tz())

# ---------------------------------------------------------------------------
# GTFS-RT Protobuf helpers
# ---------------------------------------------------------------------------

def _parse_pb(url: str):
    """Fetch and parse a GTFS-RT protobuf feed."""
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError:
        print("ERROR: gtfs-realtime-bindings not installed.")
        print("Run: pip3 install gtfs-realtime-bindings requests protobuf")
        sys.exit(1)

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    return feed

# ---------------------------------------------------------------------------
# GTFS Static data helpers
# ---------------------------------------------------------------------------

def _ensure_gtfs():
    """Check if GTFS static data exists."""
    if not (GTFS_DIR / "stops.txt").exists():
        print(f"GTFS static data not found at {GTFS_DIR}")
        print("Run: python3 scripts/capmetro.py refresh-gtfs")
        return False
    return True

def _load_csv(filename: str) -> list[dict]:
    """Load a GTFS CSV file as list of dicts."""
    path = GTFS_DIR / filename
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def _load_stops() -> dict:
    """Load stops indexed by stop_id."""
    rows = _load_csv("stops.txt")
    return {r["stop_id"]: r for r in rows}

def _load_routes() -> dict:
    """Load routes indexed by route_id."""
    rows = _load_csv("routes.txt")
    return {r["route_id"]: r for r in rows}

def _load_trips() -> dict:
    """Load trips indexed by trip_id."""
    rows = _load_csv("trips.txt")
    return {r["trip_id"]: r for r in rows}

def _load_stop_times_for_stop(stop_id: str) -> list[dict]:
    """Load stop_times for a specific stop."""
    rows = _load_csv("stop_times.txt")
    return [r for r in rows if r["stop_id"] == stop_id]

def _load_stop_times_for_trip(trip_id: str) -> list[dict]:
    """Load stop_times for a specific trip."""
    rows = _load_csv("stop_times.txt")
    return sorted(
        [r for r in rows if r["trip_id"] == trip_id],
        key=lambda r: int(r.get("stop_sequence", 0)),
    )

# ---------------------------------------------------------------------------
# Distance helper (Haversine)
# ---------------------------------------------------------------------------

def _haversine(lat1, lon1, lat2, lon2):
    """Distance in miles between two lat/lon points."""
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_refresh_gtfs(args):
    """Download and extract GTFS static data."""
    print(f"Downloading GTFS static data to {GTFS_DIR} ...")
    GTFS_DIR.mkdir(parents=True, exist_ok=True)
    resp = requests.get(FEEDS["gtfs_static"], timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(GTFS_DIR)
    files = list(GTFS_DIR.glob("*.txt"))
    print(f"Extracted {len(files)} files:")
    for f in sorted(files):
        print(f"  {f.name}")
    print("GTFS data refreshed successfully.")


def cmd_alerts(args):
    """Fetch and display current service alerts."""
    feed = _parse_pb(FEEDS["service_alerts_pb"])
    routes = _load_routes() if _ensure_gtfs() else {}

    if not feed.entity:
        print("No active service alerts.")
        return

    print(f"=== CapMetro Service Alerts ({len(feed.entity)} active) ===\n")
    for entity in feed.entity:
        alert = entity.alert
        # Header text
        header = ""
        if alert.header_text.translation:
            header = alert.header_text.translation[0].text
        # Description
        desc = ""
        if alert.description_text.translation:
            desc = alert.description_text.translation[0].text
        # Affected routes
        affected = []
        for ie in alert.informed_entity:
            rid = ie.route_id
            if rid:
                rname = routes.get(rid, {}).get("route_short_name", rid)
                affected.append(rname)

        # Cause / Effect
        cause = str(alert.cause) if alert.cause else ""
        effect = str(alert.effect) if alert.effect else ""

        # Active periods
        periods = []
        for ap in alert.active_period:
            start = datetime.fromtimestamp(ap.start, tz=local_tz()).strftime("%m/%d %I:%M%p") if ap.start else "?"
            end = datetime.fromtimestamp(ap.end, tz=local_tz()).strftime("%m/%d %I:%M%p") if ap.end else "ongoing"
            periods.append(f"{start} - {end}")

        print(f"📢 {header}")
        if affected:
            print(f"   Routes: {', '.join(affected)}")
        if periods:
            print(f"   Period: {'; '.join(periods)}")
        if desc:
            # Truncate long descriptions
            if len(desc) > 300:
                desc = desc[:300] + "..."
            print(f"   {desc}")
        print()


def cmd_vehicles(args):
    """Fetch and display real-time vehicle positions."""
    route_filter = args.route

    # Use JSON feed (easier to parse, no protobuf dependency for this command)
    print("Fetching vehicle positions...")
    resp = requests.get(FEEDS["vehicle_positions_json"], timeout=30)
    resp.raise_for_status()
    data = resp.json()

    routes = _load_routes() if _ensure_gtfs() else {}

    # The JSON structure from CapMetro
    entities = data.get("entity", data) if isinstance(data, dict) else data

    vehicles = []
    for entity in entities:
        v = entity.get("vehicle", entity)
        trip = v.get("trip", {})
        pos = v.get("position", {})
        vid = v.get("vehicle", {}).get("id", "?")
        rid = trip.get("route_id", "")
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        ts = v.get("timestamp")

        if route_filter and rid != route_filter:
            continue
        if not rid:  # Not in service
            continue

        rname = routes.get(rid, {}).get("route_short_name", rid)
        rlong = routes.get(rid, {}).get("route_long_name", "")

        time_str = ""
        if ts:
            try:
                time_str = datetime.fromtimestamp(int(ts), tz=local_tz()).strftime("%I:%M:%S %p")
            except (ValueError, OSError):
                time_str = str(ts)

        vehicles.append({
            "vid": vid,
            "route": rname,
            "route_name": rlong,
            "lat": lat,
            "lon": lon,
            "time": time_str,
        })

    if not vehicles:
        filter_msg = f" on route {route_filter}" if route_filter else ""
        print(f"No active vehicles found{filter_msg}.")
        return

    print(f"\n=== Active CapMetro Vehicles ({len(vehicles)}) ===\n")
    # Group by route
    by_route = {}
    for v in vehicles:
        by_route.setdefault(v["route"], []).append(v)

    for route in sorted(by_route.keys(), key=lambda x: x.zfill(5)):
        vlist = by_route[route]
        rlong = vlist[0]["route_name"]
        print(f"Route {route} — {rlong} ({len(vlist)} vehicles)")
        for v in vlist:
            print(f"  🚍 Vehicle {v['vid']}: ({v['lat']:.5f}, {v['lon']:.5f}) @ {v['time']}")
        print()


def cmd_arrivals(args):
    """Get next arrivals at a stop."""
    stop_id = args.stop
    route_filter = args.route

    if not _ensure_gtfs():
        return

    stops = _load_stops()
    routes = _load_routes()
    trips = _load_trips()

    if stop_id not in stops:
        print(f"Stop ID '{stop_id}' not found in GTFS data.")
        print("Use 'stops --search <name>' to find stop IDs.")
        return

    stop = stops[stop_id]
    print(f"\n=== Arrivals at: {stop['stop_name']} (ID: {stop_id}) ===\n")

    # Fetch trip updates for real-time arrival info
    feed = _parse_pb(FEEDS["trip_updates_pb"])

    rt_arrivals = []
    for entity in feed.entity:
        tu = entity.trip_update
        trip_id = tu.trip.trip_id
        route_id = tu.trip.route_id

        if route_filter and route_id != route_filter:
            continue

        for stu in tu.stop_time_update:
            if stu.stop_id == stop_id:
                arrival_time = None
                departure_time = None
                delay = 0

                if stu.arrival.time:
                    arrival_time = datetime.fromtimestamp(stu.arrival.time, tz=local_tz())
                    delay = stu.arrival.delay if stu.arrival.delay else 0
                elif stu.departure.time:
                    arrival_time = datetime.fromtimestamp(stu.departure.time, tz=local_tz())
                    delay = stu.departure.delay if stu.departure.delay else 0

                if arrival_time:
                    rname = routes.get(route_id, {}).get("route_short_name", route_id)
                    rlong = routes.get(route_id, {}).get("route_long_name", "")
                    trip_info = trips.get(trip_id, {})
                    headsign = trip_info.get("trip_headsign", rlong)

                    now = local_now()
                    mins_away = (arrival_time - now).total_seconds() / 60

                    if mins_away < -5:  # Already passed
                        continue

                    rt_arrivals.append({
                        "route": rname,
                        "headsign": headsign,
                        "arrival": arrival_time.strftime("%I:%M %p"),
                        "mins_away": round(mins_away),
                        "delay_mins": round(delay / 60) if delay else 0,
                    })

    if rt_arrivals:
        rt_arrivals.sort(key=lambda x: x["mins_away"])
        print("Real-time arrivals:")
        for a in rt_arrivals[:15]:
            delay_str = f" (+{a['delay_mins']}m late)" if a['delay_mins'] > 0 else ""
            if a["mins_away"] <= 0:
                eta = "NOW"
            elif a["mins_away"] == 1:
                eta = "1 min"
            else:
                eta = f"{a['mins_away']} min"
            print(f"  🚌 Route {a['route']} → {a['headsign']}")
            print(f"     {a['arrival']} ({eta}){delay_str}")
            print()
    else:
        # Fall back to scheduled times
        print("No real-time data available. Showing scheduled times:")
        stop_times = _load_stop_times_for_stop(stop_id)
        now = local_now()
        current_time = now.strftime("%H:%M:%S")

        upcoming = []
        for st in stop_times:
            trip_id = st["trip_id"]
            trip_info = trips.get(trip_id, {})
            route_id = trip_info.get("route_id", "")

            if route_filter and route_id != route_filter:
                continue

            arr_time = st.get("arrival_time", st.get("departure_time", ""))
            if arr_time > current_time:
                rname = routes.get(route_id, {}).get("route_short_name", route_id)
                headsign = trip_info.get("trip_headsign", "")
                upcoming.append({
                    "route": rname,
                    "headsign": headsign,
                    "time": arr_time,
                })

        upcoming.sort(key=lambda x: x["time"])
        for u in upcoming[:10]:
            # Convert 24h to 12h
            try:
                h, m, s = u["time"].split(":")
                h = int(h)
                ampm = "AM" if h < 12 else "PM"
                if h > 12:
                    h -= 12
                elif h == 0:
                    h = 12
                time_str = f"{h}:{m} {ampm}"
            except (ValueError, IndexError):
                time_str = u["time"]
            print(f"  🚌 Route {u['route']} → {u['headsign']} at {time_str}")


def cmd_stops(args):
    """Search for stops by name or location."""
    if not _ensure_gtfs():
        return

    stops = _load_stops()

    if args.search:
        query = args.search.lower()
        matches = [
            s for s in stops.values()
            if query in s.get("stop_name", "").lower()
            or query in s.get("stop_desc", "").lower()
        ]
        if not matches:
            print(f"No stops found matching '{args.search}'.")
            return

        print(f"\n=== Stops matching '{args.search}' ({len(matches)} found) ===\n")
        for s in sorted(matches, key=lambda x: x["stop_name"])[:25]:
            print(f"  📍 {s['stop_name']}")
            print(f"     ID: {s['stop_id']}  |  ({s['stop_lat']}, {s['stop_lon']})")
            if s.get("stop_desc"):
                print(f"     {s['stop_desc']}")
            print()

    elif args.near:
        try:
            lat, lon = map(float, args.near.split(","))
        except ValueError:
            print("Invalid format. Use: --near LAT,LON  (e.g. --near 30.267,-97.743)")
            return

        radius = float(args.radius) if args.radius else 0.5  # miles

        nearby = []
        for s in stops.values():
            try:
                slat = float(s["stop_lat"])
                slon = float(s["stop_lon"])
            except (ValueError, KeyError):
                continue
            dist = _haversine(lat, lon, slat, slon)
            if dist <= radius:
                nearby.append((dist, s))

        nearby.sort(key=lambda x: x[0])

        if not nearby:
            print(f"No stops found within {radius} miles of ({lat}, {lon}).")
            return

        print(f"\n=== Nearby Stops ({len(nearby)} within {radius} mi) ===\n")
        for dist, s in nearby[:20]:
            print(f"  📍 {s['stop_name']} — {dist:.2f} mi")
            print(f"     ID: {s['stop_id']}")
            print()
    else:
        print("Provide --search <name> or --near LAT,LON")


def cmd_routes(args):
    """List all routes."""
    if not _ensure_gtfs():
        return

    routes = _load_routes()
    print(f"\n=== CapMetro Routes ({len(routes)}) ===\n")

    # GTFS route_type: 0=Tram, 1=Subway, 2=Rail, 3=Bus, 4=Ferry
    type_names = {"0": "Tram", "1": "Subway", "2": "Rail", "3": "Bus", "4": "Ferry"}

    for rid in sorted(routes.keys(), key=lambda x: x.zfill(5)):
        r = routes[rid]
        rtype = type_names.get(r.get("route_type", "3"), "Other")
        short = r.get("route_short_name", rid)
        long_name = r.get("route_long_name", "")
        print(f"  {short:>6} | {rtype:<5} | {long_name}")


def cmd_route_info(args):
    """Get detailed route information including stops."""
    if not _ensure_gtfs():
        return

    route_id = args.route
    routes = _load_routes()
    trips = _load_trips()
    stops = _load_stops()

    if route_id not in routes:
        # Try matching by short name
        for rid, r in routes.items():
            if r.get("route_short_name") == route_id:
                route_id = rid
                break
        else:
            print(f"Route '{args.route}' not found.")
            return

    r = routes[route_id]
    print(f"\n=== Route {r.get('route_short_name', route_id)} — {r.get('route_long_name', '')} ===")
    print(f"    Type: {r.get('route_type', '?')}  |  ID: {route_id}")
    if r.get("route_url"):
        print(f"    URL: {r['route_url']}")
    print()

    # Find a representative trip for this route to show stops
    route_trips = [t for t in trips.values() if t.get("route_id") == route_id]
    if not route_trips:
        print("No trips found for this route.")
        return

    # Pick first trip (direction 0 if available)
    dir0 = [t for t in route_trips if t.get("direction_id") == "0"]
    sample_trip = (dir0 or route_trips)[0]

    stop_times = _load_stop_times_for_trip(sample_trip["trip_id"])
    if stop_times:
        headsign = sample_trip.get("trip_headsign", "")
        print(f"Stops (direction: {headsign}):")
        for st in stop_times:
            sid = st["stop_id"]
            sname = stops.get(sid, {}).get("stop_name", sid)
            print(f"  {st.get('stop_sequence', ''):>3}. {sname} (ID: {sid})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CapMetro Austin Transit — OpenClaw Skill",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # alerts
    sub.add_parser("alerts", help="Show current service alerts")

    # vehicles
    p_veh = sub.add_parser("vehicles", help="Show real-time vehicle positions")
    p_veh.add_argument("--route", help="Filter by route ID")

    # arrivals
    p_arr = sub.add_parser("arrivals", help="Next arrivals at a stop")
    p_arr.add_argument("--stop", required=True, help="Stop ID")
    p_arr.add_argument("--route", help="Filter by route ID")

    # stops
    p_stops = sub.add_parser("stops", help="Search for stops")
    p_stops.add_argument("--search", help="Search stops by name")
    p_stops.add_argument("--near", help="Find stops near LAT,LON")
    p_stops.add_argument("--radius", help="Search radius in miles (default 0.5)")

    # routes
    sub.add_parser("routes", help="List all routes")

    # route-info
    p_ri = sub.add_parser("route-info", help="Get route details and stops")
    p_ri.add_argument("--route", required=True, help="Route ID or short name")

    # refresh-gtfs
    sub.add_parser("refresh-gtfs", help="Download/refresh GTFS static data")

    args = parser.parse_args()

    commands = {
        "alerts": cmd_alerts,
        "vehicles": cmd_vehicles,
        "arrivals": cmd_arrivals,
        "stops": cmd_stops,
        "routes": cmd_routes,
        "route-info": cmd_route_info,
        "refresh-gtfs": cmd_refresh_gtfs,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
