# {{COMPANY}}

Start here: read `HANDOFF.md` for current state, time-sensitive items, and next steps before acting.

Client folder. CRM account id: `{{SLUG}}`. Created {{DATE}}.

## Who

- Company:
- Contact (name, role, email):
- Timezone:
- Preferred channel:

## What they asked for

(One paragraph. What was agreed, the price, the dates. Link the accepted proposal in `proposals/`.)

## Conventions for this engagement

- Secrets for this client live in this folder's `.env.local` only.
- Client-facing documents go in `deliverables/`, drafts of emails in `emails/`, call notes in `calls/`, proposals in `proposals/`.
- Deliverables use the brand assets in the root `assets/brand/`.
- After every client exchange: update `HANDOFF.md`, then log the touch in the CRM (`crm.py note {{SLUG}} "..."` and `crm.py next {{SLUG}} --what "..." --due YYYY-MM-DD`).
- Do not read or reference other engagement folders unless the task explicitly spans both.
