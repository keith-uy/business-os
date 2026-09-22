# clients/

One folder per paying client, named by its CRM slug. `_template/` is copied automatically by `crm.py add --stage client` or `crm.py move <slug> client`; you can also copy it by hand.

Each client folder has:

- `CLAUDE.md`: who they are, what was agreed, conventions for this engagement.
- `HANDOFF.md`: running state. Done, blocked, time-sensitive, next steps.
- `.env.local`: this client's keys (gitignored). Copy from `.env.example`.
- `calls/`, `emails/`, `proposals/`, `deliverables/`.

Add any structure the engagement needs (a `website/` repo, `brand/`, `evidence/`). If a nested folder is its own git repository, add its path to the root `.gitignore`.
