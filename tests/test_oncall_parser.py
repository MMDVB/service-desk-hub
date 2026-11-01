import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from openpyxl import Workbook

from app.services.oncall_parser import parse_excel


class OnCallParserTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_weekly_horizontal_tables_are_parsed_independently(self):
        path = self.root / "Weekly Standby.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Oct-Nov"

        ws["B2"] = "Portal's Standby"
        ws["F2"] = "VI's Standby"

        for col in ("B", "F"):
            ws[f"{col}3"] = "Date of Week"
            ws.cell(row=3, column=ws[f"{col}3"].column + 1, value="Day")
            ws.cell(row=3, column=ws[f"{col}3"].column + 2, value="17.00 - 07.00")

        for row in range(4, 6):
            duty_date = date(2026, 10, 31) if row == 4 else date(2026, 11, 1)
            ws.cell(row=row, column=2, value=duty_date)
            ws.cell(row=row, column=3, value="Sat")
            ws.cell(row=row, column=4, value="Portal Engineer")

            ws.cell(row=row, column=6, value=duty_date)
            ws.cell(row=row, column=7, value="Sat")
            ws.cell(
                row=row,
                column=8,
                value="VI Main (Main) + VI Backup (Backup)",
            )

        wb.save(path)
        wb.close()

        result = parse_excel(path)

        portal = [e for e in result["entries"] if e["team"] == "Portal"]
        vi = [e for e in result["entries"] if e["team"] == "VI"]

        self.assertEqual(len(portal), 2)
        self.assertEqual(len(vi), 4)
        self.assertTrue(all(e["duty_date"] == date(2026, 10, 31) or
                            e["duty_date"] == date(2026, 11, 1)
                            for e in result["entries"]))
        self.assertTrue(all(e["shift_start"] == time(17, 0) for e in result["entries"]))
        self.assertTrue(all(e["shift_end"] == time(7, 0) for e in result["entries"]))

    def test_offsite_roles_and_group_are_parsed(self):
        path = self.root / "Off-Site Roster Plan.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "CLM"

        ws.append(["Date", "Group", "Oncall", "Backup", "Escalation", "Manager"])
        ws.append([
            date(2026, 10, 1),
            "CLM",
            "Reihaneh Riazati",
            "Nima Mobininia",
            "Nima",
            "Pardis",
        ])

        wb.save(path)
        wb.close()

        result = parse_excel(path)

        self.assertEqual(result["rows_count"], 4)
        entries = result["entries"]
        self.assertEqual(
            {(e["person_name"], e["role"]) for e in entries},
            {
                ("Reihaneh Riazati", "Oncall"),
                ("Nima Mobininia", "Backup"),
                ("Nima", "Escalation"),
                ("Pardis", "Manager"),
            },
        )
        self.assertTrue(all(e["team"] == "CLM" for e in entries))
        self.assertTrue(all(e["duty_date"] == date(2026, 10, 1) for e in entries))


if __name__ == "__main__":
    unittest.main(verbosity=2)
