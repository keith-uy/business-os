# {{BUSINESS_NAME}} OS

Private operating workspace for {{BUSINESS_NAME}}, run by {{OWNER_NAME}}. It holds client and lead records, the CRM, the P&L, and in-progress business work. Nothing in here is a deployable product; deployable code lives in its own repository.

If this file still shows `{{PLACEHOLDERS}}`, setup has not run. Read `init-setup.md` and follow it before doing anything else.

## Business

- Name: {{BUSINESS_NAME}}
- Owner: {{OWNER_NAME}}
- What it sells: {{WHAT_YOU_SELL}}
- Currency: {{CURRENCY}}
- Timezone: {{TIMEZONE}}

## Folder map

| Folder | Purpose | Rule |
|--------|---------|------|
| `clients/<slug>/` | One folder per paying client | Own `CLAUDE.md`, `HANDOFF.md`, and `.env.local`. Context and secrets stay inside the folder. |
| `leads/<slug>/` | One folder per prospect | Same shape as a client folder. Moves to `clients/` when they pay. |
| `crm/` | Who we are talking to, what stage, what is owed | `accounts.json` and `payments.csv`. Written only through the `crm` skill's script. |
| `pnl/` | Expenses and profit | `expenses.json` plus generated reports. Written only through the `pnl` skill's script. |
| `active/<topic>/` | Business work that is not one engagement (marketing, offers, internal tools) | One subfolder per topic. Never loose files at the top. |
| `active/.tmp/` | Scratch | Disposable. Safe to empty at any time. |
| `assets/brand/` | Logo, colors, fonts | Used for every client-facing deliverable. |
| `.claude/skills/` | Agent skills (`crm`, `pnl`, and any you add) | `.agents/skills/` mirrors it with symlinks for other agents. |

## Working rules

- Work on one engagement at a time. Read that engagement's `CLAUDE.md` first, then its `HANDOFF.md`. Do not read another engagement's folder unless the task explicitly spans both.
- Secrets live in `.env.local` files, which are gitignored at every depth. Root `.env.local` holds keys that serve the whole business. An engagement's keys live in that engagement's own `.env.local`. Never copy a key from one folder to another, print one, or commit one.
- The CRM is the source of truth for stage, next action, and money owed. Update it after every client exchange (`crm.py note`, `crm.py next`, `crm.py move`, `crm.py pay`). Never hand-edit `crm/accounts.json` or rewrite a past row in `crm/payments.csv`.
- Every engagement folder keeps a `HANDOFF.md`: what is done and verified, what is blocked and on whom, what is time-sensitive, next steps in order. Update it as work moves. A fresh session should be able to pick up from it alone.
- Put generated business output in a specific `active/<topic>/` subfolder, never at the repository root.
- Client-facing deliverables use the brand in `assets/brand/`. Keep internal notes plain markdown.
- Before claiming how an external system behaves, run the cheapest test that would prove it, or say the claim is inferred.

## Answering business questions

- "How is the business doing?" → run `crm.py status` and `pnl.py report`, then summarize.
- "What is the status of client X?" → `crm.py get X`, then that client's `HANDOFF.md`.
- "What is outstanding?" → the overdue actions and unpaid months sections of `crm.py status`, plus each active client's `HANDOFF.md` next steps.
- "What are we paying for?" → `pnl.py list` and `pnl.py summary`.

Scripts: `.claude/skills/crm/scripts/crm.py` and `.claude/skills/pnl/scripts/pnl.py`. Run them with `python3` from anywhere inside the workspace.

## Conventions

- `CLAUDE.md` and `AGENTS.md` are byte-identical mirrors. Edit one and copy it over the other so Claude Code and Codex read the same instructions.
- Slugs are lowercase kebab-case (`acme-marketing`). The CRM account id, the folder name, and the ledger `account_id` are always the same slug.
- Dates are `YYYY-MM-DD`. Money is a plain number in the workspace currency unless a row says otherwise.
- This is a solo workspace without CI. Validate locally and commit directly.
