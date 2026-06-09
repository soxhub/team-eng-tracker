#!/usr/bin/env python3
"""
Pull FireHydrant incident data for team members.

Two signal sources:
  1. Role assignments  — Commander / Responder / Subject matter expert
  2. Event timeline    — chat messages, status updates, attachments, runbook
                         steps (catches engineers who worked without a formal role)

Usage:
  python3 scripts/fh-incidents.py --start 2026-06-01 --end 2026-06-07
  python3 scripts/fh-incidents.py --start 2026-06-01 --end 2026-06-07 --patch reports/2026/06/W01

--patch rewrites each engineer's .md file in the given week directory,
inserting or replacing a "## FireHydrant Incidents" section.

Reads team and engineer configuration from config.yaml in the repo root.
Requires: FH_TOKEN env var (or set firehydrant.token in config.yaml).
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

FH_BASE = "https://api.firehydrant.io/v1"

# Event types that represent meaningful human work
WORK_EVENT_TYPES = {
    "event/chat_message",
    "event/bulk_update",
    "event/generic_resource_change",
    "event/ticket_update",
    "event/role_update",
    "incident_attachment",
    "event/runbook_attachment",
    "event/alert_linked",
}


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    if not config_path.exists():
        print(f"ERROR: config.yaml not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_engineer_maps(config: dict) -> tuple[dict, dict]:
    """Return (uid_to_info, name_to_uid) from config engineers with fh_user_id set."""
    uid_to_info: dict[str, tuple[str, str]] = {}
    name_to_uid: dict[str, str] = {}
    for eng in config.get("engineers", []):
        fh_id = eng.get("fh_user_id", "").strip()
        if not fh_id or not eng.get("active", True):
            continue
        name = eng["name"]
        slug = name.lower().replace(" ", "-")
        uid_to_info[fh_id] = (name, slug)
        name_to_uid[name] = fh_id
    return uid_to_info, name_to_uid


def fh_get(path: str, token: str) -> dict:
    url = f"{FH_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_incidents(team_id: str, start: str, end: str, token: str) -> list[dict]:
    incidents = []
    page = 1
    while True:
        data = fh_get(
            f"/incidents?team_id={team_id}"
            f"&start_date={start}&end_date={end}"
            f"&page={page}&per_page=50",
            token,
        )
        batch = data.get("data", [])
        incidents.extend(batch)
        if page >= data.get("pagination", {}).get("pages", 1):
            break
        page += 1
    return incidents


def fetch_events(inc_id: str, token: str) -> list[dict]:
    events = []
    page = 1
    while True:
        data = fh_get(f"/incidents/{inc_id}/events?page={page}&per_page=50", token)
        batch = data.get("data", [])
        events.extend(batch)
        if page >= data.get("pagination", {}).get("pages", 1):
            break
        page += 1
    return events


def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %-d")
    except Exception:
        return iso[:10]


def classify_contribution(events: list[dict], engineer_name: str) -> str:
    types = {
        e.get("type", "")
        for e in events
        if (e.get("author") or {}).get("name") == engineer_name
        and e.get("type") in WORK_EVENT_TYPES
    }
    if not types:
        return ""
    if "event/chat_message" in types and any(
        t in types for t in ("event/bulk_update", "event/generic_resource_change", "event/role_update")
    ):
        return "Investigated + managed"
    if "event/chat_message" in types:
        return "Investigated"
    if any(t in types for t in ("event/bulk_update", "event/role_update")):
        return "Managed"
    return "Contributed"


def build_per_engineer(
    incidents: list[dict],
    uid_to_info: dict,
    name_to_uid: dict,
    token: str,
    scan_events: bool = True,
) -> dict[str, list[dict]]:
    by_engineer: dict[str, list[dict]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)

    for inc in incidents:
        inc_id = inc["id"]
        inc_date = fmt_date(inc.get("started_at") or inc.get("created_at", ""))
        inc_row_base = {
            "date": inc_date,
            "number": inc["number"],
            "name": inc["name"],
            "severity": inc.get("severity", "—"),
            "url": inc.get("incident_url", ""),
        }

        # Source 1: role_assignments
        for ra in inc.get("role_assignments", []):
            user = ra.get("user")
            if not user:
                continue
            uid = user.get("id")
            if uid not in uid_to_info:
                continue
            if inc_id in seen[uid]:
                continue
            seen[uid].add(inc_id)
            role = ra.get("incident_role", {}).get("name", "Responder")
            by_engineer[uid].append({**inc_row_base, "role": role, "source": "role"})

        if not scan_events:
            continue

        # Source 2: event timeline
        print(f"  scanning events for #{inc['number']}…", file=sys.stderr)
        try:
            events = fetch_events(inc_id, token)
        except Exception as exc:
            print(f"  warning: could not fetch events for {inc_id}: {exc}", file=sys.stderr)
            continue

        for event in events:
            if event.get("type") not in WORK_EVENT_TYPES:
                continue
            author_name = (event.get("author") or {}).get("name", "")
            uid = name_to_uid.get(author_name)
            if uid is None or inc_id in seen[uid]:
                continue
            seen[uid].add(inc_id)
            contribution = classify_contribution(events, author_name)
            by_engineer[uid].append({**inc_row_base, "role": contribution or "Contributed", "source": "event"})

    return by_engineer


def render_section(rows: list[dict]) -> str:
    if not rows:
        return "## FireHydrant Incidents\n\n_No incidents this week._\n"

    lines = [
        "## FireHydrant Incidents\n",
        "| Date | # | Incident | Severity | Role |",
        "|------|---|----------|----------|------|",
    ]
    for r in sorted(rows, key=lambda x: x["number"]):
        num = f"[{r['number']}]({r['url']})" if r["url"] else str(r["number"])
        lines.append(
            f"| {r['date']} | {num} | {r['name']} | {r['severity']} | {r['role']} |"
        )
    lines.append("")
    return "\n".join(lines)


def patch_file(path: str, section_md: str) -> None:
    with open(path) as f:
        content = f.read()

    marker = "## FireHydrant Incidents"
    if marker in content:
        content = re.sub(
            r"## FireHydrant Incidents\n.*?(?=\n## |\Z)",
            section_md.rstrip() + "\n",
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.rstrip() + "\n\n" + section_md

    with open(path, "w") as f:
        f.write(content)
    print(f"  patched {path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--patch", metavar="WEEK_DIR", help="Week dir to patch, e.g. reports/2026/06/W01")
    parser.add_argument("--no-events", action="store_true", help="Skip event timeline scan (faster, roles only)")
    args = parser.parse_args()

    config = load_config()
    fh_cfg = config.get("firehydrant", {})

    token = os.environ.get("FH_TOKEN") or fh_cfg.get("token", "")
    if not token:
        print("ERROR: FH_TOKEN env var not set and firehydrant.token not in config.yaml", file=sys.stderr)
        sys.exit(1)

    team_id = fh_cfg.get("team_id", "")
    if not team_id:
        print("ERROR: firehydrant.team_id not set in config.yaml", file=sys.stderr)
        sys.exit(1)

    uid_to_info, name_to_uid = build_engineer_maps(config)
    if not uid_to_info:
        print("ERROR: No engineers with fh_user_id set in config.yaml", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching FH incidents {args.start} – {args.end} for team {team_id}…", file=sys.stderr)
    incidents = fetch_incidents(team_id, args.start, args.end, token)
    print(f"  {len(incidents)} incidents found", file=sys.stderr)

    by_engineer = build_per_engineer(
        incidents, uid_to_info, name_to_uid, token, scan_events=not args.no_events
    )

    for uid, (name, slug) in uid_to_info.items():
        rows = by_engineer.get(uid, [])
        section = render_section(rows)

        if args.patch:
            path = os.path.join(args.patch, f"{slug}.md")
            if not os.path.exists(path):
                print(f"  skip {path} (not found)", file=sys.stderr)
                continue
            patch_file(path, section)
        else:
            print(f"\n### {name}\n")
            print(section)


if __name__ == "__main__":
    main()
