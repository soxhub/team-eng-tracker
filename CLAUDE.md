# CLAUDE.md

This file guides Claude Code when generating weekly engineering reports for this team tracker.

## What This Repo Is

A weekly engineering audit system. Each week, Claude queries Jira and GitHub for each engineer's activity, writes per-engineer markdown summaries, and rolls them into a week index and monthly wins report. Reports live in `reports/YYYY/MM/WNN/`.

## Step 0 — Always Read config.yaml First

Before doing anything, read `config.yaml`. It tells you:
- **`team.name`** — used in report headers
- **`jira.cloud`** — the Atlassian cloud URL to pass as `cloudId` to Jira MCP tools
- **`jira.projects`** — the project keys to include in JQL queries (`project in (SRE, ENG)`)
- **`github.org`** — the GitHub org for `gh search prs` queries
- **`engineers[]`** — list of engineers to track (skip `active: false` engineers for new weeks)
- **`initiatives[]`** — named initiatives to map in the monthly alignment section
- **`firehydrant.team_id`** — if set, `scripts/fh-incidents.py` can add an incident section to each engineer file

## Jira Tools

Use `mcp__plugin_atlassian_atlassian__searchJiraIssuesUsingJql` for all Jira ticket queries.

> **Note**: If that tool returns transport errors, fall back to `mcp__claude_ai_Auditboard_Atlassian_MCP__searchJiraIssuesUsingJql`. Do NOT call both in parallel — they share the same MCP connection and overloading causes transport drops. Make lookups sequentially, one engineer at a time.

To resolve an engineer's Jira account ID (if not already in config.yaml), use `mcp__plugin_atlassian_atlassian__lookupJiraAccountId` with their display name.

### JQL Patterns

Replace `{cloud}` with `jira.cloud` from config, `{accountId}` with the engineer's `jira_account_id`, and `{projects}` with the `jira.projects` list.

```
# Tickets assigned to engineer, updated in the target week
project in ({projects}) AND assignee = "{accountId}"
  AND updated >= "{YYYY-MM-DD}" AND updated <= "{YYYY-MM-DD}"
  ORDER BY updated DESC

# Broader: any ticket the engineer touched (assignee OR reporter)
(assignee = "{accountId}" OR reporter = "{accountId}")
  AND updated >= "{YYYY-MM-DD}" AND updated <= "{YYYY-MM-DD}"
  ORDER BY updated DESC

# Initiative/epic tickets by key
key in (PROJ-123, PROJ-456)
```

Request these fields: `["summary", "status", "issuetype", "updated", "created"]`  
Use `responseContentFormat: "markdown"` and `maxResults: 30`.

If a project search returns no results, broaden with a cross-project query (drop the `project in (...)` filter). Some engineers work in projects not listed in config — surface them.

## GitHub PR Queries

Use the `gh` CLI:

```bash
# PRs by engineer in the target org since a date
gh search prs --author {github_handle} --created ">={YYYY-MM-DD}" "org:{github_org}" \
  --json number,title,state,createdAt,url,repository

# PRs updated (not just created) this week — catches active older PRs
gh search prs --author {github_handle} --updated ">={YYYY-MM-DD}" "org:{github_org}" \
  --json number,title,state,createdAt,url,repository
```

Merge both result sets, deduplicating by PR number. Include PRs whose `createdAt` is within the week OR whose `updatedAt` is within the week. Exclude Renovate/Dependabot bot PRs unless the engineer authored them intentionally.

## FireHydrant Incident Tracking (Optional)

If `firehydrant.team_id` is set in `config.yaml` and engineers have `fh_user_id` values, you can enrich each engineer file with a `## FireHydrant Incidents` section:

```bash
# Dry-run — print all engineers' incident sections to stdout
python3 scripts/fh-incidents.py --start YYYY-MM-DD --end YYYY-MM-DD

# Patch mode — insert/replace "## FireHydrant Incidents" in each engineer's .md file
python3 scripts/fh-incidents.py --start YYYY-MM-DD --end YYYY-MM-DD --patch reports/YYYY/MM/WNN

# Faster: skip event timeline scan (role assignments only)
python3 scripts/fh-incidents.py --start YYYY-MM-DD --end YYYY-MM-DD --patch reports/YYYY/MM/WNN --no-events
```

Set `FH_TOKEN` env var or add `firehydrant.token` to config.yaml. The script uses two signal sources:
- **Role assignments** — Commander, Responder, Subject matter expert (direct FH role data)
- **Event timeline** — chat messages, status updates, runbook steps (catches engineers active without a formal role)

Each engineer file gets a section inserted after `## Pull Requests`:

```markdown
## FireHydrant Incidents

| Date | # | Incident | Severity | Role |
|------|---|----------|----------|------|
| Jun 2 | [1597](url) | Service CPU spikes | SEV3 | Subject matter expert |
```

When generating weekly reports, mention to the user that they can run the script afterward to add incident data. Don't run it yourself — it requires a live FireHydrant API token.

## Directory Structure

```
reports/
  YYYY/
    MM/
      _index.md           ← Monthly "Engineering Monthly Wins" report
      WNN/
        _index.md         ← Week overview (list of all engineers + one-line highlights)
        {first-last}.md   ← Per-engineer weekly audit file
```

Filenames use `first-last` (lowercase, hyphenated). Example: `alice-smith.md`.

