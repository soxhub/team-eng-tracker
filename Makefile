.PHONY: help new-week lookup-jira dev build install

PYTHON := python3
HACK    := hack

help:
	@echo ""
	@echo "Team Engineering Tracker"
	@echo "========================"
	@echo ""
	@echo "  make new-week      Scaffold this week's directory with stub files"
	@echo "  make lookup-jira   Print Jira account ID lookup instructions"
	@echo "  make dev           Start Jekyll dev server at http://localhost:4000"
	@echo "  make build         Build Jekyll site to _site/"
	@echo "  make install       Install Python dependencies"
	@echo ""

new-week:
	$(PYTHON) $(HACK)/new_week.py

new-week-dry:
	$(PYTHON) $(HACK)/new_week.py --dry-run

lookup-jira:
	@echo ""
	@echo "To look up missing Jira account IDs:"
	@echo ""
	@echo "  1. Open Claude Code in this repo"
	@echo "  2. Say: \"look up Jira account IDs for all engineers in config.yaml\""
	@echo "  3. Claude will use the Atlassian MCP plugin to resolve each engineer's"
	@echo "     display name to a Jira accountId UUID."
	@echo "  4. Add the returned IDs to config.yaml under each engineer's"
	@echo "     jira_account_id field."
	@echo ""

install:
	pip install pyyaml

dev:
	bundle exec jekyll serve --livereload

build:
	bundle exec jekyll build
