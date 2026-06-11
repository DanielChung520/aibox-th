"""
Memory security module - secret scanning and path validation.
"""

import re
import hashlib
from pathlib import Path

from memory_agent.core.models import SecretDetectionResult, PathValidationResult


SECRET_PATTERNS = [
    (r"AKIA[A-Z0-9]{16}", "AWS Access Key"),
    (r"sk-ant-api03-[A-Za-z0-9_-]{80,}", "Anthropic API Key"),
    (r"sk-proj-[A-Za-z0-9_-]{80,}", "OpenAI API Key"),
    (r"gh[pousr]_[A-Za-z0-9_]{36,}", "GitHub Token"),
    (r"glpat-[A-Za-z0-9_-]{20}", "GitLab PAT"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack Token"),
    (r"-----BEGIN PRIVATE KEY-----", "PEM Private Key"),
    (r"AIza[--Za-z0-9_-]{35}", "GCP API Key"),
]


class SecurityError(Exception):
    pass


class SecretDetectedError(SecurityError):
    pass


class PathTraversalError(SecurityError):
    pass


def scan_content(content: str) -> SecretDetectionResult:
    detected = []
    for pattern, name in SECRET_PATTERNS:
        if re.search(pattern, content):
            detected.append(name)
    return SecretDetectionResult(
        has_secrets=len(detected) > 0,
        detected_patterns=detected,
    )


def scan_file(file_path: Path) -> SecretDetectionResult:
    if not file_path.exists():
        return SecretDetectionResult(has_secrets=False)
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return scan_content(content)
    except Exception:
        return SecretDetectionResult(has_secrets=False)


def validate_path_safety(
    relative_path: str,
    base_dir: Path,
) -> PathValidationResult:
    try:
        clean_path = relative_path.replace("\x00", "")
        clean_path = clean_path.replace("%2e%2e%2f", "..")
        clean_path = clean_path.replace("%2e%2e/", "..")
        clean_path = clean_path.replace("%2e/", ".")
        clean_path = clean_path.replace("%2e.", "..")
        fullwidth_dot = "\uff0e\uff0e\uff0f"
        if fullwidth_dot in clean_path:
            clean_path = clean_path.replace(fullwidth_dot, "..")
        if "\\" in clean_path and ":" in clean_path:
            return PathValidationResult(
                is_valid=False,
                error="Windows path traversal detected",
            )
        resolved = (base_dir / clean_path).resolve()
        if not str(resolved).startswith(str(base_dir.resolve())):
            return PathValidationResult(
                is_valid=False,
                error="Path traversal attempt detected",
            )
        return PathValidationResult(
            is_valid=True,
            sanitized_path=str(resolved),
        )
    except Exception as e:
        return PathValidationResult(
            is_valid=False,
            error=str(e),
        )


def validate_symlink_safety(file_path: Path, base_dir: Path) -> bool:
    try:
        if not file_path.is_symlink():
            return True
        target = file_path.resolve()
        if not str(target).startswith(str(base_dir.resolve())):
            return False
        if not target.exists():
            return False
        return True
    except Exception:
        return False


def compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()
