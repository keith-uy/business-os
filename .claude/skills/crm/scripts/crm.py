#!/usr/bin/env python3
"""Local file CRM for a Business OS workspace. Python 3.8+, stdlib only.

Data lives in crm/accounts.json (one object per account) and crm/payments.csv
(append-only ledger). Every write snapshots accounts.json to crm/.backups/ first.

Run from anywhere inside the workspace:
    python3 .claude/skills/crm/scripts/crm.py status
"""
import argparse
import csv
import json
import os
import shutil
import sys
from decimal import InvalidOperation
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

STAGES = ["new", "contacted", "call-booked", "proposal", "client", "churned", "lost"]
LEAD_STAGES = STAGES[:4]
PAYMENT_TYPES = ["setup_fee", "monthly", "project", "other"]
PAYMENT_COLUMNS = ["date", "account_id", "type", "amount", "currency", "reference", "period", "notes"]


# ---------- paths ----------

def find_root(start: Path = None) -> Path:
    """Walk up until a folder containing crm/ and pnl/ is found."""
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        # .claude/skills/ also holds crm/ and pnl/ folders; skip it by requiring
        # that crm/ is a data folder, not a skill folder.
        if ((candidate / "crm").is_dir() and (candidate / "pnl").is_dir()
                and not (candidate / "crm" / "SKILL.md").exists()):
            return candidate
    sys.exit("Could not find the workspace root (a folder containing crm/ and pnl/).")


ROOT = find_root(Path(__file__).parent)
ACCOUNTS = ROOT / "crm" / "accounts.json"
PAYMENTS = ROOT / "crm" / "payments.csv"
BACKUPS = ROOT / "crm" / ".backups"


# ---------- io ----------

def load_accounts():
    if not ACCOUNTS.exists():
        return []
    try:
        with ACCOUNTS.open(encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"crm/accounts.json is not valid JSON ({e}). Restore the newest snapshot from "
                 f"crm/.backups/ or from git history, then retry.")
    if not isinstance(data, list):
        sys.exit("crm/accounts.json must be a JSON array of accounts.")
    return data


def snapshot(path):
    """Copy a data file into .backups/ before changing it."""
    if path.exists() and path.stat().st_size:
        BACKUPS.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(path, BACKUPS / f"{path.stem}-{stamp}{path.suffix}")


def atomic_write(path, text):
    """Write to a temp file next to the target, then rename it into place."""
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def save_accounts(accounts):
    snapshot(ACCOUNTS)
    atomic_write(ACCOUNTS, json.dumps(accounts, indent=2, ensure_ascii=False) + "\n")


def load_payments():
    if not PAYMENTS.exists():
        return []
    with PAYMENTS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_payment(row):
    """Rewrite the ledger atomically with the new row appended (snapshot first)."""
    snapshot(PAYMENTS)
    rows = load_payments() + [row]
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=PAYMENT_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in PAYMENT_COLUMNS})
    atomic_write(PAYMENTS, buf.getvalue())


# ---------- helpers ----------

def today():
    return date.today().isoformat()


def check_date(value, label):
    """Accept only YYYY-MM-DD. Returns the value unchanged."""
    if value in (None, ""):
        return value
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"{label} must be YYYY-MM-DD, got '{value}'.")
    return value


def parse_date(value, label):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        sys.exit(f"{label} must be YYYY-MM-DD, got '{value}'. Fix it with crm.py contract.")


def slugify(text):
    out = "".join(c.lower() if c.isalnum() else "-" for c in text.strip())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def find_account(accounts, key):
    key_l = key.lower()
    for a in accounts:
        if a["id"] == key_l or a["company"].lower() == key_l:
            return a
    partial = [a for a in accounts if key_l in a["id"] or key_l in a["company"].lower()]
    if len(partial) == 1:
        return partial[0]
    if partial:
        sys.exit(f"'{key}' matches several accounts: {', '.join(a['id'] for a in partial)}. Use the full id.")
    sys.exit(f"No account matches '{key}'. Try: crm.py list --all")


def parse_contact(text):
    """'Name <email> (Role)' -> dict. Any part may be missing."""
    name, email, role = text, "", ""
    if "(" in text and text.endswith(")"):
        text, role = text.rsplit("(", 1)
        role = role[:-1].strip()
        name = text.strip()
    if "<" in name and name.endswith(">"):
        name, email = name.rsplit("<", 1)
        email = email[:-1].strip()
        name = name.strip()
    return {"name": name, "email": email, "role": role}


def folder_for(account):
    base = "clients" if account["stage"] == "client" else "leads"
    return f"{base}/{account['id']}"


