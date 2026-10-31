from __future__ import annotations

import shutil
import subprocess
import tempfile
from starlette.background import BackgroundTask
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from ..auth import CurrentUser, require_auth
from ..services.oosla_pit_report import (
    build_oosla_rows,
    build_pit_rows,
    generate_report,
)

router = APIRouter(prefix="/api/oosla-pit", tags=["OOSLA/PIT"])

MAX_FILE_SIZE = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm"}


async def save_upload(upload: UploadFile, destination: Path) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type: {suffix or 'unknown'}. Upload .xlsx or .xlsm files.",
        )

    total = 0
    try:
        with destination.open("wb") as target:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        "Each file must be 25 MB or smaller.",
                    )
                target.write(chunk)
    finally:
        await upload.close()


def convert_with_libreoffice(source: Path, output_dir: Path) -> Path:
    executable = shutil.which("libreoffice") or shutil.which("soffice")
    if not executable:
        raise ValueError(
            "The OOSLA workbook could not be read and LibreOffice is unavailable."
        )

    profile_dir = output_dir / "lo-profile"
    profile_dir.mkdir()

    try:
        result = subprocess.run(
            [
                executable,
                f"-env:UserInstallation={profile_dir.as_uri()}",
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(output_dir),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("LibreOffice conversion timed out.") from exc

    converted = output_dir / source.name
    if result.returncode != 0 or not converted.is_file():
        details = (result.stderr or result.stdout or "").strip()
        raise ValueError(
            "LibreOffice could not convert the OOSLA workbook."
            + (f" Details: {details[:500]}" if details else "")
        )

    return converted


@router.post("/generate")
async def generate_oosla_pit_report(
    pit_file: UploadFile = File(...),
    oosla_file: UploadFile = File(...),
    user: CurrentUser = Depends(require_auth),
):
    """Generate the four-sheet OOSLA/PIT Excel report."""
    del user  # Role dependency validates access; no database write is required.

    temp_dir = Path(tempfile.mkdtemp(prefix="oosla-pit-"))
    try:
        pit_path = temp_dir / "pit-upload.xlsx"
        oosla_path = temp_dir / "oosla-upload.xlsx"
        output_path = temp_dir / "OOSLA_Tickets_Report.xlsx"

        await save_upload(pit_file, pit_path)
        await save_upload(oosla_file, oosla_path)

        try:
            # Validate PIT before trying to generate any output.
            build_pit_rows(pit_path)

            # Some source exports have malformed Excel styles. Convert a copy
            # only if openpyxl cannot read the original upload.
            try:
                build_oosla_rows(oosla_path)
            except Exception as initial_error:
                try:
                    converted_dir = temp_dir / "converted"
                    converted_dir.mkdir()
                    converted_source = temp_dir / "oosla-source.xlsx"
                    shutil.copy2(oosla_path, converted_source)
                    converted_path = convert_with_libreoffice(
                        converted_source, converted_dir
                    )
                    build_oosla_rows(converted_path)
                    oosla_path = converted_path
                except Exception as conversion_error:
                    raise ValueError(
                        "Could not read the OOSLA workbook, even after conversion. "
                        f"Initial error: {str(initial_error)[:250]}. "
                        f"Conversion error: {str(conversion_error)[:250]}"
                    ) from conversion_error

            generate_report(pit_path, oosla_path, output_path)

        except ValueError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, str(exc)
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Could not generate report. Check that both files are valid Excel workbooks. {str(exc)[:300]}",
            ) from exc

        return FileResponse(
            path=output_path,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            filename="OOSLA Tickets Report.xlsx",
            background=BackgroundTask(lambda: shutil.rmtree(temp_dir, ignore_errors=True)),
        )
    except BaseException:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
