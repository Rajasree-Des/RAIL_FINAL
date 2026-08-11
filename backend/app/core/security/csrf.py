import secrets
import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings
from app.core.exceptions import ValidationError


class CSRFProtection:
    def __init__(self) -> None:
        self._serializer = URLSafeTimedSerializer(settings.csrf_secret_key)
        self._max_age = 3600  # 1 hour

    def generate_token(self, session_id: str) -> str:
        """Generate a CSRF token bound to a session ID."""
        return self._serializer.dumps(session_id, salt="csrf-token")

    def generate_session_and_token(self) -> tuple[str, str]:
        """Generate a new session ID and corresponding CSRF token."""
        session_id = str(uuid.uuid4())
        token = self.generate_token(session_id)
        return session_id, token

    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate a CSRF token against a session ID."""
        try:
            decoded = self._serializer.loads(token, salt="csrf-token", max_age=self._max_age)
            return secrets.compare_digest(decoded, session_id)
        except (BadSignature, SignatureExpired):
            return False

    def validate_or_raise(self, token: str, session_id: str) -> None:
        """Validate a CSRF token or raise ValidationError."""
        if not self.validate_token(token, session_id):
            raise ValidationError("Invalid or expired CSRF token")


csrf_protection = CSRFProtection()