def money(x):
    try:
        return Decimal(str(x or 0))
    except InvalidOperation:
        sys.exit(f"Amount must be a number, got '{x}'.")


def fmt(x, currency="USD"):
    return f"{currency} {money(x):,.2f}"


def currencies_in_use(accounts, payments):
    found = {p.get("currency") for p in payments if p.get("currency")}
    found |= {a["contract"].get("currency") for a in accounts if a.get("contract") and a["contract"].get("currency")}
    return sorted(found) or ["USD"]


# ---------- commands ----------

def cmd_list(args):
    accounts = load_accounts()
    rows = [a for a in accounts if args.all or a["stage"] not in ("churned", "lost")]
    if args.stage:
        rows = [a for a in rows if a["stage"] == args.stage]
    if not rows:
        print("No accounts." if not accounts else "No accounts match.")
        return
    rows.sort(key=lambda a: (STAGES.index(a["stage"]), a["company"].lower()))
    print(f"{'ID':<28} {'STAGE':<12} {'LAST TOUCH':<11} NEXT ACTION")
    for a in rows:
        nxt = a.get("next_action") or {}
        nxt_s = f"{nxt.get('due', '')} {nxt.get('what', '')}".strip() or "-"
        print(f"{a['id']:<28} {a['stage']:<12} {a.get('last_touch', ''):<11} {nxt_s}")


def cmd_get(args):
    a = find_account(load_accounts(), args.account)
    print(json.dumps(a, indent=2, ensure_ascii=False))
    pays = [p for p in load_payments() if p["account_id"] == a["id"]]
    if pays:
        print("\nPayments:")
        for p in pays:
            print(f"  {p['date']}  {p['type']:<10} {fmt(p['amount'], p['currency'])}  {p.get('period', '')}  {p.get('notes', '')}")


def cmd_add(args):
    accounts = load_accounts()
    slug = slugify(args.id or args.company)
    if any(a["id"] == slug for a in accounts):
        sys.exit(f"Account '{slug}' already exists.")
    if args.stage not in STAGES:
        sys.exit(f"Stage must be one of: {', '.join(STAGES)}")
    check_date(args.due, "--due")
    a = {
        "id": slug,
        "company": args.company,
        "contact": parse_contact(args.contact) if args.contact else {"name": "", "email": "", "role": ""},
        "stage": args.stage,
        "source": args.source or "",
        "created": today(),
        "last_touch": today(),
        "next_action": {"what": args.next or "", "due": args.due or ""},
        "notes": f"{today()}: {args.notes}" if args.notes else "",
        "contract": None,
    }
    a["folder"] = folder_for(a)
    accounts.append(a)
    save_accounts(accounts)
    created = maybe_create_folder(a)
    print(f"Added {slug} ({a['stage']}). Folder: {a['folder']}{' (created from template)' if created else ''}")


def maybe_create_folder(account):
    """Create the engagement folder from the matching _template if it is missing."""
    target = ROOT / account["folder"]
    if target.exists():
        return False
    template = target.parent / "_template"
    if not template.is_dir():
        target.mkdir(parents=True)
        return True
    shutil.copytree(template, target)
    for name in ("CLAUDE.md", "HANDOFF.md"):
        p = target / name
        if p.exists():
            text = p.read_text(encoding="utf-8")
            text = text.replace("{{COMPANY}}", account["company"]).replace("{{SLUG}}", account["id"])
            text = text.replace("{{DATE}}", today())
            p.write_text(text, encoding="utf-8")
    return True


def cmd_move(args):
    accounts = load_accounts()
    a = find_account(accounts, args.account)
    if args.stage not in STAGES:
        sys.exit(f"Stage must be one of: {', '.join(STAGES)}")
    old_stage, old_folder = a["stage"], ROOT / a.get("folder", folder_for(a))
    a["stage"] = args.stage
    a["last_touch"] = today()
    if args.note:
        a["notes"] = f"{today()}: {args.note}\n{a.get('notes', '')}".strip()
    a["folder"] = folder_for(a)
    new_folder = ROOT / a["folder"]
    save_accounts(accounts)   # record the stage first so an interrupted move is visible, not silent
    moved = False
    if old_folder != new_folder and old_folder.is_dir() and not new_folder.exists():
        new_folder.parent.mkdir(exist_ok=True)
        shutil.move(str(old_folder), str(new_folder))
        moved = True
    elif old_folder != new_folder and old_folder.is_dir() and new_folder.exists():
        print(f"Warning: {a['folder']} already exists, so {old_folder.relative_to(ROOT)} was left in place. Merge them by hand.")
    print(f"{a['id']}: {old_stage} -> {a['stage']}")
    if moved:
        print(f"Moved folder {old_folder.relative_to(ROOT)} -> {a['folder']}")
    if args.stage == "client" and not a.get("contract"):
        print("Reminder: set the contract so the P&L can expect revenue:\n"
              f"  crm.py contract {a['id']} --json '{{\"setup_fee\": 0, \"monthly\": 0, \"currency\": \"USD\", \"start_date\": \"{today()}\", \"billing_day\": 1, \"status\": \"active\"}}'")


