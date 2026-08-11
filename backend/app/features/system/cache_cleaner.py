"""Safely clear whitelisted disposable cache directories."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DENY_SUFFIXES = {".db", ".sqlite", ".sqlite3"}
DENY_DIR_NAMES = {
    "output",
    "extracted",
    "report-configs",
    "uploads",
    "migrations",
    "templates",
    ".git",
    "node_modules",
    "app",
    "src",
    "tests",
}


@dataclass
class CacheCleanResult:
    cleared: list[str] = field(default_factory=list)
    files_removed: int = 0
    directories_removed: int = 0
    bytes_freed: int = 0
    skipped_locked: int = 0
    partial: bool = False


def _find_backend_root() -> Path:
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "app" / "main.py").is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    return cwd


def _find_repo_root(backend_root: Path) -> Path:
    parent = backend_root.parent
    if (parent / "package.json").is_file() or (parent / "vite.config.ts").is_file():
        return parent.resolve()
    return backend_root


def _is_denied_path(path: Path) -> bool:
    resolved = path.resolve()
    parts_lower = {p.lower() for p in resolved.parts}
    if "storage" in parts_lower:
        idx = resolved.parts.index("storage") if "storage" in resolved.parts else -1
        if idx >= 0 and idx + 1 < len(resolved.parts):
            sub = resolved.parts[idx + 1].lower()
            if sub in DENY_DIR_NAMES:
                return True
    if resolved.suffix.lower() in DENY_SUFFIXES:
        return True
    if resolved.name.lower() == "railway.db":
        return True
    if resolved.name == ".env" or resolved.name.startswith(".env."):
        return True
    return False


def _is_under(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _collect_whitelist_roots(backend_root: Path, repo_root: Path) -> list[tuple[Path, str]]:
    """Return (absolute path, label) pairs safe to clean."""
    candidates: list[tuple[Path, str]] = [
        (backend_root / ".pytest_cache", "filesystem:backend/.pytest_cache"),
        (backend_root / "storage" / "debug", "filesystem:storage/debug"),
        (
            backend_root / "storage" / "automation-screenshots",
            "filesystem:storage/automation-screenshots",
        ),
        (
            backend_root / "storage" / "_pdf_layout_probe",
            "filesystem:storage/_pdf_layout_probe",
        ),
        (repo_root / "node_modules" / ".vite", "filesystem:node_modules/.vite"),
    ]

    roots: list[tuple[Path, str]] = []
    for path, label in candidates:
        if path.exists():
            roots.append((path.resolve(), label))

    for pycache in backend_root.rglob("__pycache__"):
        if pycache.is_dir() and not _is_denied_path(pycache):
            roots.append((pycache.resolve(), f"filesystem:{pycache.relative_to(backend_root).as_posix()}"))

    # Deduplicate by resolved path
    seen: set[str] = set()
    unique: list[tuple[Path, str]] = []
    for path, label in roots:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append((path, label))
    return unique


def _safe_unlink_file(path: Path, result: CacheCleanResult) -> None:
    if _is_denied_path(path):
        return
    try:
        size = path.stat().st_size
        path.unlink()
        result.files_removed += 1
        result.bytes_freed += size
    except PermissionError:
        result.skipped_locked += 1
        result.partial = True
    except OSError:
        result.skipped_locked += 1
        result.partial = True


def _safe_rmdir(path: Path, result: CacheCleanResult) -> None:
    if _is_denied_path(path):
        return
    try:
        path.rmdir()
        result.directories_removed += 1
    except OSError:
        result.skipped_locked += 1
        result.partial = True


def clear_whitelisted_cache(
    *,
    backend_root: Path | None = None,
    repo_root: Path | None = None,
) -> CacheCleanResult:
    """Delete files under strict whitelist roots; never touch protected data."""
    backend = backend_root or _find_backend_root()
    repo = repo_root or _find_repo_root(backend)
    result = CacheCleanResult()

    for root, label in _collect_whitelist_roots(backend, repo):
        if not root.exists():
            continue
        if not _is_under(backend, root) and not _is_under(repo, root):
            continue

        touched = False
        if root.is_file():
            _safe_unlink_file(root, result)
            touched = True
        elif root.is_dir():
            for dirpath, dirnames, filenames in os.walk(root, topdown=False):
                current = Path(dirpath)
                if _is_denied_path(current):
                    continue
                for name in filenames:
                    file_path = current / name
                    if _is_denied_path(file_path):
                        continue
                    _safe_unlink_file(file_path, result)
                    touched = True
                for name in dirnames:
                    sub = current / name
                    if _is_denied_path(sub):
                        continue
                if current != root:
                    try:
                        if current.is_dir() and not any(current.iterdir()):
                            _safe_rmdir(current, result)
                            touched = True
                    except OSError:
                        result.skipped_locked += 1
                        result.partial = True

        if touched and label not in result.cleared:
            result.cleared.append(label)

    return result


def validate_cache_path(path: Path, allowed_root: Path) -> bool:
    """Reject path traversal outside allowed root."""
    try:
        resolved = path.resolve()
        root = allowed_root.resolve()
        resolved.relative_to(root)
        return not _is_denied_path(resolved)
    except ValueError:
        return False
