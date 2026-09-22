# {{COMPANY}}

Start here: read `HANDOFF.md` for current state, time-sensitive items, and next steps before acting.

Lead folder. CRM account id: `{{SLUG}}`. Created {{DATE}}. Becomes `clients/{{SLUG}}/` when they pay (`crm.py move {{SLUG}} client` moves it).

## Who

- Company:
- Contact (name, role, email):
- How they found us:
- Timezone:

## What they asked for

(What they said they need, in their words where possible. What we think they actually need.)

## Conventions for this engagement

- Secrets for this lead live in this folder's `.env.local` only.
- Proposals go in `proposals/`, call notes in `calls/`, email drafts in `emails/`.
- After every exchange: update `HANDOFF.md`, then `crm.py note {{SLUG}} "..."` and `crm.py next {{SLUG}} --what "..." --due YYYY-MM-DD`.
- Do not read other engagement folders unless the task explicitly spans both.
