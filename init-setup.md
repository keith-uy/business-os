# Workspace setup (for the agent)

You are Claude Code, Codex, or a similar coding agent. The person has just cloned this template. Your job is to turn it into their business workspace, prove it works, and then teach them how to use it. Follow the steps in order. Ask only the questions listed; pick sensible defaults for everything else and say what you picked.

## 1. Collect the basics

Ask, in one message:

1. Business name (used in folder names and headings).
2. Owner's name.
3. What the business sells, in one line (for example "websites and CRM automations for small firms").
4. Currency code (default `USD`).
5. Timezone (default: the machine's timezone).
6. Whether they already have clients, leads, or subscriptions to enter now (they can answer "later").

## 2. Fill in the placeholders

Replace every `{{PLACEHOLDER}}` in `CLAUDE.md` with the answers, then copy `CLAUDE.md` over `AGENTS.md` so the two files are byte-identical. Placeholders: `{{BUSINESS_NAME}}`, `{{OWNER_NAME}}`, `{{WHAT_YOU_SELL}}`, `{{CURRENCY}}`, `{{TIMEZONE}}`.

Also replace `{{BUSINESS_NAME}}` in `README.md`. Do not touch the `_template` folders under `clients/` and `leads/`; their `{{COMPANY}}`, `{{SLUG}}` and `{{DATE}}` placeholders are filled by the CRM script when an engagement folder is created.

If the folder is still called `business-os-template`, suggest renaming it to `<BusinessName>_OS`, and offer to run the rename.

## 3. Secrets

Copy `.env.example` to `.env.local` at the root. Confirm `.gitignore` lists `.env.local`. Tell the person: root `.env.local` is for keys that serve the whole business; each engagement folder gets its own `.env.local` for that client's keys, and you will never read one engagement's keys while working in another.

## 4. Verify the tooling

Run these and show the output:

```
python3 --version
python3 .claude/skills/crm/scripts/crm.py status
python3 .claude/skills/pnl/scripts/pnl.py summary
python3 -m unittest discover -s tests -v
```

Python 3.8 or newer is required. No packages need installing; both scripts are standard library only. If `.agents/skills/` shows broken links (Windows clones without symlink support), recreate the two entries as copies or junctions of `.claude/skills/crm` and `.claude/skills/pnl`.

## 5. Git

If the workspace is not already a git repository the person controls, offer to run `git init` and make a first commit. Recommend a private remote for backup. Point out the `.gitignore` line for nested repositories: if a client's website lives as its own repo inside `clients/<slug>/`, add its path there so this repo does not record a broken pointer.

## 6. Seed the first records (if they said yes in step 1)

- A lead: `crm.py add --company "Name" --stage new --source referral --contact "Person <email> (Role)" --next "what to do next" --due YYYY-MM-DD`. The script creates `leads/<slug>/` from `leads/_template/`.
- A client: same command with `--stage client`, then `crm.py contract <slug> --json '{"setup_fee": 0, "monthly": 0, "start_date": "YYYY-MM-DD"}'`. The folder is created under `clients/`.
- A subscription: `pnl.py add --json '{"id": "tool", "name": "Tool", "category": "software", "cost": {"amount": 20, "currency": "USD", "cycle": "monthly"}}'`.

Then open the new engagement's `CLAUDE.md` and fill in the "Who" and "What they asked for" sections from what the person tells you.

## 7. Teach the workspace

End setup with a short walkthrough in plain language. Cover these points in this order, using the person's business name and real examples from step 6 where you have them:

**The idea.** One folder is the whole business. The root `CLAUDE.md` (mirrored as `AGENTS.md`) is what every agent session reads first. Each client and lead has its own folder with its own instructions, running notes, and secrets, so work on one never bleeds into another.

**Daily use.** Open a session at the root to ask about the business as a whole ("how are we doing", "what is overdue", "what are we paying for"). Open a session inside `clients/<slug>/` (or tell the agent which client) to do delivery work; the agent reads that folder's `CLAUDE.md` and `HANDOFF.md` and works only there.

**Leads to clients.** A new prospect is `crm.py add`. Each conversation gets `crm.py note` and a new `crm.py next` with a date. When they pay, `crm.py move <slug> client` relocates the folder from `leads/` to `clients/` and asks for the contract. When they stop, `crm.py move <slug> churned`.

**Money.** Every payment received is one `crm.py pay` line. Every subscription or one-off cost is one `pnl.py add`. `crm.py status` shows the pipeline, MRR, overdue actions, and months a monthly fee was expected but not paid. `pnl.py report --month YYYY-MM` shows income minus expenses; `--year YYYY --html` writes a table to `pnl/reports/`.

**Handoffs.** Each engagement's `HANDOFF.md` is the running state: done and verified, blocked and on whom, time-sensitive items, next steps in order. The agent updates it as work moves, so any new session can pick up cold.

**Everything else.** Work that is not a single engagement (marketing, an offer you are designing, an internal tool) goes in `active/<topic>/`. Scratch goes in `active/.tmp/` and can be deleted at any time. Brand assets go in `assets/brand/` so deliverables look consistent.

**Growing it.** New repeatable workflows become skills in `.claude/skills/<name>/SKILL.md` (mirror them into `.agents/skills/`). Rules the person keeps repeating belong in the root `CLAUDE.md`; rules about one client belong in that client's `CLAUDE.md`.

## 8. Finish

Record the setup date at the top of this file (`Setup completed YYYY-MM-DD for <BusinessName>`) so a future session knows it has run. Leave the rest of the file in place as the reference for how the workspace is meant to be used.
