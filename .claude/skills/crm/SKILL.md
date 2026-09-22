---
name: crm
description: Local file CRM for the business. Accounts and stages in crm/accounts.json, payments in crm/payments.csv, written only via crm.py. Use when the user says "add a lead", "move X to client", "log a payment", "what's next with X", "what's overdue", "what's my MRR", or asks how the business or a specific account is doing.
---

# CRM

Two files under `crm/`, one script, no hand edits.

| File | Shape | Rule |
|------|-------|------|
| `crm/accounts.json` | array of account objects | written by `crm.py` only |
| `crm/payments.csv` | append-only ledger | never edit a past row |
| `crm/.backups/` | snapshots before every write | automatic, gitignored |

## Account schema

```json
{
  "id": "acme-marketing",
  "company": "Acme Marketing",
  "contact": {"name": "", "email": "", "role": ""},
  "stage": "new | contacted | call-booked | proposal | client | churned | lost",
  "source": "referral | inbound | cold-email | ...",
  "created": "YYYY-MM-DD",
  "last_touch": "YYYY-MM-DD",
  "next_action": {"what": "", "due": "YYYY-MM-DD"},
  "notes": "dated lines, newest first",
  "folder": "leads/acme-marketing",
  "contract": null
}
```

`contract` is set when the account becomes a client:

```json
{"setup_fee": 1500, "monthly": 400, "currency": "USD", "start_date": "YYYY-MM-DD",
 "billing_day": 1, "status": "active | paused | ended", "paused_from": null, "ended_on": null}
```

`monthly` drives MRR and the "unpaid months" check in `status`. A one-off project with no retainer keeps `monthly` at 0.

## Payment columns

`date, account_id, type, amount, currency, reference, period, notes`

- `type`: `setup_fee | monthly | project | other`
- `reference`: external transaction id if there is one. It is the dedup key; the script refuses a duplicate.
- `period`: `YYYY-MM` the monthly fee covers. Defaults to the payment month for `monthly` rows.

## Commands

Run from anywhere inside the workspace:

```
python3 .claude/skills/crm/scripts/crm.py list [--stage client] [--all]
python3 .claude/skills/crm/scripts/crm.py get <slug-or-company>
python3 .claude/skills/crm/scripts/crm.py add --company "Acme" [--stage new] [--source referral] \
    [--contact "Name <email> (Role)"] [--next "..."] [--due YYYY-MM-DD] [--notes "..."]
python3 .claude/skills/crm/scripts/crm.py move <slug> <stage> [--note "why"]
python3 .claude/skills/crm/scripts/crm.py next <slug> --what "..." [--due YYYY-MM-DD]   # --what "" clears
python3 .claude/skills/crm/scripts/crm.py note <slug> "dated note"
python3 .claude/skills/crm/scripts/crm.py contract <slug> --json '{"setup_fee": 0, "monthly": 0, "start_date": "YYYY-MM-DD"}'
python3 .claude/skills/crm/scripts/crm.py pay --account <slug> --type monthly --amount 400 [--date YYYY-MM-DD] \
    [--period YYYY-MM] [--reference <txn id>] [--notes "..."] [--dry-run]
python3 .claude/skills/crm/scripts/crm.py status
```

`add` creates `leads/<slug>/` (or `clients/<slug>/` when `--stage client`) from the matching `_template/`. `move ... client` relocates the folder from `leads/` to `clients/` and reminds you to set the contract.

## Routing

- "add a lead / new prospect" → `add`, then fill in the new folder's `CLAUDE.md`.
- "we talked to X / X replied" → `note` and `next` with a date. Update the engagement's `HANDOFF.md` too.
- "X signed / X paid the deposit" → `move X client`, `contract`, `pay`.
- "log a payment" → `pay`. If it came from a payment processor, pass the real transaction id as `--reference`.
- "how is the business / what's overdue / who hasn't paid" → `status`, then read it back in plain words.
- "status of X" → `get X`, then that engagement's `HANDOFF.md`.

## Safety

- Never hand-edit `accounts.json`. If a bulk change is needed, do it with a short script that reads, changes and writes through the same JSON shape, after a backup.
- A payment row is immutable. Fix a mistake with a correcting row (`--type other`, negative amount, note explaining why).
- Confirm with the user before `move` to `churned` or `lost`.