Week directories are named `W01`–`W05` within each month, starting from `W01` on the 1st.

## Per-Engineer File Format

```markdown
# {First Last} — WNN ({Month Day–Day, YYYY})

**Theme**: One-line characterization of the week's work

## Jira Tickets

| Key | Summary | Type | Status |
|-----|---------|------|--------|
| [KEY](url) | Summary | Bug/Task/Story/Technical Story | **Done** |

## Pull Requests

| Date | Repo | PR | Status |
|------|------|----|--------|
| Mon DD | repo-name | [PR title](url) | Merged/Open/Closed |

## Summary

Two to four sentences. What did the work add up to? What shipped, what moved, what's next?
Focus on *impact* not just activity. Be specific about what changed in production or what
unblocked downstream work. For investigations, name the root cause and the outcome.
```

Status values in Jira table: **Done**, **In Progress**, **In Review**, **Backlog**, **Not Doing**  
Status values in PR table: `Merged`, `Open`, `Closed` (use plain text, not bold)

## Weekly Index Format (`_index.md`)

```markdown
---
title: "Week NN — {Month} {YYYY}"
weight: N
---

# Week NN — {Month Day–Day, YYYY}

## Engineer Audits

- [First Last](./first-last.md) — one-line highlight of their week's headline contribution
- ...

## Week Overview

Two to three sentences summarizing the week's collective output. What were the 2–3 most
significant deliveries across the team? Name the engineer and the outcome.
```

## Monthly Report Format (`_index.md` at the month level)

The monthly report is written at the end of the month (after the last week is done). It has these sections:

```markdown
---
title: "{Month} {YYYY}"
weight: {month number}
---

# Engineering Monthly Wins: {Month} {YYYY}

**Team**: {team.name}
**Engineers**: {comma-separated active engineer names}

| Week | Dates | Notes |
|------|-------|-------|
| [W01](./W01/_index.md) | {dates} | one-liner |
...

---

## The Big Milestones

2–3 platform-level deliveries with full context. Each gets its own bold header and 2–3
sentences explaining what shipped, why it matters, and who drove it.

---

## Standout Engineer Highlights

One bullet per engineer. Format: **[@handle](github url) — Name:** N PRs / N tickets —
top contribution sentence.

---

## The Month in Numbers

| Metric | Value | Status |
|--------|-------|--------|
| Jira Tickets Shipped | N | |
| PRs Merged | N | |
...

---

## Behind-the-Scenes Wins

Quiet infrastructure/reliability/tooling improvements that don't get headlines but matter.
2–4 bullet points.

---

## Initiative Alignment — {team.name}

One section per initiative in config.yaml. Table showing which engineer contributed
what, mapped to that initiative, by week.

### {Initiative Name} — {Description}

| Engineer | Contribution |
|----------|-------------|
...
```

## Generating Reports — Step by Step

When the user says "generate W0X reports" or "generate reports for last week":

1. **Read config.yaml** to get the team, engineer list, Jira cloud, projects, GitHub org.
2. **Determine the week** — "last week" means the calendar week that just ended (Mon–Sun). Derive `YYYY/MM/WNN` path and the date range.
3. **Look up missing Jira account IDs** — if any engineer in config has an empty `jira_account_id`, use `lookupJiraAccountId` to find them and note the ID in your response so the user can update config.yaml.
4. **Query Jira for each engineer** — one engineer at a time (sequential, not parallel) to avoid MCP transport drops. Use the updated date range as the filter.
5. **Query GitHub PRs for each engineer** — `gh search prs` for the week date range. Collect created-this-week + updated-this-week PRs.
6. **Create the week directory** if it doesn't exist: `reports/YYYY/MM/WNN/`.
7. **Write per-engineer files** — one file per active engineer. Skip `active: false` engineers.
8. **Write `_index.md`** for the week — after all engineer files are done.
9. **Update the month `_index.md`** — add the new week to the week table. Create the month `_index.md` if this is the first week of the month.

Write all files before committing. When done, summarize what was created and suggest: `git add reports/ && git commit`.

## Handling Edge Cases

**Engineer with no Jira activity:** Check GitHub PRs before concluding no activity. If both are empty, note "No tracked Jira or GitHub activity this week — possible leave or review-only week" in the Summary. Do not fabricate tickets.

**Engineer with no `jira_account_id` in config:** Use `lookupJiraAccountId` to discover it. Report the ID to the user so they can add it to config.yaml permanently.

**New engineer:** Create their file as normal. In the Summary, note it's their first tracked week if their first contribution date is this week.

**Departed engineer:** If `active: false`, skip for new week generation. They still appear in older reports.

**MCP transport drops:** If `mcp__plugin_atlassian_atlassian__*` tools drop mid-call, wait and retry once. If they keep failing, switch to `mcp__claude_ai_Auditboard_Atlassian_MCP__*` equivalents. Never run more than 2–3 Jira MCP calls in parallel.

## Updating config.yaml

After a session where you discover new Jira account IDs, missing engineers, or updated initiative keys, tell the user exactly what to add/update in config.yaml. Don't edit config.yaml automatically — it's the user's source of truth.

## Key Commands

```bash
make new-week       # Scaffold current week directory with stub files
make lookup-jira    # Print Jira lookup instructions for all engineers missing IDs
make help           # Show all available targets
```
