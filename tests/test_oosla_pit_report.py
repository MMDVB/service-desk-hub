import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from app.services.oosla_pit_report import build_oosla_rows, build_pit_rows


class OOSLAPITReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def create_oosla_file(self):
        path = self.root / "oosla.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append([
            "Ticket#", "Summary", "Group Assignee", "Status", "P",
            "Created", "Vendor", "Age of Ticket", "Reassignment Count",
            "SD Watcher", "Escalation Level", "Escalation Contact Point",
            "Incident ETR", "Time to resolution", "Reason of OOSLA",
            "Escalation Time (non-secure)", "OOSLA History (non-secure)",
            "OOSLA Last Update (non-secure)",
        ])
        ws.append(["INC001", "CT ticket", "CT Security Solutions", "In Progress",
                   "P2", None, "Vendor A", 5, 1, None, None, None, None,
                   None, None, None, None, None])
        ws.append(["INC002", "Other ticket", "ITS ESB Support", "Assigned to Team",
                   "P3", None, "Vendor B", 7, 0, None, None, None, None,
                   None, None, None, None, None])
        ws.append(["INC003", "Excluded group", "Architecture Group - ESB",
                   "Pending Customer Action", "P2", None, "Vendor C", 8, 2,
                   None, None, None, None, None, None, None, None, None])
        ws.append(["INC004", "Too young", "ITS ESB Support", "In Progress",
                   "P3", None, "Vendor D", 3, 0, None, None, None, None,
                   None, None, None, None, None])
        ws.append(["", "No ticket number", "NWG GI LAN Operation", "In Progress",
                   "P3", None, "Vendor E", 9, 0, None, None, None, None,
                   None, None, None, None, None])
        wb.save(path)
        wb.close()
        return path

    def create_pit_file(self):
        path = self.root / "pit.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.append([
            "Ticket#", "Summary", "PIT", "Group Assignee", "P", "Status",
            "Created", "Updated", "Age of Ticket", "Vendor", "Project Picker",
        ])
        ws.append(["INC010", "Age five", "PIT A", "Team A", "P2", "In Progress",
                   None, None, 5, "Vendor A", "Project A"])
        ws.append(["INC011", "Age twelve", "PIT B", "Team B", "P3", "Assigned to Team",
                   None, None, 12, "Vendor B", "Project B"])
        ws.append(["INC012", "Age text", "PIT C", "Team C", "P3", "In Progress",
                   None, None, "8 days", "Vendor C", "Project C"])
        ws.append(["", "Blank ticket", "PIT D", "Team D", "P3", "In Progress",
                   None, None, 99, "Vendor D", "Project D"])
        wb.save(path)
        wb.close()
        return path

    def test_oosla_main_keeps_all_eligible_tickets_and_splits_subsets(self):
        tables = build_oosla_rows(self.create_oosla_file())

        # The main ITS sheet should retain every eligible ticket.
        self.assertEqual(
            {row[0] for row in tables["its"]},
            {"INC001", "INC002", "INC003"},
        )
        self.assertEqual([row[0] for row in tables["nwg_ct"]], ["INC001"])
        self.assertEqual([row[0] for row in tables["other"]], ["INC002"])

        # Excluded groups stay in the main sheet but are not copied to Other.
        self.assertNotIn(
            "INC003",
            {row[0] for row in tables["other"] + tables["nwg_ct"]},
        )

    def test_oosla_excludes_age_below_four_and_blank_ticket(self):
        tables = build_oosla_rows(self.create_oosla_file())
        all_tickets = {
            row[0]
            for key in ("its", "nwg_ct", "other")
            for row in tables[key]
        }
        self.assertNotIn("INC004", all_tickets)
        self.assertEqual(len(all_tickets), 3)

    def test_pit_skips_blank_tickets_and_sorts_by_age_descending(self):
        rows = build_pit_rows(self.create_pit_file())

        self.assertEqual([row[0] for row in rows], ["INC011", "INC012", "INC010"])
        self.assertEqual([row[8] for row in rows], [12, "8 days", 5])


if __name__ == "__main__":
    unittest.main(verbosity=2)
