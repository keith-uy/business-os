#!/usr/bin/env python3
"""Profit and loss for a Business OS workspace. Python 3.8+, stdlib only.

Income comes from crm/payments.csv (what clients actually paid).
Expenses come from pnl/expenses.json (what the business commits to pay).
Net = income minus expenses, per month.

    python3 .claude/skills/pnl/scripts/pnl.py summary
    python3 .claude/skills/pnl/scripts/pnl.py report --month 2026-09
    python3 .claude/skills/pnl/scripts/pnl.py report --year 2026 --html
"""
import argparse
import csv
import html
import json
import os
import shutil
import sys
from decimal import InvalidOperation
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

CYCLES = ["monthly", "yearly", "one-time", "usage", "free"]
STATUSES = ["active", "trial", "paused", "cancelled"]


def find_root(start: Path) -> Path:
    p = start.resolve()
    for candidate in [p, *p.parents]:
        # .claude/skills/ also holds crm/ and pnl/ folders; skip it by requiring
        # that crm/ is a data folder, not a skill folder.
        if ((candidate / "crm").is_dir() and (candidate / "pnl").is_dir()
                and not (candidate / "crm" / "SKILL.md").exists()):
            return candidate
    sys.exit("Could not find the workspace root (a folder containing crm/ and pnl/).")


ROOT = find_root(Path(__file__).parent)
EXPENSES = ROOT / "pnl" / "expenses.json"
PAYMENTS = ROOT / "crm" / "payments.csv"
BACKUPS = ROOT / "pnl" / ".backups"
REPORTS = ROOT / "pnl" / "reports"


def money(x):
    try:
        return Decimal(str(x or 0))
    except InvalidOperation:
        sys.exit(f"Amount must be a number, got '{x}'.")


def fmt(x, cur):
    return f"{cur} {money(x):,.2f}"


