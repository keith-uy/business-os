# Business OS template

A folder structure for running a small service business with a coding agent (Claude Code, Codex, or similar). One folder holds the whole business: every client, every lead, the CRM, the P&L, and whatever you are working on. The agent reads one instructions file at the root and one inside each engagement, so it always knows where it is and never mixes one client's context or API keys with another's.

No accounts, no database, no dependencies. Plain JSON, CSV and markdown, plus two small Python scripts (standard library only).

## Layout

```
YourBusiness_OS/
├── CLAUDE.md            # what every agent session reads first (AGENTS.md is an identical copy)
├── init-setup.md        # one-time setup script for the agent
├── .env.local           # business-wide keys (gitignored)
├── clients/
│   ├── _template/       # copied for each new client
│   └── acme/            # CLAUDE.md, HANDOFF.md, .env.local, calls/, emails/, proposals/, deliverables/
├── leads/
│   ├── _template/
│   └── northwind/       # same shape; moves to clients/ when they pay
├── crm/
│   ├── accounts.json    # who, what stage, next action, contract
│   └── payments.csv     # append-only ledger of money received
├── pnl/
│   ├── expenses.json    # every subscription and one-off cost
│   └── reports/         # generated monthly and yearly P&L
├── active/
│   ├── <topic>/         # non-client work: marketing, offers, internal tools
│   └── .tmp/            # scratch, safe to delete
├── assets/brand/        # logo, colors, fonts for deliverables
└── .claude/skills/      # crm and pnl skills (.agents/skills/ mirrors them)
```

## Quick start

1. Clone this repository and rename the folder to `<YourBusiness>_OS`.
2. Open it in your coding agent and say: **"Read init-setup.md and set up this workspace."**
3. Answer its six questions. It fills in the placeholders, verifies the scripts, seeds your first records if you want, and walks you through how the workspace works.

Requirements: Python 3.8+ and git. Nothing to install.

## How it works

**Clients and leads.** Each engagement is a folder with its own `CLAUDE.md` (who they are, what they asked for, conventions), `HANDOFF.md` (running state: done, blocked, time-sensitive, next steps), and `.env.local` (that client's keys). The agent works inside one engagement at a time.

**CRM.** `crm/accounts.json` holds every account with a stage (`new`, `contacted`, `call-booked`, `proposal`, `client`, `churned`, `lost`), a dated next action, and the contract once they become a client. `crm/payments.csv` is an append-only ledger. The `crm.py` script is the only writer, and it snapshots before every change.

```
python3 .claude/skills/crm/scripts/crm.py add --company "Acme" --source referral --next "Send proposal" --due 2026-10-01
python3 .claude/skills/crm/scripts/crm.py move acme client
python3 .claude/skills/crm/scripts/crm.py contract acme --json '{"setup_fee": 1500, "monthly": 400, "start_date": "2026-10-01"}'
python3 .claude/skills/crm/scripts/crm.py pay --account acme --type setup_fee --amount 1500
python3 .claude/skills/crm/scripts/crm.py status
```

Moving an account to `client` also moves its folder from `leads/` to `clients/`.

**P&L.** `pnl/expenses.json` is the catalog of everything the business pays for (free tools too, so it doubles as a stack inventory). `pnl.py report` takes income from the CRM ledger, subtracts committed expenses, and prints or writes the result.

```
python3 .claude/skills/pnl/scripts/pnl.py add --json '{"id":"hosting","name":"Hosting","category":"infrastructure","cost":{"amount":20,"currency":"USD","cycle":"monthly"}}'
python3 .claude/skills/pnl/scripts/pnl.py summary
python3 .claude/skills/pnl/scripts/pnl.py report --month 2026-10
python3 .claude/skills/pnl/scripts/pnl.py report --year 2026 --html
```

**Questions you can ask the agent at the root.** "How is the business doing?" "What is overdue?" "What is the status of Acme?" "What are we paying for?" "What renews this month?" Each maps to a script call plus the relevant `HANDOFF.md`; the root `CLAUDE.md` tells the agent which.

**Active.** Anything that is not one engagement lives in `active/<topic>/`: a campaign, an offer you are designing, an internal tool. Loose files at the top of `active/` are not allowed; the agent sorts them into a topic.

## Secrets

`.gitignore` excludes `.env.local` at every depth, so root keys and per-client keys are both safe to keep next to the work they belong to. `.env.example` files show the shape. Never put a key in `CLAUDE.md`, `HANDOFF.md`, or the CRM.

## Extending

- Add a skill: `.claude/skills/<name>/SKILL.md` with a `name` and `description` frontmatter, plus optional `scripts/`. Add a symlink in `.agents/skills/` so Codex sees it too.
- Add a rule: if you keep repeating an instruction to the agent, put it in the root `CLAUDE.md` (business-wide) or the engagement's `CLAUDE.md` (that client only). Copy the root file over `AGENTS.md` after editing.
- Nested repositories: a client's website repo can live inside `clients/<slug>/`. Add its path to `.gitignore` so this repo does not track it.

## Tests

```
python3 -m unittest discover -s tests -v
```

## License

MIT. Use it for your own business, rename it, change it.
