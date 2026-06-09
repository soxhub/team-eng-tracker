#!/usr/bin/env python3
"""
Scaffold the current week's directory and stub files.

Usage:
    python hack/new_week.py
    python hack/new_week.py --date 2026-06-15   # force a specific date
    python hack/new_week.py --dry-run            # preview without creating files
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML is required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
REPORTS_DIR = ROOT / "reports"

MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def week_of_month(d: date) -> int:
    """Return which week of the month d falls in (1-indexed, weeks start Mon)."""
    # Find Monday of d's ISO week
    mon = d - timedelta(days=d.weekday())
    # Find Monday of the first week that overlaps the month
    first_of_month = date(d.year, d.month, 1)
    first_mon = first_of_month - timedelta(days=first_of_month.weekday())
    return (mon - first_mon).days // 7 + 1


def week_date_range(d: date) -> tuple[date, date]:
    """Return (monday, sunday) of the ISO week containing d."""
    mon = d - timedelta(days=d.weekday())
    sun = mon + timedelta(days=6)
    return mon, sun


def format_date_range(start: date, end: date) -> str:
    if start.month == end.month:
        return f"{MONTH_NAMES[start.month]} {start.day}–{end.day}, {start.year}"
    return (
        f"{MONTH_NAMES[start.month]} {start.day}–"
        f"{MONTH_NAMES[end.month]} {end.day}, {start.year}"
    )


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"config.yaml not found at {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def create_month_index(month_dir: Path, config: dict, year: int, month: int, dry_run: bool):
    index_path = month_dir / "_index.md"
    if index_path.exists():
        return

    team_name = config["team"]["name"]
    engineers = [e["name"] for e in config["engineers"] if e.get("active", True)]
    team_str = " · ".join(engineers)
    month_name = MONTH_NAMES[month]

    content = f"""---
title: "{month_name} {year}"
weight: {month}
---

# Engineering Monthly Wins: {month_name} {year}

**Team**: {team_name}
**Engineers**: {team_str}

| Week | Dates | Notes |
|------|-------|-------|

---

*Monthly summary will be written at end of month.*
"""
    if dry_run:
        print(f"  [dry-run] would create: {index_path.relative_to(ROOT)}")
    else:
        index_path.write_text(content)
        print(f"  Created: {index_path.relative_to(ROOT)}")


def create_week_index(week_dir: Path, config: dict, week_num: int, month_name: str,
                      date_range_str: str, year: int, dry_run: bool):
    index_path = week_dir / "_index.md"
    if index_path.exists():
        print(f"  Exists:  {index_path.relative_to(ROOT)}")
        return

    active = [e for e in config["engineers"] if e.get("active", True)]
    lines = "\n".join(
        f"- [{e['name']}](./{slug(e['name'])}.md) — *add highlight*"
        for e in active
    )

    content = f"""---
title: "Week {week_num:02d} — {month_name} {year}"
weight: {week_num}
---

# Week {week_num:02d} — {date_range_str}

## Engineer Audits

{lines}

## Week Overview

*Run Claude Code and say "generate W{week_num:02d} reports for last week" to fill this in.*
"""
    if dry_run:
        print(f"  [dry-run] would create: {index_path.relative_to(ROOT)}")
    else:
        index_path.write_text(content)
        print(f"  Created: {index_path.relative_to(ROOT)}")


def create_engineer_stub(week_dir: Path, engineer: dict, week_label: str,
                         date_range_str: str, dry_run: bool):
    filename = slug(engineer["name"]) + ".md"
    path = week_dir / filename
    if path.exists():
        print(f"  Exists:  {path.relative_to(ROOT)}")
        return

    content = f"""# {engineer['name']} — {week_label} ({date_range_str})

**Theme**: *TODO — run Claude Code to generate this report*

## Jira Tickets

| Key | Summary | Type | Status |
|-----|---------|------|--------|

## Pull Requests

| Date | Repo | PR | Status |
|------|------|----|--------|

## Summary

*TODO — run Claude Code to generate this report.*
"""
    if dry_run:
        print(f"  [dry-run] would create: {path.relative_to(ROOT)}")
    else:
        path.write_text(content)
        print(f"  Created: {path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new tracking week")
    parser.add_argument("--date", help="Date within the target week (YYYY-MM-DD); defaults to today")
    parser.add_argument("--dry-run", action="store_true", help="Preview without creating files")
    args = parser.parse_args()

    today = date.fromisoformat(args.date) if args.date else date.today()
    config = load_config()

    year = today.year
    month = today.month
    week_num = week_of_month(today)
    week_start, week_end = week_date_range(today)
    month_name = MONTH_NAMES[month]
    week_label = f"W{week_num:02d}"
    date_range_str = format_date_range(week_start, week_end)

    week_dir = REPORTS_DIR / str(year) / f"{month:02d}" / week_label
    month_dir = week_dir.parent

    print(f"\nScaffolding: {week_label} — {date_range_str}")
    print(f"  Target dir: {week_dir.relative_to(ROOT)}\n")

    if not args.dry_run:
        week_dir.mkdir(parents=True, exist_ok=True)

    create_month_index(month_dir, config, year, month, args.dry_run)
    create_week_index(week_dir, config, week_num, month_name, date_range_str, year, args.dry_run)

    active = [e for e in config["engineers"] if e.get("active", True)]
    for eng in active:
        create_engineer_stub(week_dir, eng, week_label, date_range_str, args.dry_run)

    print(f"\nDone. Next step:")
    print(f"  Open Claude Code in this repo and say:")
    print(f'  "generate {week_label} ({date_range_str}) reports"\n')


if __name__ == "__main__":
    main()