def cmd_next(args):
    accounts = load_accounts()
    a = find_account(accounts, args.account)
    check_date(args.due, "--due")
    a["next_action"] = {"what": args.what, "due": args.due or ""}
    a["last_touch"] = today()
    save_accounts(accounts)
    print(f"{a['id']}: next action -> {args.what or '(cleared)'} {args.due or ''}".rstrip())


def cmd_note(args):
    accounts = load_accounts()
    a = find_account(accounts, args.account)
    a["notes"] = f"{today()}: {args.text}\n{a.get('notes', '')}".strip()
    a["last_touch"] = today()
    save_accounts(accounts)
    print(f"{a['id']}: note added")


def cmd_contract(args):
    accounts = load_accounts()
    a = find_account(accounts, args.account)
    try:
        c = json.loads(args.json)
    except json.JSONDecodeError as e:
        sys.exit(f"Bad JSON: {e}")
    base = {"setup_fee": 0, "monthly": 0, "currency": "USD", "start_date": today(),
            "billing_day": 1, "status": "active", "paused_from": None, "ended_on": None}
    base.update(a.get("contract") or {})
    base.update(c)
    for k in ("start_date", "paused_from", "ended_on"):
        check_date(base.get(k), f"contract.{k}")
    money(base.get("setup_fee")); money(base.get("monthly"))
    a["contract"] = base
    a["last_touch"] = today()
    save_accounts(accounts)
    print(f"{a['id']}: contract set to {json.dumps(base)}")


def cmd_pay(args):
    accounts = load_accounts()
    a = find_account(accounts, args.account)
    if args.type not in PAYMENT_TYPES:
        sys.exit(f"Type must be one of: {', '.join(PAYMENT_TYPES)}")
    d = check_date(args.date, "--date") or today()
    ref = args.reference or f"manual-{a['id']}-{d}-{args.type}"
    if any(p["reference"] == ref for p in load_payments()):
        sys.exit(f"A payment with reference '{ref}' is already in the ledger, so nothing was written. "
                 f"If this is a second, separate payment, pass a unique --reference.")
    currency = args.currency or (a.get("contract") or {}).get("currency") or "USD"
    row = {"date": d, "account_id": a["id"], "type": args.type, "amount": f"{money(args.amount):.2f}",
           "currency": currency, "reference": ref,
           "period": args.period or (d[:7] if args.type == "monthly" else ""), "notes": args.notes or ""}
    if args.dry_run:
        print("DRY RUN, would append:", row)
        return
    append_payment(row)
    a["last_touch"] = d if d > a.get("last_touch", "") else a["last_touch"]
    save_accounts(accounts)
    print(f"Logged {fmt(row['amount'], currency)} {args.type} from {a['id']} on {d} (ref {ref})")


