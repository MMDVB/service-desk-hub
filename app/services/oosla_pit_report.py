"""Python port of the OOSLA/PIT daily report macros."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook, Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


OOSLA_HEADERS = [
    "Number", "Ticket", "Summary", "Group Assignee", "Status", "P",
    "Created", "Vendor", "Age of Ticket", "Reassignment Count",
    "SD Watcher", "Escalation Level", "Escalation Contact Point",
    "Incident ETR", "Time to resolution", "Reason of OOSLA",
    "Escalation Time", "OOSLA History", "OOSLA Last Update",
]

PIT_HEADERS = [
    "Number", "Ticket", "Summary", "PIT", "Group Assignee", "P",
    "Status", "Created", "Updated", "Age of Ticket", "Vendor",
    "Project Picker",
]

BLUE = "00B0F0"
STATUS_COLORS = {
    "assigned to team": "B7B7B7",
    "pending cancellation": "00B050",
    "pending change implementation": "00B050",
    "pending chg impt": "00B050",
    "pending customer action": "FFFF00",
    "in progress": "F4B183",
}
EXCLUDED_GROUPS = {
    "tecnotree l3",
    "its tecnotree l3 support",
    "architecture group - esb",
}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _number(value: Any, default: float = 0) -> float:
    if value is None or _text(value) == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        text = _text(value)
        token = ""
        for char in text:
            if char.isdigit() or (char == "." and "." not in token):
                token += char
            elif token:
                break
            else:
                return default
        try:
            return float(token)
        except ValueError:
            return default


def _normalise_group(value: Any) -> str:
    text = _text(value).replace("\xa0", " ")
    for dash in ("\u2013", "\u2014", "\u2011", "\u2212"):
        text = text.replace(dash, "-")
    return " ".join(text.lower().split())


def _group_kind(group: Any) -> str:
    value = _text(group).upper()
    if value.startswith("CT") or value.startswith("NWG") or value == "IP OPERATIONS":
        return "nwg_ct"
    if _normalise_group(group) in EXCLUDED_GROUPS:
        return "excluded"
    return "other"


def _read_rows(path: str | Path, sheet_name: str | None = None) -> tuple[list[str], list[list[Any]]]:
    """Read an Excel sheet without modifying the source workbook."""
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet_name] if sheet_name else wb.active
        values = ws.iter_rows(values_only=True)
        raw_headers = next(values, ())
        headers = [_text(v) for v in raw_headers]
        rows = [list(row) for row in values if any(v is not None for v in row)]
        return headers, rows
    finally:
        wb.close()


def _format_sheet(ws, date_columns: tuple[int, ...] = ()) -> None:
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    thin = Side(style="thin", color="B7C9D6")
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
            if cell.row == 1:
                cell.fill = PatternFill("solid", fgColor=BLUE)
                cell.font = Font(name="Calibri", size=11, bold=True)
            else:
                cell.font = Font(name="Calibri", size=11)
    for col_idx in date_columns:
        for row_idx in range(2, ws.max_row + 1):
            ws.cell(row_idx, col_idx).number_format = "m/d/yyyy h:mm"
    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        max_len = max(
            (len(_text(ws.cell(r, col_idx).value)) for r in range(1, ws.max_row + 1)),
            default=10,
        )
        ws.column_dimensions[letter].width = min(max(max_len + 2, 10), 45)
    for row_idx in range(1, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 30


def _write_table(ws, headers: list[str], rows: list[list[Any]]) -> None:
    ws.append(headers)
    for index, row in enumerate(rows, start=1):
        ws.append([index, *row])
    _format_sheet(ws)


def build_oosla_rows(path: str | Path, sheet_name: str | None = None) -> dict[str, list[list[Any]]]:
    """Transform a raw OOSLA export into the three macro-compatible report tables."""
    headers, source_rows = _read_rows(path, sheet_name)
    header_map = {header.strip().lower(): idx for idx, header in enumerate(headers) if header}
    if "ticket#" not in header_map:
        raise ValueError("OOSLA file is missing the required 'Ticket#' column.")

    def get(row: list[Any], name: str) -> Any:
        idx = header_map.get(name.lower())
        return row[idx] if idx is not None and idx < len(row) else None

    result = {"its": [], "nwg_ct": [], "other": []}
    for row in source_rows:
        ticket = get(row, "Ticket#")
        if ticket is None or _text(ticket) == "":
            continue
        age = _number(get(row, "Age of Ticket"), 0)
        if age < 4:
            continue
        group = get(row, "Group Assignee")
        etr = get(row, "Incident ETR")
        output = [
            ticket,
            get(row, "Summary"),
            group,
            get(row, "Status"),
            get(row, "P"),
            get(row, "Created"),
            get(row, "Vendor"),
            age,
            _number(get(row, "Reassignment Count"), 0),
            get(row, "SD Watcher"),
            get(row, "Escalation Level"),
            get(row, "Escalation Contact Point"),
            etr if etr not in (None, "") else "N/A",
            get(row, "Time to resolution"),
            get(row, "Reason of OOSLA"),
            get(row, "Escalation Time (non-secure)") or get(row, "Escalation Time"),
            get(row, "OOSLA History (non-secure)") or get(row, "OOSLA History"),
            get(row, "OOSLA Last Update (non-secure)") or get(row, "OOSLA Last Update"),
        ]
        # Keep every eligible ticket in the main ITS sheet.
        result["its"].append(output)

        # Also copy matching tickets into their respective split sheets.
        kind = _group_kind(group)
        if kind == "nwg_ct":
            result["nwg_ct"].append(output)
        elif kind == "other":
            result["other"].append(output)
        # Excluded groups remain only in the main ITS sheet.
    return result


def write_oosla_sheets(wb: Workbook, tables: dict[str, list[list[Any]]]) -> None:
    """Add the three OOSLA sheets in the required order."""
    definitions = [
        ("ITS OOSLA INCs", "its"),
        ("NWG & CT INCs", "nwg_ct"),
        ("Other Group Assignees", "other"),
    ]
    for title, key in definitions:
        ws = wb.create_sheet(title)
        _write_table(ws, OOSLA_HEADERS, tables[key])
        # Split sheets omit Time to resolution and OOSLA History.
        if key != "its":
            ws.delete_cols(18, 1)  # Remove OOSLA History.
            ws.delete_cols(15, 1)  # Remove Time to resolution.
            if ws.max_column > 17 and all(
                ws.cell(row_idx, ws.max_column).value is None
                for row_idx in range(1, ws.max_row + 1)
            ):
                ws.delete_cols(ws.max_column, 1)
            _format_sheet(ws, date_columns=(7, 16, 17))
        else:
            _format_sheet(ws, date_columns=(7, 14, 17, 19))
        for row_idx in range(2, ws.max_row + 1):
            status_text = _text(ws.cell(row_idx, 5).value).lower()
            color = STATUS_COLORS.get(status_text)
            if color:
                ws.cell(row_idx, 5).fill = PatternFill("solid", fgColor=color)


def build_pit_rows(path: str | Path, sheet_name: str | None = None) -> list[list[Any]]:
    """Validate and transform a PIT export using the original macro's header mapping."""
    headers, source_rows = _read_rows(path, sheet_name)
    header_map: dict[str, int] = {}
    for idx, header in enumerate(headers):
        key = " ".join(_text(header).replace("\xa0", " ").lower().split())
        if key and key not in header_map:
            header_map[key] = idx

    required = [
        "ticket#", "summary", "pit", "group assignee", "p", "status",
        "created", "updated", "age of ticket", "vendor", "project picker",
    ]
    missing = [name for name in required if name not in header_map]
    if missing:
        raise ValueError("PIT file is missing required columns: " + ", ".join(missing))

    result = []
    for row in source_rows:
        ticket_idx = header_map["ticket#"]
        ticket = row[ticket_idx] if ticket_idx < len(row) else None
        if ticket is None or _text(ticket) == "":
            continue
        output = [ticket]
        for name in required[1:]:
            idx = header_map[name]
            output.append(row[idx] if idx < len(row) else None)
        result.append(output)

    result.sort(key=lambda row: _number(row[8], -1), reverse=True)
    return result


def write_pit_sheet(wb: Workbook, rows: list[list[Any]]) -> None:
    ws = wb.create_sheet("PIT OOSLA INCs")
    _write_table(ws, PIT_HEADERS, rows)
    _format_sheet(ws, date_columns=(8, 9))
    for row_idx in range(2, ws.max_row + 1):
        status_text = _text(ws.cell(row_idx, 7).value).lower()
        color = STATUS_COLORS.get(status_text)
        if color:
            ws.cell(row_idx, 7).fill = PatternFill("solid", fgColor=color)


def generate_report(pit_path: str | Path, oosla_path: str | Path, output_path: str | Path) -> Path:
    """Generate the four-sheet workbook. Source files are read-only and never modified."""
    pit_rows = build_pit_rows(pit_path)
    oosla_tables = build_oosla_rows(oosla_path)
    wb = Workbook()
    wb.remove(wb.active)
    write_pit_sheet(wb, pit_rows)
    write_oosla_sheets(wb, oosla_tables)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output)
    wb.close()
    return output
