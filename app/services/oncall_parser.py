from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


# =========================================================
# Text normalization
# =========================================================

_DIGIT_MAP = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).translate(_DIGIT_MAP)

    text = re.sub(
        r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff\u00a0]",
        " ",
        text,
    )

    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def name_key(value: str) -> str:
    text = clean_text(value).casefold()
    return re.sub(r"[^\w]", "", text, flags=re.UNICODE)


def clean_team(value: str) -> str:
    text = clean_text(value)

    text = re.sub(r"['’`]s\b", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\b(stand\s*by|stanfby|standby|on[\s-]?call)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\)(?=\S)", ") ", text)
    text = re.sub(r"\s+", " ", text).strip(" -_:")

    return text[:150] if text else "Unknown"


# =========================================================
# Phone number extraction
# =========================================================

def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", clean_text(value))

    if digits.startswith("0098"):
        digits = "0" + digits[4:]

    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]

    elif len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits

    return digits


def extract_phones(value: str) -> list[dict[str, str]]:
    text = clean_text(value)

    pattern = (
        r"(?<!\d)"
        r"((?:\+98|0098|98|0)?9\d{9}|0\d{10})"
        r"(?!\d)"
    )

    results = []

    for match in re.finditer(pattern, text):
        phone = normalize_phone(match.group(1))

        if phone:
            results.append({
                "label": "",
                "phone": phone,
            })

    return results


# =========================================================
# Date parsing
# =========================================================

def parse_date_any(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, (int, float)):
        try:
            if 30000 < value < 80000:
                return date(1899, 12, 30) + timedelta(days=int(value))
        except (ValueError, OverflowError):
            return None

    text = clean_text(value)

    if not text:
        return None

    iso_match = re.match(
        r"^(\d{4})-(\d{1,2})-(\d{1,2})",
        text,
    )

    if iso_match:
        try:
            return date(
                int(iso_match.group(1)),
                int(iso_match.group(2)),
                int(iso_match.group(3)),
            )
        except ValueError:
            return None

    text = re.sub(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
        r"mon|tue|tues|wed|thu|thr|thur|thurs|fri|sat|sun)\b\.?",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s,]+", " ", text).strip()

    formats = (
        "%b %d %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %y",
        "%d %b %y",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d.%m.%Y",
        "%Y/%m/%d",
    )

    for fmt in formats:
        try:
            parsed = datetime.strptime(text, fmt).date()

            if 2000 <= parsed.year <= 2100:
                return parsed

        except ValueError:
            continue

    return None


# =========================================================
# Shift parsing
# =========================================================

