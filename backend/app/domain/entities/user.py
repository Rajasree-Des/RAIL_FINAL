from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    OFFICER = "officer"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    id: str
    username: str
    email: str
    password_hash: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None

    def has_role(self, role: UserRole) -> bool:
        return self.role == role

    def has_any_role(self, roles: list[UserRole]) -> bool:
        return self.role in roles

    def can_access_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def can_generate_reports(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.OFFICER]

    def can_upload_files(self) -> bool:
        return self.role in [UserRole.ADMIN, UserRole.OFFICER]
