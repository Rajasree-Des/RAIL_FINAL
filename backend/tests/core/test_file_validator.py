
import pytest

from app.core.exceptions import ValidationError
from app.core.security.file_validator import FileValidator


@pytest.fixture
def validator():
    return FileValidator()


class TestFilenameValidation:
    def test_valid_filename(self, validator):
        result = validator.validate_filename("report.xlsx")
        assert result == "report.xlsx"

    def test_empty_filename(self, validator):
        with pytest.raises(ValidationError) as exc:
            validator.validate_filename("")
        assert "empty" in str(exc.value.message).lower()

    def test_path_traversal_attack(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("../../../etc/passwd")

    def test_path_traversal_in_name(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("file..xlsx")

    def test_dangerous_windows_chars(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("file<script>.xlsx")

    def test_null_byte(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("file\x00.xlsx")

    def test_windows_reserved_names(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("CON.xlsx")

    def test_long_filename(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_filename("a" * 300 + ".xlsx")


class TestExtensionValidation:
    def test_valid_xlsx(self, validator):
        ext = validator.validate_extension("report.xlsx")
        assert ext == ".xlsx"

    def test_valid_xls(self, validator):
        ext = validator.validate_extension("report.xls")
        assert ext == ".xls"

    def test_valid_csv(self, validator):
        ext = validator.validate_extension("report.csv")
        assert ext == ".csv"

    def test_invalid_extension(self, validator):
        with pytest.raises(ValidationError) as exc:
            validator.validate_extension("report.exe")
        assert ".exe" in str(exc.value.message)

    def test_no_extension(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_extension("report")

    def test_double_extension_attack(self, validator):
        with pytest.raises(ValidationError) as exc:
            validator.validate_extension("report.xlsx.exe")
        assert ".exe" in str(exc.value.message)


class TestSizeValidation:
    def test_valid_size(self, validator):
        validator.validate_size(1024 * 1024)

    def test_empty_file(self, validator):
        with pytest.raises(ValidationError) as exc:
            validator.validate_size(0)
        assert "empty" in str(exc.value.message).lower()

    def test_oversized_file(self, validator):
        with pytest.raises(ValidationError) as exc:
            validator.validate_size(100 * 1024 * 1024)
        assert "size" in str(exc.value.message).lower()


class TestSanitizeFilename:
    def test_spaces_to_underscores(self, validator):
        result = validator.sanitize_filename("my report.xlsx")
        assert " " not in result
        assert "_" in result

    def test_remove_special_chars(self, validator):
        result = validator.sanitize_filename("report@#$%.xlsx")
        assert "@" not in result
        assert "#" not in result

    def test_strip_leading_dots(self, validator):
        result = validator.sanitize_filename(".hidden.xlsx")
        assert not result.startswith(".")

    def test_preserve_extension(self, validator):
        result = validator.sanitize_filename("my file.xlsx")
        assert result.endswith(".xlsx")


class TestFullValidation:
    def test_valid_upload(self, validator):
        result = validator.validate_upload(
            filename="report.xlsx",
            size=1024,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert result == "report.xlsx"

    def test_invalid_extension_rejected(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_upload(
                filename="malware.exe",
                size=1024,
            )

    def test_oversized_rejected(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_upload(
                filename="large.xlsx",
                size=100 * 1024 * 1024,
            )
