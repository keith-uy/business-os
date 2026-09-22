# crm/

- `accounts.json`: every account. Stage, contact, source, dated next action, notes, contract. Generated and maintained by `.claude/skills/crm/scripts/crm.py`; do not hand-edit.
- `payments.csv`: append-only ledger of money received. Columns: `date, account_id, type, amount, currency, reference, period, notes`. Never edit a past row; add a correcting row instead.
- `reports/`: optional exports.
- `.backups/`: automatic snapshots before every scripted write (gitignored).

See `.claude/skills/crm/SKILL.md` for the schema and commands.
