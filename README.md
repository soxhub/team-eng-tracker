# Team Engineering Tracker

A weekly engineering audit system for engineering managers. Claude Code queries Jira and GitHub for each engineer's activity each week, writes per-engineer markdown summaries, and rolls them into weekly and monthly reports.

## What You Get

- **Per-engineer weekly files** — Jira tickets, pull requests, and a 2–4 sentence narrative
- **Weekly index** — one-line highlights for every engineer + a team summary paragraph
- **Monthly wins report** — big milestones, standout highlights, metrics, and initiative alignment

Reports live in `reports/YYYY/MM/WNN/` and render as a Jekyll site on GitHub Pages.

## Setup (5 minutes)

### 1. Use this template

Click **Use this template** → **Create a new repository** on GitHub. Name it something like `my-team-eng-tracker`.

Clone it locally:

```bash
git clone git@github.com:<your-org>/<your-repo>.git
cd <your-repo>
```

### 2. Edit `config.yaml`

Fill in your team details:

```yaml
team:
  name: "Platform Engineering"   # used in report headers
  slug: "platform-eng"           # used in directory paths

jira:
  cloud: "yourcompany.atlassian.net"
  projects:
    - PLAT
    - ENG

github:
  org: "your-github-org"

engineers:
  - name: "Alice Smith"
    github: "asmith"
    jira_account_id: ""          # run `make lookup-jira` to find this
    active: true
```

For `jira_account_id` values, run `make lookup-jira` after configuring names — it will print instructions for Claude Code to look them up.

### 3. Scaffold the first week

```bash
make new-week
```

This creates `reports/YYYY/MM/WNN/` with stub files for each engineer.

### 4. Generate reports with Claude Code

Open Claude Code in this repo and say:

```
generate W01 reports for last week
```

Claude reads `config.yaml`, queries Jira for each engineer's tickets, fetches their GitHub PRs, and writes the report files. It works through engineers one at a time (sequential Jira calls to avoid MCP transport drops).

## Weekly Workflow

```bash
# Monday morning — scaffold this week
make new-week

# After the week ends — generate reports
# Open Claude Code and say: "generate W0X reports for last week"

# Review the files, then commit
git add reports/
git commit -m "Weekly update: YYYY-MM-DD"
git push origin HEAD
```

## Requirements

- **Claude Code** — [claude.ai/code](https://claude.ai/code) or `npm install -g @anthropic-ai/claude-code`
- **Atlassian MCP plugin** — configured in Claude Code settings (provides Jira access)
- **`gh` CLI** — [cli.github.com](https://cli.github.com), authenticated with `gh auth login`
- **Python 3.10+** with PyYAML — `pip install pyyaml` (for `make new-week`)
- **GitHub repo access** — `gh` CLI must be able to search PRs in your org

### Atlassian MCP Setup

In your Claude Code settings, add the Atlassian MCP plugin. Claude Code will use it for all Jira queries. No API keys need to be stored in this repo.

## Directory Structure

```
reports/
  YYYY/
    MM/
      _index.md           ← Monthly "Engineering Monthly Wins" report
      WNN/
        _index.md         ← Week overview (list of all engineers + highlights)
        {first-last}.md   ← Per-engineer weekly audit
config.yaml               ← Team configuration (edit this)
CLAUDE.md                 ← Instructions for Claude Code (do not edit unless customizing)
hack/
  new_week.py             ← Week scaffolding script
```

## Customizing

- **Add an engineer**: Add them to `config.yaml` and run `make new-week`.
- **Remove an engineer**: Set `active: false` in config.yaml — they'll appear in historical reports but be skipped going forward.
- **Add an initiative**: Add to the `initiatives:` list in `config.yaml`. Claude includes an initiative alignment table in the monthly report.
- **Change the Jira projects**: Edit `jira.projects` in `config.yaml`.

## GitHub Pages

Push to `main` and the site auto-deploys via `.github/workflows/pages.yml`. Enable GitHub Pages in your repo settings: **Settings → Pages → Source: GitHub Actions**.

## Available Commands

```bash
make new-week       # Scaffold current week directory with stub files
make lookup-jira    # Print Jira lookup instructions for engineers missing IDs
make help           # Show all available targets
```
