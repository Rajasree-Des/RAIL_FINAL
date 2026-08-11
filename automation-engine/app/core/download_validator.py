"""Download validation — verify file exists and meets minimum size."""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".zip"}
MIN_FILE_SIZE_BYTES = 100


def validate_download(file_path: Path) -> tuple[bool, str]:
    if not file_path.exists():
        return False, "Download file not found"

    if not file_path.is_file():
        return False, "Download path is not a file"

    size = file_path.stat().st_size
    if size < MIN_FILE_SIZE_BYTES:
        return False, f"File too small ({size} bytes)"

    if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        return False, f"Unexpected file type: {file_path.suffix}"

    return True, "OK"
