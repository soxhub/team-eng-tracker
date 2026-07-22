# /weekly-audit

Collect and write the weekly engineering audit for all active engineers from Jira and GitHub.

## Arguments

`$ARGUMENTS` — optional week path like `2026/07/W03`. If omitted, derive the current ISO week from today's date.

---

## Step 0 — Read config.yaml and determine week

**First**, read `config.yaml`. You need:
- `team.name` — for report headers
- `jira.cloud` — Atlassian cloud URL (e.g. `auditboard.atlassian.net`)
- `jira.projects` — Jira project keys for JQL queries
- `github.org` — GitHub org for `gh search prs`
- `engineers[]` — list of engineers; skip `active: false` for new weeks
- `initiatives[]` — for monthly alignment (used if generating monthly report)

**Then** determine the week target:

If `$ARGUMENTS` is provided (e.g. `2026/07/W03`), parse it:
- Year = first segment
- Month = second segment (zero-padded)
- Week label = third segment (e.g. `W03`)

If omitted, compute from today's date:
- ISO week number → week label (e.g. week 3 within July → `W03`)
- Derive `YYYY/MM/WNN` path

From the week label and year, compute **Monday** and **Sunday** dates (Mon–Sun inclusive). These become `WEEK_START` and `WEEK_END` (format `YYYY-MM-DD`). Also compute the human-readable range (e.g. `July 14–20, 2026`).

---

## Step 1 — Active engineer roster

From `config.yaml`, collect all engineers where `active: true` (or `active` is not set). Skip any marked `active: false`. Note any `notes` fields that indicate OOO for the target week — skip those engineers too and mention them in the final report.

---

## Step 2 — Set up week directory

Check whether `reports/YYYY/MM/WNN/` already exists. If not, run:

```bash
python hack/new_week.py --date WEEK_START
```

This creates the directory with `_index.md` and per-engineer stub files. If the directory already exists, proceed to Step 3.

If `new_week.py` fails or is unavailable, create the directory and files manually:
- `reports/YYYY/MM/WNN/_index.md` — stub week index
- `reports/YYYY/MM/WNN/{first-last}.md` for each active engineer — stub with just the header line

---

## Step 3 — Jira data (sequential, one engineer at a time)

> **Important**: Run Jira queries **sequentially**, not in parallel. Parallel MCP calls cause transport drops. Do one engineer, wait for results, then do the next.

For each active engineer:

1. If `jira_account_id` is empty in config.yaml, call `mcp__plugin_atlassian_atlassian__lookupJiraAccountId` with their display name to find it. Note the ID so you can tell the user to add it to config.yaml.

2. Run two JQL queries via `mcp__plugin_atlassian_atlassian__searchJiraIssuesUsingJql`. Use `cloudId: "{jira.cloud}"`, `responseContentFormat: "markdown"`, `maxResults: 30`.

   > If that tool returns transport errors, fall back to `mcp__claude_ai_Auditboard_Atlassian_MCP__searchJiraIssuesUsingJql` with the same args.

   **Query A — assigned tickets updated this week:**
   ```
   project in ({jira.projects}) AND assignee = "{accountId}"
   AND updated >= "WEEK_START" AND updated <= "WEEK_END"
   ORDER BY updated DESC
   ```

   **Query B — tickets reported by engineer this week:**
   ```
   project in ({jira.projects}) AND reporter = "{accountId}"
   AND created >= "WEEK_START" AND created <= "WEEK_END"
   ORDER BY created DESC
   ```

3. Deduplicate across both queries. For each ticket collect: key, summary, issuetype name, status name, and build the URL as `https://{jira.cloud}/browse/{KEY}`.

4. If both queries return empty, try a broader cross-project query (drop the `project in (...)` filter) — some engineers work across projects not listed in config.

---

## Step 4 — GitHub PR data (one engineer at a time)

For each active engineer, run via `gh`:

```bash
# PRs created this week
gh search prs --author {github} --created ">={WEEK_START}" "org:{github.org}" \
  --json number,title,state,createdAt,url,repository

# PRs updated this week (catches active older PRs)
gh search prs --author {github} --updated ">={WEEK_START}" "org:{github.org}" \
  --json number,title,state,createdAt,url,repository
```

Merge both result sets, deduplicating by PR number. Exclude bot PRs (Renovate, Dependabot) unless the engineer authored them intentionally. Extract repo name from `repository.nameWithOwner` — use just the repo name part (after the `/`).

---

## Step 5 — Write per-engineer `.md` files

For each engineer, write (or overwrite) `reports/YYYY/MM/WNN/{first-last}.md` using this template:

```markdown
# {First Last} — WNN (Mon DD–Sun DD, YYYY)

**Theme**: {one-line characterization of the week — the dominant thread of work}

## Jira Tickets

| Key | Summary | Type | Status |
|-----|---------|------|--------|
| [KEY](url) | Summary | Type | **Done** |

## Pull Requests

| Date | Repo | PR | Status |
|------|------|----|--------|
| Mon DD | repo-name | [Title](url) | Merged |

## Summary

{Two-to-four sentence narrative. What does the totality of the week's work add up to? Name the biggest ticket or delivery. Note any cross-team impact. Avoid repeating the ticket list — synthesize it. Focus on impact, not just activity.}
```

Rules:
- **Jira Tickets**: include every ticket from Step 3. Status values: `**Done**`, `**In Progress**`, `**In Review**`, `**Backlog**`, `**Not Doing**`.
- **Pull Requests**: populate from Step 4. If no PRs found, leave the table with a single `— | — | No PRs found this week | — |` row.
- **Theme**: synthesize from the Jira tickets — what was the engineer focused on?
- **Summary**: 2–4 sentences written for a manager reading a weekly digest. Be specific about what shipped or moved.
- **Engineer with no activity**: note "No tracked Jira or GitHub activity this week — possible leave or review-only week" in the Summary. Do not fabricate tickets.

---

## Step 6 — Write weekly `_index.md`

Write `reports/YYYY/MM/WNN/_index.md` using this template:

```markdown
---
title: "Week NN — {Month} {YYYY}"
weight: {week number within month}
---

# Week NN — {Month Day–Day, YYYY}

## Engineer Audits

- [First Last](./first-last.md) — {one-line highlight from their Theme or top ticket}
- ...

## Week Overview

{Two to three sentences summarizing the week's collective output. What were the 2–3 most significant deliveries across the team? Name the engineer and the outcome.}
```

List only active engineers for this week (skip OOO engineers). One-line highlights come directly from each engineer's **Theme** line.

---

## Step 7 — Update monthly `_index.md`

Check `reports/YYYY/MM/_index.md`. If it exists, add this week to the `| Week | Dates | Notes |` table. If it doesn't exist, create it (the stub was created by `new_week.py`).

---

## Step 8 — Confirm and report

After all files are written, report:
- Week directory created/updated: `reports/YYYY/MM/WNN/`
- Date range covered: `WEEK_START` → `WEEK_END`
- Engineers processed (list each with ticket count and PR count)
- Any engineers skipped (OOO, `active: false`, or no Jira ID found)
- Any Jira account IDs discovered that should be added to `config.yaml`
- Next suggested action: `git add reports/ && git commit -m "Add WNN MONTH YYYY weekly audits"`
