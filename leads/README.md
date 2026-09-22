# leads/

One folder per prospect, named by its CRM slug. Created by `crm.py add` from `_template/`. When a lead pays, `crm.py move <slug> client` moves the whole folder to `clients/<slug>/` so nothing is lost.

Same shape as a client folder: `CLAUDE.md`, `HANDOFF.md`, `.env.local`, `calls/`, `emails/`, `proposals/`.
