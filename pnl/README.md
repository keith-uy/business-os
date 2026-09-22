# pnl/

- `expenses.json`: every subscription, contractor, and one-off cost, including free tools (so it doubles as the list of what the business uses). Maintained by `.claude/skills/pnl/scripts/pnl.py`.
- `reports/`: generated P&L files (`2026-09.html`, `2026.html`).
- `.backups/`: automatic snapshots (gitignored).

Income is read from `crm/payments.csv`, so there is no separate income file. See `.claude/skills/pnl/SKILL.md`.
