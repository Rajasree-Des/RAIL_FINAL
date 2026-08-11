import os
import re
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings
from app.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = frozenset(settings.allowed_file_extensions)
MAX_FILENAME_LENGTH = 255

MIME_TYPE_MAP = {
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
}

MAGIC_BYTES = {
    ".xlsx": b"PK\x03\x04",
    ".xls": b"\xd0\xcf\x11\xe0",
    ".csv": None,
}

DANGEROUS_PATTERNS = [
    r"\.\.",
    r"[<>:\"|?*]",
    r"[\x00-\x1f]",
    r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)",
]


class FileValidator:
    def __init__(self) -> None:
        self._allowed_extensions = ALLOWED_EXTENSIONS
        self._max_size = settings.max_upload_size_bytes
        self._dangerous_patterns = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]

    def validate_filename(self, filename: str) -> str:
        if not filename:
            raise ValidationError("Filename cannot be empty")

        if len(filename) > MAX_FILENAME_LENGTH:
            raise ValidationError(f"Filename exceeds maximum length of {MAX_FILENAME_LENGTH}")

        for pattern in self._dangerous_patterns:
            if pattern.search(filename):
                raise ValidationError("Filename contains invalid characters")

        return self.sanitize_filename(filename)

    def sanitize_filename(self, filename: str) -> str:
        name = os.path.basename(filename)
        name = re.sub(r"[^\w\s\-.]", "", name)
        name = re.sub(r"\s+", "_", name)
        name = name.strip("._")

        if not name:
            raise ValidationError("Filename is invalid after sanitization")

        return name

    def validate_extension(self, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext not in self._allowed_extensions:
            allowed = ", ".join(sorted(self._allowed_extensions))
            raise ValidationError(f"File type '{ext}' not allowed. Allowed: {allowed}")
        return ext

    def validate_size(self, size: int) -> None:
        if size <= 0:
            raise ValidationError("File is empty")
        if size > self._max_size:
            max_mb = self._max_size / (1024 * 1024)
            raise ValidationError(f"File exceeds maximum size of {max_mb:.0f}MB")

    def validate_content_type(self, content_type: str | None, extension: str) -> None:
        if not content_type:
            return

        expected = MIME_TYPE_MAP.get(extension)
        if expected and content_type not in [expected, "application/octet-stream"]:
            raise ValidationError(f"Content type mismatch for {extension} file")

    def validate_magic_bytes(self, file: BinaryIO, extension: str) -> None:
        expected_magic = MAGIC_BYTES.get(extension)
        if expected_magic is None:
            return

        current_pos = file.tell()
        file.seek(0)
        header = file.read(len(expected_magic))
        file.seek(current_pos)

        if header != expected_magic:
            raise ValidationError(f"File content does not match {extension} format")

    def validate_upload(
        self,
        filename: str,
        size: int,
        content_type: str | None = None,
        file: BinaryIO | None = None,
    ) -> str:
        safe_name = self.validate_filename(filename)
        ext = self.validate_extension(safe_name)
        self.validate_size(size)
        self.validate_content_type(content_type, ext)

        if file:
            self.validate_magic_bytes(file, ext)

        return safe_name


file_validator = FileValidator()