def parse_shift(value: str) -> tuple[time, time] | None:
    text = clean_text(value)

    match = re.search(
        r"(\d{1,2})[.:](\d{2})\s*"
        r"(?:-|–|to|till)\s*"
        r"(\d{1,2})[.:](\d{2})",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    try:
        start = time(int(match.group(1)), int(match.group(2)))
        end = time(int(match.group(3)), int(match.group(4)))

        return start, end

    except ValueError:
        return None


# =========================================================
# Person and role parsing
# =========================================================

def split_persons(value: str) -> list[dict[str, str]]:
    text = clean_text(value)

    if not text:
        return []

    results = []

    pattern = r"([^()+/,]+?)\s*\(([^)]*)\)"

    for match in re.finditer(pattern, text):
        name = match.group(1).strip(" -–+&,/")
        role = clean_text(match.group(2))

        if name:
            results.append({
                "name": name,
                "role": role,
            })

    if results:
        return results

    parts = re.split(
        r"\s+[+/,]\s+|\s+[-–]\s+|\s*\n\s*",
        text,
    )

    for part in parts:
        part = part.strip()

        if part:
            results.append({
                "name": part,
                "role": "",
            })

    return results


# =========================================================
# Source group detection
# =========================================================

def group_from_filename(filename: str) -> str:
    base = Path(filename).stem

    tokens = re.split(r"[\s_-]+", base)

    ignored = {
        "jan", "feb", "mar", "apr", "may", "jun",
        "jul", "aug", "sep", "sept", "oct", "nov", "dec",
        "january", "february", "march", "april",
        "june", "july", "august", "september",
        "october", "november", "december",
        "from", "to", "till", "until",
    }

    keep = []

    for token in tokens:
        if not token:
            continue

        if re.search(r"\d", token):
            continue

        if token.casefold() in ignored:
            continue

        keep.append(token)

    result = " ".join(keep).strip()

    return result[:100] if result else "Other"

# =========================================================
# Excel import (.xlsx / .xlsm)
# =========================================================

from openpyxl import load_workbook


HEADER_ALIASES = {
    "date": {
        "date", "day", "duty date", "on call date",
        "oncall date", "shift date",
    },
    "team": {
        "team", "department", "group", "unit",
        "service", "team name",
    },
    "name": {
        "name", "person", "contact", "engineer",
        "resource", "on call", "oncall", "employee",
    },
    "role": {
        "role", "position", "title", "designation",
    },
    "phone": {
        "phone", "mobile", "telephone", "contact number",
        "phone number", "mobile number",
    },
    "email": {
        "email", "e-mail", "mail", "email address",
    },
    "start": {
        "start", "start time", "from", "shift start",
    },
    "end": {
        "end", "end time", "to", "shift end",
    },
    "shift": {
        "shift", "time", "working hours", "duty hours",
    },
    "note": {
        "note", "notes", "remark", "remarks", "comment",
    },
}


def normalize_header(value: Any) -> str:
    text = clean_text(value).casefold()
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def identify_header(value: Any) -> str | None:
    header = normalize_header(value)

    for field, aliases in HEADER_ALIASES.items():
        if header in aliases:
            return field

    return None


def expand_merged_cells(ws) -> list[list[Any]]:
    rows = [
        [cell.value for cell in row]
        for row in ws.iter_rows()
    ]

    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds

        value = ws.cell(min_row, min_col).value

        for row_idx in range(min_row, max_row + 1):
            for col_idx in range(min_col, max_col + 1):
                rows[row_idx - 1][col_idx - 1] = value

    return rows


def find_header_row(rows: list[list[Any]]) -> tuple[int, dict[str, int]] | None:
    best = None
    best_score = 0

    for row_idx, row in enumerate(rows[:40]):
        mapping = {}

        for col_idx, value in enumerate(row):
            field = identify_header(value)

            if field and field not in mapping:
                mapping[field] = col_idx

        score = len(mapping)

        if score > best_score and (
            "name" in mapping or "phone" in mapping
        ):
            best = (row_idx, mapping)
            best_score = score

    return best


def value_at(row: list[Any], mapping: dict[str, int], field: str) -> Any:
    index = mapping.get(field)

    if index is None or index >= len(row):
        return None

    return row[index]


def parse_excel_time(value: Any) -> time | None:
    if isinstance(value, datetime):
        return value.time().replace(second=0, microsecond=0)

    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)

    if isinstance(value, (int, float)):
        try:
            seconds = int(float(value) * 86400) % 86400
            return (
                datetime.min + timedelta(seconds=seconds)
            ).time()
        except (ValueError, OverflowError):
            return None

    text = clean_text(value)

    if not text:
        return None

    for fmt in ("%H:%M", "%H.%M", "%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(text.upper(), fmt).time()
        except ValueError:
            continue

    return None


def make_entry(
    *,
    team: str,
    duty_date: date,
    name: str = "",
    role: str = "",
    phone: str = "",
    email: str = "",
    start: time | None = None,
    end: time | None = None,
    note: str = "",
) -> dict[str, Any]:

    return {
        "team": clean_team(team),
        "duty_date": duty_date,
        "shift_start": start,
        "shift_end": end,
        "person_name": clean_text(name)[:150],
        "role": clean_text(role)[:50],
        "phone": normalize_phone(phone)[:30],
        "email": clean_text(email)[:150],
        "note": clean_text(note)[:255],
    }


def parse_table_sheet(
    rows: list[list[Any]],
    team: str,
) -> list[dict[str, Any]]:

    header = find_header_row(rows)

    if not header:
        return []

    header_idx, mapping = header
    entries = []

    for row in rows[header_idx + 1:]:
        if not any(value is not None for value in row):
            continue

        raw_date = value_at(row, mapping, "date")
        duty_date = parse_date_any(raw_date)

        if duty_date is None:
            continue

        row_team = clean_text(value_at(row, mapping, "team")) or team

        raw_shift = value_at(row, mapping, "shift")
        shift = parse_shift(clean_text(raw_shift)) if raw_shift else None

        start = parse_excel_time(value_at(row, mapping, "start"))
        end = parse_excel_time(value_at(row, mapping, "end"))

        if shift:
            start, end = shift

        name = clean_text(value_at(row, mapping, "name"))
        role = clean_text(value_at(row, mapping, "role"))
        phone = clean_text(value_at(row, mapping, "phone"))
        email = clean_text(value_at(row, mapping, "email"))
        note = clean_text(value_at(row, mapping, "note"))

        if not any((name, phone, email)):
            continue

        people = split_persons(name) or [{"name": "", "role": ""}]

        for person in people:
            entries.append(make_entry(
                team=row_team,
                duty_date=duty_date,
                name=person["name"],
                role=person["role"] or role,
                phone=phone,
                email=email,
                start=start,
                end=end,
                note=note,
            ))

    return entries



def parse_offsite_sheet(rows: list[list[Any]], team: str) -> list[dict[str, Any]]:
    """Parse Off-Site roster sheets with one person column per responsibility."""
    header_idx = None
    mapping: dict[str, int] = {}

    aliases = {
        "date": {"date"},
        "group": {"group", "team"},
        "oncall": {"oncall", "on call"},
        "backup": {"backup"},
        "escalation": {"escalation"},
        "manager": {"manager"},
    }

    for idx, row in enumerate(rows[:30]):
        found = {}
        for col, value in enumerate(row):
            text = normalize_header(value)
            for field, names in aliases.items():
                if text in names and field not in found:
                    found[field] = col
        if "date" in found and any(k in found for k in ("oncall", "backup", "escalation", "manager")):
            header_idx, mapping = idx, found
            break

    if header_idx is None:
        return []

    entries = []
    role_fields = ("oncall", "backup", "escalation", "manager")

    for row in rows[header_idx + 1:]:
        date_col = mapping["date"]
        duty_date = parse_date_any(row[date_col] if date_col < len(row) else None)
        if duty_date is None:
            continue

        row_team = clean_text(
            row[mapping["group"]]
            if "group" in mapping and mapping["group"] < len(row)
            else ""
        ) or team

        for role in role_fields:
            col = mapping.get(role)
            if col is None or col >= len(row):
                continue

            raw = clean_text(row[col])
            if not raw:
                continue

            for person in split_persons(raw):
                name = person["name"].strip()
                if not name:
                    continue
                entries.append(make_entry(
                    team=row_team,
                    duty_date=duty_date,
                    name=name,
                    role=person["role"] or role.title(),
                ))

    return entries


def parse_weekly_sheet(rows: list[list[Any]], team: str) -> list[dict[str, Any]]:
    """Parse independent horizontal weekly standby tables."""
    entries = []
    headers = []

    for row_idx, row in enumerate(rows[:60]):
        for col_idx, value in enumerate(row):
            text = normalize_header(value)
            if text in {"date of week", "date", "duty date"}:
                headers.append((row_idx, col_idx))

    if not headers:
        return entries

    for header_pos, (header_row, date_col) in enumerate(headers):
        next_header_col = (
            headers[header_pos + 1][1]
            if header_pos + 1 < len(headers)
            and headers[header_pos + 1][0] == header_row
            else len(rows[header_row])
        )

        title = ""
        for title_row in range(max(0, header_row - 2), header_row):
            if date_col < len(rows[title_row]):
                candidate = clean_text(rows[title_row][date_col])
                if candidate:
                    title = candidate
        table_team = clean_team(title) if title else team

        day_col = date_col + 1
        shift = None
        shift_col = None
        for col in range(date_col + 1, min(next_header_col, date_col + 13)):
            if col >= len(rows[header_row]):
                break
            parsed = parse_shift(clean_text(rows[header_row][col]))
            if parsed:
                shift, shift_col = parsed, col
                break

        if shift_col is None:
            continue

        for row in rows[header_row + 1:]:
            raw_date = row[date_col] if date_col < len(row) else None
            duty_date = parse_date_any(raw_date)
            if duty_date is None:
                # Stop at the next table heading or a clear section break.
                if any(
                    normalize_header(v) in {"date of week", "date", "duty date"}
                    for v in row[date_col:next_header_col]
                ):
                    break
                continue

            # Names may occupy the shift column or adjacent cells in the table.
            last_col = min(next_header_col, max(shift_col + 1, date_col + 6))
            for col in range(shift_col, last_col):
                if col >= len(row):
                    continue
                raw_person = clean_text(row[col])
                if not raw_person or parse_date_any(raw_person) or parse_shift(raw_person):
                    continue
                if normalize_header(raw_person) in {"sat", "sun", "mon", "tue", "tues", "wed", "thu", "thur", "fri"}:
                    continue
                if "@" in raw_person or extract_phones(raw_person):
                    continue
                if re.fullmatch(r"[\d\s+()./-]+", raw_person):
                    continue

                for person in split_persons(raw_person):
                    name = person["name"].strip()
                    if not name:
                        continue
                    entries.append(make_entry(
                        team=table_team,
                        duty_date=duty_date,
                        name=name,
                        role=person["role"],
                        start=shift[0],
                        end=shift[1],
                    ))

    return entries

def parse_excel(
    file_path: str | Path,
    original_filename: str | None = None,
) -> dict[str, Any]:

    path = Path(file_path)
    filename = original_filename or path.name

    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        raise ValueError("Only .xlsx and .xlsm files are supported.")

    workbook = load_workbook(
        filename=path,
        read_only=False,
        data_only=True,
        keep_vba=path.suffix.lower() == ".xlsm",
    )

    all_entries = []
    sheet_reports = []

    default_team = clean_team(group_from_filename(filename))

    try:
        for ws in workbook.worksheets:
            rows = expand_merged_cells(ws)

            if not rows:
                continue

            sheet_team = clean_team(ws.title)

            if sheet_team in {"Sheet1", "Sheet2", "Sheet3"}:
                sheet_team = default_team

            offsite_entries = parse_offsite_sheet(rows, sheet_team)
            weekly_entries = parse_weekly_sheet(rows, sheet_team) if not offsite_entries else []
            table_entries = (
                parse_table_sheet(rows, sheet_team)
                if not offsite_entries and not weekly_entries
                else []
            )

            if offsite_entries:
                entries = offsite_entries
                structure = "offsite"
            elif weekly_entries:
                entries = weekly_entries
                structure = "weekly"
            else:
                entries = table_entries
                structure = "table"

            all_entries.extend(entries)

            sheet_reports.append({
                "sheet": ws.title,
                "structure": structure,
                "team": sheet_team,
                "rows_count": len(entries),
            })

    finally:
        workbook.close()

    dates = [
        entry["duty_date"]
        for entry in all_entries
    ]

    return {
        "entries": all_entries,
        "rows_count": len(all_entries),
        "period_start": min(dates) if dates else None,
        "period_end": max(dates) if dates else None,
        "source_group": default_team,
        "sheets": sheet_reports,
        "warnings": [] if all_entries else [
            "No On-Call records could be detected in this workbook."
        ],
    }




# =========================================================
# Manual Paste and Outlook MSG import
# =========================================================

def parse_period_text(text: str) -> tuple[date, date] | None:
    text = clean_text(text)
    date_pattern = (
        r"\d{4}-\d{1,2}-\d{1,2}"
        r"|\d{1,2}(?:st|nd|rd|th)?[\s/-]+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"[\s,-]+\d{2,4}"
        r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
        r"\s+\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{2,4}"
    )
    matches = re.findall(date_pattern, text, flags=re.IGNORECASE)
    dates = [parse_date_any(value) for value in matches]
    dates = [value for value in dates if value]

    if len(dates) >= 2:
        return dates[0], dates[1]
    if len(dates) == 1:
        return dates[0], dates[0]
    return None


def _contact_entries(
    text: str,
    group: str,
    start_date: date,
    end_date: date,
    shift_start: time,
    shift_end: time,
) -> list[dict[str, Any]]:
    entries = []
    seen = set()

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        columns = [
            clean_text(part)
            for part in re.split(r"\t+|\s{2,}", line)
            if clean_text(part)
        ]

        if not columns:
            continue

        normalized_line = clean_text(line)
        phones = extract_phones(normalized_line)
        emails = re.findall(
            r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            normalized_line,
            flags=re.IGNORECASE,
        )
        phone = phones[0]["phone"] if phones else ""
        email = emails[0] if emails else ""

        if re.search(
            r"\b(team|name|contact|phone|mobile|email|standby|on.?call)\b",
            normalized_line,
            re.IGNORECASE,
        ):
            continue

        if len(columns) >= 3:
            row_team = clean_team(columns[0])
            name = columns[1]
        elif len(columns) == 2:
            row_team = clean_team(columns[0]) if phone or email else group
            name = columns[1] if phone or email else columns[0]
        else:
            row_team = group
            name = columns[0]

        name = re.sub(
            r"\b(?:\+?98|0098)?[\d\s().-]{9,}\b", "", name
        ).strip(" -,:")
        name = re.sub(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            "",
            name,
        ).strip()

        if not name or (not phone and not email):
            continue

        key = (row_team.casefold(), name.casefold(), phone, email.casefold())
        if key in seen:
            continue
        seen.add(key)

        current = start_date
        while current <= end_date:
            entries.append(make_entry(
                team=row_team,
                duty_date=current,
                name=name,
                phone=phone,
                email=email,
                start=shift_start,
                end=shift_end,
            ))
            current += timedelta(days=1)

    return entries


def parse_pasted_text(
    text: str,
    group: str = "SAEI VAS",
    from_date: date | str | None = None,
    to_date: date | str | None = None,
    shift_start: str = "08:00",
    shift_end: str = "08:00",
) -> dict[str, Any]:
    text = str(text or "")
    if not text.strip():
        raise ValueError("Paste content is empty.")
    if len(text) > 200_000:
        raise ValueError("Paste content exceeds the 200,000 character limit.")

    if bool(from_date) != bool(to_date):
        raise ValueError("Both From and To dates must be provided.")

    if from_date and to_date:
        start_date = parse_date_any(from_date)
        end_date = parse_date_any(to_date)
    else:
        period = parse_period_text(text)
        if not period:
            raise ValueError("Could not detect a date range. Please provide From and To dates.")
        start_date, end_date = period

    if not start_date or not end_date or end_date < start_date:
        raise ValueError("Invalid date range.")

    if (end_date - start_date).days > 62:
        raise ValueError("The date range cannot exceed 62 days.")

    start = parse_excel_time(shift_start)
    end = parse_excel_time(shift_end)
    if not start or not end:
        raise ValueError("Invalid shift time. Use HH:MM format.")

    group = clean_team(group)
    entries = _contact_entries(
        text, group, start_date, end_date, start, end
    )
    if not entries:
        raise ValueError("No valid contact rows were found in the pasted text.")

    return {
        "entries": entries,
        "rows_count": len(entries),
        "period_start": start_date,
        "period_end": end_date,
        "source_group": group,
        "warnings": [],
    }


def parse_msg(file_path: str | Path) -> dict[str, Any]:
    try:
        import extract_msg
    except ImportError as exc:
        raise RuntimeError("The extract-msg package is required to read Outlook MSG files.") from exc

    path = Path(file_path)
    if not path.is_file() or path.stat().st_size < 1536:
        raise ValueError("Invalid or empty Outlook MSG file.")
    if path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("Outlook MSG file exceeds the 30 MB limit.")

    message = None
    try:
        message = extract_msg.Message(str(path))
        subject = clean_text(message.subject or "")
        body = clean_text(message.body or "")
    except Exception as exc:
        raise ValueError(f"Could not read Outlook MSG file: {exc}") from exc
    finally:
        if message is not None:
            try:
                message.close()
            except Exception:
                pass

    if not body:
        raise ValueError("The Outlook MSG message body is empty.")

    # Ignore quoted replies and forwarded message history.
    body = re.split(
        r"(?im)^\s*(?:From|Sent|发件人)\s*:",
        body,
        maxsplit=1,
    )[0]

    period = parse_period_text(subject + "\n" + body)
    if not period:
        raise ValueError(
            "No duty date range was found in this MSG. "
            "A contact-directory email cannot be imported as a dated roster."
        )

    start_date, end_date = period
    if end_date < start_date or (end_date - start_date).days > 62:
        raise ValueError("Invalid or unsupported date range in MSG.")

    group_text = re.sub(
        r"\b(plan|list|schedule|standby|on.?call)\b",
        " ",
        subject,
        flags=re.IGNORECASE,
    )
    group = clean_team(group_text) if group_text.strip() else group_from_filename(path.name)

    entries = _contact_entries(
        body,
        group,
        start_date,
        end_date,
        time(8, 0),
        time(8, 0),
    )
    if not entries:
        raise ValueError("No valid roster contacts were found in this MSG.")

    return {
        "entries": entries,
        "rows_count": len(entries),
        "period_start": start_date,
        "period_end": end_date,
        "source_group": group,
        "subject": subject,
        "warnings": [],
    }


# =========================================================
