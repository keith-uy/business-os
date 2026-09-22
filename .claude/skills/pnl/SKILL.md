---
name: pnl
description: Profit and loss for the business. Expenses catalog in pnl/expenses.json, income read from the CRM payment ledger, monthly and yearly reports via pnl.py. Use when the user says "add an expense", "track this subscription", "what's my monthly burn", "what tools do we pay for", "what renews soon", "am I profitable", or asks for a P&L.
---

# P&L

Income is what the CRM ledger says was received (`crm/payments.csv`). Expenses are what the business commits to pay (`pnl/expenses.json`). Net is the difference, per month. This is a committed-cost model, not a bank reconciliation: it answers "are we ahead or behind this month", not "what cleared the bank".

## Expense schema

```json
{
  "id": "hosting",
  "name": "Hosting",
  "category": "software | infrastructure | contractor | marketing | office | other",
  "purpose": "what it is for",
  "cost": {"amount": 20, "currency": "USD", "cycle": "monthly | yearly | one-time | usage | free", "est_monthly": null},
  "status": "active | trial | paused | cancelled",
  "started": "YYYY-MM-DD",
  "renewal": "YYYY-MM-DD",
  "trial_ends": null,
  "cancelled_on": null,
  "paused_from": null,
  "resumed_on": null,
  "date": "YYYY-MM-DD (one-time only)",
  "notes": ""
}
```

How each cycle counts in a month: `monthly` as-is, `yearly` divided by 12, `usage` by `est_monthly`, `one-time` only in the month of its `date`, `free` never.

Dates decide whether an entry counts in a given month, so past reports stay correct when something changes: `started` (not before), `paused_from` and `resumed_on` (not during the gap), `cancelled_on` (not from that month on). A `paused` or `cancelled` status with no date is treated as effective from the beginning, so always pass the date.

## Commands

```
python3 .claude/skills/pnl/scripts/pnl.py add --json '{"id":"hosting","name":"Hosting","category":"infrastructure","cost":{"amount":20,"currency":"USD","cycle":"monthly"}}'
python3 .claude/skills/pnl/scripts/pnl.py list
python3 .claude/skills/pnl/scripts/pnl.py summary                 # burn, by category, renewals in 30 days
python3 .claude/skills/pnl/scripts/pnl.py report [--month YYYY-MM] [--html]
python3 .claude/skills/pnl/scripts/pnl.py report --year YYYY [--html]
```

`add` is idempotent on `id`, so re-running it with new fields updates the entry. `--html` writes to `pnl/reports/`.

## Routing

- "add an expense / we now pay for X" → `add`.
- "cancel X" → `add` with `{"id": "x", "status": "cancelled", "cancelled_on": "YYYY-MM-DD"}`.
- "pause X" → `add` with `{"id": "x", "status": "paused", "paused_from": "YYYY-MM-DD"}`; resume with `{"id": "x", "status": "active", "resumed_on": "YYYY-MM-DD"}`.
- Amounts are summed as-is. If more than one currency is in use the scripts print a warning; keep one currency per workspace or convert before entering.
- "what's my burn / what do we pay for" → `summary` and `list`.
- "how did last month go / are we profitable" → `report --month`.
- "year to date" → `report --year`.

Income never gets entered here. Log it with the `crm` skill (`crm.py pay`) so the two views agree.
