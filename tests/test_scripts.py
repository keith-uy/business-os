"""End-to-end checks for crm.py and pnl.py against a throwaway copy of the workspace.

    python3 -m unittest discover -s tests -v
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="business-os-"))
        for name in ("clients", "leads", "crm", "pnl", ".claude", "active", "assets"):
            src = REPO / name
            shutil.copytree(src, self.tmp / name, symlinks=True,
                            ignore=shutil.ignore_patterns("__pycache__", ".backups"))
        self.crm = self.tmp / ".claude/skills/crm/scripts/crm.py"
        self.pnl = self.tmp / ".claude/skills/pnl/scripts/pnl.py"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, script, *args, ok=True):
        r = subprocess.run([sys.executable, str(script), *args], cwd=self.tmp,
                           capture_output=True, text=True)
        if ok:
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        else:
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def accounts(self):
        return json.loads((self.tmp / "crm/accounts.json").read_text())

    def payments(self):
        with (self.tmp / "crm/payments.csv").open(newline="") as f:
            return list(csv.DictReader(f))

    # ---- crm ----

    def test_lead_to_client_flow(self):
        out = self.run_script(self.crm, "add", "--company", "Acme Marketing", "--source", "referral",
                              "--contact", "Jane Doe <jane@acme.test> (Owner)",
                              "--next", "Send proposal", "--due", "2030-01-01")
        self.assertIn("Added acme-marketing", out)
        lead_dir = self.tmp / "leads/acme-marketing"
        self.assertTrue((lead_dir / "CLAUDE.md").exists())
        text = (lead_dir / "CLAUDE.md").read_text()
        self.assertIn("# Acme Marketing", text)
        self.assertIn("`acme-marketing`", text)
        self.assertNotIn("{{", text)
        a = self.accounts()[0]
        self.assertEqual(a["contact"], {"name": "Jane Doe", "email": "jane@acme.test", "role": "Owner"})
        self.assertEqual(a["folder"], "leads/acme-marketing")

        out = self.run_script(self.crm, "move", "acme", "client", "--note", "Deposit paid")
        self.assertIn("new -> client", out)
        self.assertIn("Moved folder", out)
        self.assertFalse(lead_dir.exists())
        self.assertTrue((self.tmp / "clients/acme-marketing/CLAUDE.md").exists())
        self.assertEqual(self.accounts()[0]["folder"], "clients/acme-marketing")
        self.assertTrue(self.accounts()[0]["notes"].startswith(date.today().isoformat()))

        self.run_script(self.crm, "contract", "acme", "--json",
                        '{"setup_fee": 1500, "monthly": 400, "start_date": "2020-01-01"}')
        c = self.accounts()[0]["contract"]
        self.assertEqual(c["monthly"], 400)
        self.assertEqual(c["status"], "active")
        self.assertEqual(c["currency"], "USD")

        self.run_script(self.crm, "pay", "--account", "acme", "--type", "setup_fee", "--amount", "1500",
                        "--date", "2020-01-05")
        self.run_script(self.crm, "pay", "--account", "acme", "--type", "monthly", "--amount", "400",
                        "--date", "2020-01-05", "--reference", "txn_1")
        # duplicate reference is refused
        self.run_script(self.crm, "pay", "--account", "acme", "--type", "monthly", "--amount", "400",
                        "--date", "2020-02-05", "--reference", "txn_1", ok=False)
        rows = self.payments()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["period"], "2020-01")

        out = self.run_script(self.crm, "status")
        self.assertIn("MRR: USD 400.00", out)
        self.assertIn("2020-02  acme-marketing", out)   # expected but unpaid month
        self.assertNotIn("2020-01  acme-marketing", out)

        # ending the contract stops expecting fees
        self.run_script(self.crm, "contract", "acme", "--json", '{"status": "ended", "ended_on": "2020-01-31"}')
        out = self.run_script(self.crm, "status")
        self.assertIn("MRR: USD 0.00", out)
        self.assertNotIn("2020-02  acme-marketing", out)

        backups = list((self.tmp / "crm/.backups").glob("accounts-*.json"))
        self.assertGreater(len(backups), 0)

    def test_status_flags_overdue_and_idle(self):
        self.run_script(self.crm, "add", "--company", "Late Co", "--next", "Call back", "--due", "2000-01-01")
        self.run_script(self.crm, "add", "--company", "Idle Co")
        out = self.run_script(self.crm, "status")
        self.assertIn("2000-01-01  late-co", out)
        self.assertIn("idle-co", out.split("no next action")[1])

    def test_duplicate_and_unknown_account(self):
        self.run_script(self.crm, "add", "--company", "Acme")
        self.run_script(self.crm, "add", "--company", "Acme", ok=False)
        self.run_script(self.crm, "get", "nobody", ok=False)

    def test_next_clear_and_get(self):
        self.run_script(self.crm, "add", "--company", "Acme", "--next", "x", "--due", "2030-01-01")
        self.run_script(self.crm, "next", "acme", "--what", "")
        self.assertEqual(self.accounts()[0]["next_action"]["what"], "")
        out = self.run_script(self.crm, "get", "acme")
        self.assertIn('"id": "acme"', out)

    # ---- pnl ----

    def test_pnl_report(self):
        self.run_script(self.crm, "add", "--company", "Acme", "--stage", "client")
        self.run_script(self.crm, "pay", "--account", "acme", "--type", "project", "--amount", "1000",
                        "--date", "2020-03-10")
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"hosting","name":"Hosting","category":"infrastructure","started":"2019-01-01",'
                        '"cost":{"amount":20,"currency":"USD","cycle":"monthly"}}')
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"domain","name":"Domain","started":"2019-01-01",'
                        '"cost":{"amount":120,"currency":"USD","cycle":"yearly"}}')
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"laptop","name":"Laptop","date":"2020-03-02",'
                        '"cost":{"amount":500,"currency":"USD","cycle":"one-time"}}')
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"future","name":"Started later","started":"2021-01-01",'
                        '"cost":{"amount":999,"currency":"USD","cycle":"monthly"}}')
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"old","name":"Cancelled before","status":"cancelled","cancelled_on":"2020-01-15",'
                        '"started":"2019-01-01","cost":{"amount":999,"currency":"USD","cycle":"monthly"}}')
        out = self.run_script(self.pnl, "report", "--month", "2020-03", "--html")
        self.assertIn("Income        USD 1,000.00", out)
        self.assertIn("Expenses      USD 530.00", out)   # 20 + 10 + 500
        self.assertIn("Net           USD 470.00", out)
        self.assertNotIn("future", out)
        self.assertNotIn("old", out.split("Expenses")[1])
        self.assertTrue((self.tmp / "pnl/reports/2020-03.html").exists())

        out = self.run_script(self.pnl, "report", "--month", "2020-04")
        self.assertIn("Expenses      USD 30.00", out)    # one-time no longer counted

        out = self.run_script(self.pnl, "summary")
        self.assertIn("Fixed monthly burn:     USD 1,029.00", out)   # 20 + 10 + 999 (live today), cancelled one excluded

        # idempotent update
        self.run_script(self.pnl, "add", "--json", '{"id":"hosting","name":"Hosting","cost":{"amount":25,"cycle":"monthly"}}')
        items = json.loads((self.tmp / "pnl/expenses.json").read_text())
        self.assertEqual(len(items), 5)
        self.assertEqual([e for e in items if e["id"] == "hosting"][0]["cost"]["amount"], 25)

        out = self.run_script(self.pnl, "report", "--year", "2020")
        self.assertIn("2020-03", out)
        self.assertIn("TOTAL", out)

    def test_paused_expense_keeps_history(self):
        self.run_script(self.pnl, "add", "--json",
                        '{"id":"tool","name":"Tool","started":"2020-01-01","status":"paused","paused_from":"2020-06-01",'
                        '"cost":{"amount":50,"currency":"USD","cycle":"monthly"}}')
        self.assertIn("Expenses      USD 50.00", self.run_script(self.pnl, "report", "--month", "2020-03"))
        self.assertIn("Expenses      USD 0.00", self.run_script(self.pnl, "report", "--month", "2020-06"))
        # a pause with a resume date, while still active
        self.run_script(self.pnl, "add", "--json", '{"id":"tool","status":"active","resumed_on":"2020-09-01"}')
        self.assertIn("Expenses      USD 0.00", self.run_script(self.pnl, "report", "--month", "2020-07"))
        self.assertIn("Expenses      USD 50.00", self.run_script(self.pnl, "report", "--month", "2020-09"))

    def test_html_report_escapes(self):
        self.run_script(self.crm, "add", "--company", "A<b>&c", "--stage", "client")
        self.run_script(self.crm, "pay", "--account", "a-b-c", "--type", "project", "--amount", "10",
                        "--date", "2020-03-10", "--notes", "<script>")
        self.run_script(self.pnl, "report", "--month", "2020-03", "--html")
        page = (self.tmp / "pnl/reports/2020-03.html").read_text()
        self.assertNotIn("<script>", page)

    def test_ambiguous_and_bad_dates(self):
        self.run_script(self.crm, "add", "--company", "Acme One")
        self.run_script(self.crm, "add", "--company", "Acme Two")
        out = self.run_script(self.crm, "get", "acme", ok=False)
        self.assertIn("matches several", out)
        self.run_script(self.crm, "get", "acme-one")
        self.run_script(self.crm, "next", "acme-one", "--what", "x", "--due", "09/22/2026", ok=False)
        self.run_script(self.crm, "pay", "--account", "acme-one", "--type", "other", "--amount", "abc", ok=False)
        self.run_script(self.crm, "contract", "acme-one", "--json", '{"start_date": "2020/01/01"}', ok=False)
        # corrupted JSON gives a readable message, not a traceback
        (self.tmp / "crm/accounts.json").write_text("{not json")
        out = self.run_script(self.crm, "status", ok=False)
        self.assertIn("not valid JSON", out)
        self.assertNotIn("Traceback", out)

    def test_pnl_rejects_bad_input(self):
        self.run_script(self.pnl, "add", "--json", '{"id":"x"}', ok=False)
        self.run_script(self.pnl, "add", "--json", '{"id":"x","name":"x","cost":{"amount":1,"cycle":"weekly"}}', ok=False)
        self.run_script(self.pnl, "add", "--json", 'not json', ok=False)


if __name__ == "__main__":
    unittest.main()