def expected_months(contract, upto: date):
    """Months (YYYY-MM) a monthly fee is expected, from start_date to `upto`."""
    if not contract or money(contract.get("monthly")) <= 0:
        return []
    start = parse_date(contract.get("start_date"), "contract.start_date")
    stop = upto
    if contract.get("status") == "ended" and contract.get("ended_on"):
        stop = min(stop, parse_date(contract["ended_on"], "contract.ended_on"))
    if contract.get("status") == "paused" and contract.get("paused_from"):
        stop = min(stop, parse_date(contract["paused_from"], "contract.paused_from"))
    months, y, m = [], start.year, start.month
    while (y, m) <= (stop.year, stop.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return months


def cmd_status(args):
    accounts = load_accounts()
    payments = load_payments()
    curs = currencies_in_use(accounts, payments)
    cur = curs[0]
    t = date.today()
    this_month = t.strftime("%Y-%m")
    print(f"Business status as of {t.isoformat()}\n")
    if len(curs) > 1:
        print(f"Warning: several currencies in use ({', '.join(curs)}). Totals below add them as-is and are labeled {cur}.\n")

    counts = {s: 0 for s in STAGES}
    for a in accounts:
        counts[a["stage"]] += 1
    print("Pipeline:", "  ".join(f"{s}={counts[s]}" for s in STAGES if counts[s]) or "empty")

    clients = [a for a in accounts if a["stage"] == "client"]
    mrr = sum(money(a["contract"].get("monthly")) for a in clients
              if a.get("contract") and a["contract"].get("status", "active") == "active")
    collected_month = sum(money(p["amount"]) for p in payments if p["date"].startswith(this_month))
    collected_all = sum(money(p["amount"]) for p in payments)
    print(f"Active clients: {len(clients)}   MRR: {fmt(mrr, cur)}")
    print(f"Collected this month: {fmt(collected_month, cur)}   All time: {fmt(collected_all, cur)}")

    print("\nOverdue or due-today next actions:")
    due = [a for a in accounts if a["stage"] not in ("churned", "lost")
           and (a.get("next_action") or {}).get("due") and a["next_action"]["due"] <= t.isoformat()]
    for a in sorted(due, key=lambda a: a["next_action"]["due"]):
        print(f"  {a['next_action']['due']}  {a['id']:<26} {a['next_action']['what']}")
    if not due:
        print("  none")

    print("\nActive leads with no next action:")
    idle = [a for a in accounts if a["stage"] in LEAD_STAGES and not (a.get("next_action") or {}).get("what")]
    for a in idle:
        print(f"  {a['id']:<26} last touch {a.get('last_touch', '?')}")
    if not idle:
        print("  none")

    print("\nMonthly fees not yet in the ledger:")
    missing = []
    for a in clients:
        paid = {p["period"] for p in payments if p["account_id"] == a["id"] and p["type"] == "monthly"}
        for month in expected_months(a.get("contract"), t):
            if month not in paid:
                missing.append((month, a["id"], a["contract"]["monthly"], a["contract"].get("currency", cur)))
    for month, aid, amt, c in sorted(missing):
        print(f"  {month}  {aid:<26} {fmt(amt, c)}")
    if not missing:
        print("  none")

    print("\nClients with no contract set:")
    nc = [a["id"] for a in clients if not a.get("contract")]
    print("  " + (", ".join(nc) if nc else "none"))


# ---------- cli ----------

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("list", help="list accounts"); s.add_argument("--stage", choices=STAGES)
    s.add_argument("--all", action="store_true", help="include churned and lost"); s.set_defaults(fn=cmd_list)

    s = sub.add_parser("get", help="show one account and its payments"); s.add_argument("account"); s.set_defaults(fn=cmd_get)

    s = sub.add_parser("add", help="add an account (creates its folder from _template)")
    s.add_argument("--company", required=True); s.add_argument("--id", help="slug, defaults to the company name")
    s.add_argument("--stage", default="new", choices=STAGES); s.add_argument("--source", help="referral, inbound, cold-email, ...")
    s.add_argument("--contact", help='"Name <email> (Role)"'); s.add_argument("--next", help="next action")
    s.add_argument("--due", help="YYYY-MM-DD"); s.add_argument("--notes"); s.set_defaults(fn=cmd_add)

    s = sub.add_parser("move", help="change stage (moves leads/<id> to clients/<id> on 'client')")
    s.add_argument("account"); s.add_argument("stage", choices=STAGES); s.add_argument("--note"); s.set_defaults(fn=cmd_move)

    s = sub.add_parser("next", help="set the next action"); s.add_argument("account")
    s.add_argument("--what", required=True, help='use "" to clear'); s.add_argument("--due"); s.set_defaults(fn=cmd_next)

    s = sub.add_parser("note", help="prepend a dated note"); s.add_argument("account"); s.add_argument("text"); s.set_defaults(fn=cmd_note)

    s = sub.add_parser("contract", help="set contract fields (merged into the existing contract)")
    s.add_argument("account"); s.add_argument("--json", required=True); s.set_defaults(fn=cmd_contract)

    s = sub.add_parser("pay", help="append one payment to the ledger")
    s.add_argument("--account", required=True); s.add_argument("--type", required=True, choices=PAYMENT_TYPES)
    s.add_argument("--amount", required=True); s.add_argument("--date", help="YYYY-MM-DD, default today")
    s.add_argument("--period", help="YYYY-MM the monthly fee covers"); s.add_argument("--reference", help="external txn id (dedup key)")
    s.add_argument("--currency"); s.add_argument("--notes"); s.add_argument("--dry-run", action="store_true"); s.set_defaults(fn=cmd_pay)

    s = sub.add_parser("status", help="overview: pipeline, MRR, overdue actions, unpaid months"); s.set_defaults(fn=cmd_status)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
