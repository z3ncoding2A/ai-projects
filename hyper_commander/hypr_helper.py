#!/usr/bin/env python3
import sys
import json
import subprocess
import argparse

def get_monitors():
    try:
        res = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        print(f"Error getting monitors: {e}", file=sys.stderr)
        return []

def get_clients():
    try:
        res = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        print(f"Error getting clients: {e}", file=sys.stderr)
        return []

def close_window(address):
    try:
        subprocess.run(["hyprctl", "dispatch", "closewindow", f"address:{address}"], check=True)
        print(f"Closed window address:{address}")
        return True
    except Exception as e:
        print(f"Error closing window address:{address}: {e}", file=sys.stderr)
        return False

def check_position(rx, ry, position_name):
    pos_norm = position_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    if pos_norm == "topleft":
        return rx < 0.5 and ry < 0.5
    elif pos_norm == "bottomleft":
        return rx < 0.5 and ry >= 0.5
    elif pos_norm == "topright":
        return rx >= 0.5 and ry < 0.5
    elif pos_norm == "bottomright":
        return rx >= 0.5 and ry >= 0.5
    elif pos_norm == "left":
        return rx < 0.5
    elif pos_norm == "right":
        return rx >= 0.5
    elif pos_norm == "top":
        return ry < 0.5
    elif pos_norm == "bottom":
        return ry >= 0.5
    elif pos_norm in ("center", "middle"):
        return 0.25 <= rx <= 0.75 and 0.25 <= ry <= 0.75
    return False

def matches_position(rx, ry, pos_queries):
    # If no positional query is specified, it matches (passes through)
    if not pos_queries:
        return True
    for pos in pos_queries:
        if check_position(rx, ry, pos):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Hyper Commander window helper utility.")
    subparsers = parser.add_subparsers(dest="command")

    close_parser = subparsers.add_parser("close", help="Close windows matching filters")
    close_parser.add_argument("--class", dest="win_class", help="Window class name (case-insensitive substring match)")
    close_parser.add_argument("--title", help="Window title (case-insensitive substring match)")
    close_parser.add_argument("--position", action="append", default=[], help="Spatial positions to target (e.g. top, bottom-left)")
    close_parser.add_argument("--exclude-position", action="append", default=[], help="Spatial positions to exclude (e.g. bottom-right)")
    close_parser.add_argument("--monitor", help="Monitor name or ID to restrict to")
    close_parser.add_argument("--dry-run", action="store_true", help="Print matching windows without closing them")

    args = parser.parse_args()

    if args.command == "close":
        clients = get_clients()
        monitors = get_monitors()

        # Map monitor ID and Name to monitor configuration
        mon_map = {}
        for m in monitors:
            mon_map[m["id"]] = m
            mon_map[str(m["id"])] = m
            mon_map[m["name"].lower()] = m

        matched_windows = []

        for client in clients:
            # Skip unmapped or hidden windows
            if not client.get("mapped", True) or client.get("hidden", False):
                continue

            # Class filter
            if args.win_class:
                c_class = client.get("class", "").lower()
                q_class = args.win_class.lower()
                if q_class not in c_class:
                    continue

            # Title filter
            if args.title:
                c_title = client.get("title", "").lower()
                q_title = args.title.lower()
                if q_title not in c_title:
                    continue

            # Monitor filter
            client_mon_id = client.get("monitor", 0)
            if args.monitor:
                q_mon = args.monitor.lower()
                # Find matching monitor config
                target_mon = mon_map.get(q_mon)
                if not target_mon or client_mon_id != target_mon.get("id"):
                    continue

            # Position calculations
            monitor = mon_map.get(client_mon_id)
            if not monitor and monitors:
                monitor = monitors[0]

            if monitor:
                mx, my = monitor.get("x", 0), monitor.get("y", 0)
                mw, mh = monitor.get("width", 1920), monitor.get("height", 1080)
            else:
                mx, my, mw, mh = 0, 0, 1920, 1080

            # Compute client center
            cx = client["at"][0] + client["size"][0] / 2
            cy = client["at"][1] + client["size"][1] / 2

            # Relative center coordinates (0.0 to 1.0)
            rx = (cx - mx) / mw
            ry = (cy - my) / mh

            # Exclude position filter
            if args.exclude_position:
                should_exclude = False
                for pos in args.exclude_position:
                    if check_position(rx, ry, pos):
                        should_exclude = True
                        break
                if should_exclude:
                    continue

            # Include position filter
            if args.position:
                if not matches_position(rx, ry, args.position):
                    continue

            matched_windows.append(client)

        if not matched_windows:
            print("No matching windows found.")
            return

        print(f"Found {len(matched_windows)} matching window(s):")
        for win in matched_windows:
            print(f"  - Class: {win.get('class')}, Title: {win.get('title')}, Address: {win.get('address')}, Pos: {win.get('at')}, Size: {win.get('size')}")

        if args.dry_run:
            print("Dry run: no windows closed.")
            return

        for win in matched_windows:
            close_window(win["address"])

    else:
        if args.command:
            print(f"Unknown command: {args.command}", file=sys.stderr)
        parser.print_help()

if __name__ == "__main__":
    main()
