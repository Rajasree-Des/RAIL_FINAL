from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class PasswordHasher:
    def __init__(self) -> None:
        self._hasher = Argon2Hasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        try:
            self._hasher.verify(hashed, password)
            return True
        except (VerifyMismatchError, InvalidHashError):
            return False

    @staticmethod
    def is_valid_hash_format(hashed: str) -> bool:
        """Return True when stored hash looks like a supported Argon2 digest."""
        return hashed.startswith("$argon2")

    def needs_rehash(self, hashed: str) -> bool:
        return self._hasher.check_needs_rehash(hashed)


password_hasher = PasswordHasher()