def load_expenses():
    if not EXPENSES.exists():
        return []
    try:
        with EXPENSES.open(encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        sys.exit(f"pnl/expenses.json is not valid JSON ({e}). Restore the newest snapshot from "
                 f"pnl/.backups/ or from git history, then retry.")
    if not isinstance(data, list):
        sys.exit("pnl/expenses.json must be a JSON array.")
    for e in data:
        if not isinstance(e.get("cost"), dict) or "id" not in e:
            sys.exit(f"Expense entry {e.get('id') or e!r} needs an 'id' and a 'cost' object.")
    return data


def save_expenses(items):
    if EXPENSES.exists() and EXPENSES.stat().st_size:
        BACKUPS.mkdir(exist_ok=True)
        shutil.copy2(EXPENSES, BACKUPS / f"expenses-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.json")
    tmp = EXPENSES.with_name(EXPENSES.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, EXPENSES)


def load_payments():
    if not PAYMENTS.exists():
        return []
    with PAYMENTS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def currencies_in_use(expenses, payments):
    found = {e["cost"].get("currency") for e in expenses if e["cost"].get("currency")}
    found |= {p.get("currency") for p in payments if p.get("currency")}
    return sorted(found) or ["USD"]


def currency_of(expenses, payments):
    curs = currencies_in_use(expenses, payments)
    if len(curs) > 1:
        print(f"Warning: several currencies in use ({', '.join(curs)}). Totals add them as-is and are labeled {curs[0]}.\n")
    return curs[0]


# ---------- expense math ----------

def active_in_month(e, month):
    """Is this expense in force during YYYY-MM?

    Dated fields decide: started, paused_from / resumed_on, cancelled_on. A status
    of paused or cancelled with no date is treated as effective from the start.
    """
    started = (e.get("started") or "")[:7]
    if started and started > month:
        return False
    status = e.get("status", "active")
    if status == "cancelled":
        ended = (e.get("cancelled_on") or "")[:7]
        return bool(ended) and month < ended
    if status == "paused":
        paused = (e.get("paused_from") or "")[:7]
        return bool(paused) and month < paused
    resumed = (e.get("resumed_on") or "")[:7]
    paused = (e.get("paused_from") or "")[:7]
    if paused and month >= paused and (not resumed or month < resumed):
        return False
    return True


def monthly_cost(e, month=None):
    """Committed cost of one expense for a given month (or a generic month if None)."""
    cost = e.get("cost", {})
    amt, cycle = money(cost.get("amount")), cost.get("cycle", "monthly")
    if month and not active_in_month(e, month):
        return Decimal(0)
    if not month and e.get("status") not in ("active", "trial"):
        return Decimal(0)
    if cycle == "monthly":
        return amt
    if cycle == "yearly":
        # Rounded to cents per month; twelve months may differ from the yearly charge by a few cents.
        return (amt / 12).quantize(Decimal("0.01"))
    if cycle == "usage":
        return money(cost.get("est_monthly"))
    if cycle == "one-time":
        return amt if month and (e.get("date") or e.get("started") or "")[:7] == month else Decimal(0)
    return Decimal(0)


# ---------- commands ----------

def cmd_add(args):
    items = load_expenses()
    try:
        patch = json.loads(args.json)
    except json.JSONDecodeError as e:
        sys.exit(f"Bad JSON: {e}")
    if "id" not in patch:
        sys.exit("Entry needs an 'id'.")
    existing = next((e for e in items if e["id"] == patch["id"]), None)
    entry = dict(existing) if existing else {}
    if "cost" in patch:
        entry["cost"] = dict(entry.get("cost") or {})
        entry["cost"].update(patch.pop("cost"))
    entry.update(patch)
    for k in ("name", "cost"):
        if k not in entry:
            sys.exit(f"Entry needs '{k}'. Minimal: {{\"id\":\"tool\",\"name\":\"Tool\",\"cost\":{{\"amount\":10,\"currency\":\"USD\",\"cycle\":\"monthly\"}}}}")
    entry.setdefault("category", "other")
    entry.setdefault("status", "active")
    entry["cost"].setdefault("currency", "USD")
    entry["cost"].setdefault("cycle", "monthly")
    if entry["cost"]["cycle"] not in CYCLES:
        sys.exit(f"cost.cycle must be one of: {', '.join(CYCLES)}")
    if entry["status"] not in STATUSES:
        sys.exit(f"status must be one of: {', '.join(STATUSES)}")
    money(entry["cost"].get("amount"))
    for k in ("started", "renewal", "trial_ends", "cancelled_on", "paused_from", "resumed_on", "date"):
        v = entry.get(k)
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                sys.exit(f"{k} must be YYYY-MM-DD, got '{v}'.")
    if entry["cost"]["cycle"] == "one-time":
        entry.setdefault("date", date.today().isoformat())
    if existing:
        items[items.index(existing)] = entry
    else:
        items.append(entry)
    save_expenses(items)
    print(f"{'Updated' if existing else 'Added'} {entry['id']}: {fmt(entry['cost']['amount'], entry['cost']['currency'])} {entry['cost']['cycle']}")


def cmd_list(args):
    items = load_expenses()
    if not items:
        print("No expenses yet. Add one with: pnl.py add --json '{...}'")
        return
    print(f"{'ID':<22} {'CATEGORY':<14} {'STATUS':<10} {'CYCLE':<9} {'AMOUNT':>12}  {'PER MONTH':>10}")
    for e in sorted(items, key=lambda e: (e.get("category", ""), e["name"].lower())):
        c = e["cost"]
        print(f"{e['id']:<22} {e.get('category', ''):<14} {e.get('status', ''):<10} {c.get('cycle', ''):<9} "
              f"{money(c.get('amount')):>12,.2f}  {monthly_cost(e):>10,.2f}")


def cmd_summary(args):
    items = load_expenses()
    cur = currency_of(items, load_payments())
    now = date.today().strftime("%Y-%m")
    fixed = sum(monthly_cost(e, now) for e in items if e["cost"].get("cycle") in ("monthly", "yearly"))
    variable = sum(monthly_cost(e, now) for e in items if e["cost"].get("cycle") == "usage")
    print(f"Fixed monthly burn:     {fmt(fixed, cur)}   ({fmt(fixed * 12, cur)} per year)")
    print(f"Variable estimate:      {fmt(variable, cur)} per month")
    by_cat = {}
    for e in items:
        by_cat[e.get("category", "other")] = by_cat.get(e.get("category", "other"), Decimal(0)) + monthly_cost(e, now)
    if by_cat:
        print("\nBy category (per month):")
        for cat, amt in sorted(by_cat.items(), key=lambda kv: -kv[1]):
            if amt:
                print(f"  {cat:<16} {fmt(amt, cur)}")
    soon = []
    horizon = date.today().toordinal() + 30
    for e in items:
        for key in ("renewal", "trial_ends"):
            d = e.get(key)
            if d and date.today().toordinal() <= datetime.strptime(d, "%Y-%m-%d").date().toordinal() <= horizon:
                soon.append((d, e["id"], key))
    print("\nRenewals and trial ends in the next 30 days:")
    for d, eid, key in sorted(soon):
        print(f"  {d}  {eid}  ({key.replace('_', ' ')})")
    if not soon:
        print("  none")


def month_lines(month, expenses, payments):
    income_rows = [p for p in payments if p["date"][:7] == month]
    income = sum(money(p["amount"]) for p in income_rows)
    expense_rows = [(e, monthly_cost(e, month)) for e in expenses]
    expense_rows = [(e, c) for e, c in expense_rows if c]
    expense = sum(c for _, c in expense_rows)
    return income, income_rows, expense, expense_rows


def cmd_report(args):
    expenses, payments = load_expenses(), load_payments()
    cur = currency_of(expenses, payments)
    if args.year:
        months = [f"{args.year}-{m:02d}" for m in range(1, 13)]
        rows = []
        print(f"P&L {args.year}\n{'MONTH':<9} {'INCOME':>12} {'EXPENSES':>12} {'NET':>12}")
        tot_i = tot_e = Decimal(0)
        for m in months:
            if m > date.today().strftime("%Y-%m"):
                break
            i, _, e, _ = month_lines(m, expenses, payments)
            rows.append((m, i, e, i - e)); tot_i += i; tot_e += e
            print(f"{m:<9} {i:>12,.2f} {e:>12,.2f} {i - e:>12,.2f}")
        print(f"{'TOTAL':<9} {tot_i:>12,.2f} {tot_e:>12,.2f} {tot_i - tot_e:>12,.2f}")
        if args.html:
            path = write_html(f"P&L {args.year}", cur, [("Month", "Income", "Expenses", "Net")] +
                              [(m, f"{i:,.2f}", f"{e:,.2f}", f"{n:,.2f}") for m, i, e, n in rows] +
                              [("Total", f"{tot_i:,.2f}", f"{tot_e:,.2f}", f"{tot_i - tot_e:,.2f}")],
                              f"{args.year}.html")
            print(f"\nWrote {path.relative_to(ROOT)}")
        return

    month = args.month or date.today().strftime("%Y-%m")
    income, income_rows, expense, expense_rows = month_lines(month, expenses, payments)
    print(f"P&L {month}\n")
    print(f"Income        {fmt(income, cur)}")
    for p in sorted(income_rows, key=lambda p: p["date"]):
        print(f"  {p['date']}  {p['account_id']:<24} {p['type']:<10} {money(p['amount']):>10,.2f}")
    print(f"\nExpenses      {fmt(expense, cur)}")
    for e, c in sorted(expense_rows, key=lambda ec: -ec[1]):
        print(f"  {e['id']:<36} {e['cost'].get('cycle', ''):<9} {c:>10,.2f}")
    print(f"\nNet           {fmt(income - expense, cur)}")
    if args.html:
        table = [("Line", "Detail", "Amount")]
        table += [("Income", f"{p['date']} {p['account_id']} ({p['type']})", f"{money(p['amount']):,.2f}") for p in income_rows]
        table += [("Expense", f"{e['name']} ({e['cost'].get('cycle', '')})", f"-{c:,.2f}") for e, c in expense_rows]
        table += [("Net", "", f"{income - expense:,.2f}")]
        path = write_html(f"P&L {month}", cur, table, f"{month}.html")
        print(f"\nWrote {path.relative_to(ROOT)}")


def write_html(title, cur, rows, filename):
    REPORTS.mkdir(exist_ok=True)
    head, *body = rows
    esc = lambda c: html.escape(str(c))
    title, cur = esc(title), esc(cur)
    trs = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>" for r in body)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px 10px;border-bottom:1px solid #e5e5e5;text-align:left}}
td:last-child,th:last-child{{text-align:right;font-variant-numeric:tabular-nums}}tr:last-child td{{font-weight:600}}
p{{color:#666}}</style></head><body><h1>{title}</h1><p>Amounts in {cur}. Generated {date.today().isoformat()}.</p>
<table><thead><tr>{"".join(f"<th>{esc(c)}</th>" for c in head)}</tr></thead><tbody>{trs}</tbody></table></body></html>
"""
    path = REPORTS / filename
    path.write_text(page, encoding="utf-8")
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add", help="add or update an expense (idempotent on id)"); s.add_argument("--json", required=True); s.set_defaults(fn=cmd_add)
    s = sub.add_parser("list", help="every tool and subscription"); s.set_defaults(fn=cmd_list)
    s = sub.add_parser("summary", help="monthly burn, by category, upcoming renewals"); s.set_defaults(fn=cmd_summary)
    s = sub.add_parser("report", help="income minus expenses for a month or a year")
    s.add_argument("--month", help="YYYY-MM (default: current month)"); s.add_argument("--year", type=int)
    s.add_argument("--html", action="store_true", help="also write pnl/reports/<period>.html"); s.set_defaults(fn=cmd_report)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
