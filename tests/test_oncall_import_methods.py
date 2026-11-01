import unittest
from datetime import date, time

from app.services.oncall_parser import parse_period_text, parse_pasted_text


class OnCallImportMethodTests(unittest.TestCase):
    def test_parse_period_text(self):
        result = parse_period_text(
            "Standby period: 31 Oct 2026 till 6 Nov 2026"
        )
        self.assertEqual(
            result,
            (date(2026, 10, 31), date(2026, 11, 6)),
        )

    def test_manual_paste_creates_daily_entries(self):
        result = parse_pasted_text(
            "Portal    Ali Rezaei    09123456789",
            group="Portal",
            from_date="2026-10-31",
            to_date="2026-11-01",
            shift_start="17:00",
            shift_end="07:00",
        )
        self.assertEqual(result["rows_count"], 2)
        self.assertEqual(result["entries"][0]["team"], "Portal")
        self.assertEqual(result["entries"][0]["person_name"], "Ali Rezaei")
        self.assertEqual(result["entries"][0]["phone"], "09123456789")
        self.assertEqual(result["entries"][0]["shift_start"], time(17, 0))
        self.assertEqual(result["entries"][0]["shift_end"], time(7, 0))

    def test_manual_paste_rejects_missing_period(self):
        with self.assertRaises(ValueError):
            parse_pasted_text("Portal    Ali    09123456789")


if __name__ == "__main__":
    unittest.main(verbosity=2)
