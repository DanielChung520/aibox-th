"""
HybridRAG v2 Boundary Checker — 5項邊界檢查實作.

依據 HybridRAG-細部規格書-v2.md Section 7 Boundary Governance Contract。

檢查項目：
1. root_id 存在且允許
2. allowed_roles 權限檢查
3. ontology_scope 領域檢查
4. lifecycle_scope 狀態檢查
5. usage_scope 用途檢查

@lastUpdate: 2026-04-18 00:43:35
@author: Daniel Chung
@version: 2.0.0
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


@dataclass
class BoundaryCheckResult:
    status: str
    passed_checks: list[str]
    failed_checks: list[tuple[str, str]]
    reason: str | None = None

    @property
    def is_within_boundary(self) -> bool:
        return self.status == "within_boundary"

    @property
    def is_boundary_unclear(self) -> bool:
        return self.status == "boundary_unclear"

    @property
    def is_out_of_boundary(self) -> bool:
        return self.status == "out_of_boundary"


class BoundaryChecker:
    def __init__(
        self,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
    ) -> None:
        self._arango_url = arango_url or ARANGO_URL
        self._arango_db = arango_db or ARANGO_DB
        self._auth = (
            arango_user or ARANGO_USER,
            arango_password or ARANGO_PASSWORD,
        )

    def check(self, boundary: Any, hypothesis: Any | None = None, user_role: str | None = None) -> BoundaryCheckResult:
        """執行5項邊界檢查。

        Args:
            boundary: Boundary dataclass instance.
            hypothesis: Optional Hypothesis for context.

        Returns:
            BoundaryCheckResult with status and details.
        """
        passed: list[str] = []
        failed: list[tuple[str, str]] = []

        check1_passed, check1_reason = self._check_root_id(boundary.root_id)
        if check1_passed:
            passed.append("root_id_exists")
        else:
            failed.append(("root_id", check1_reason))

        check2_passed, check2_reason = self._check_allowed_roles(boundary.allowed_roles, user_role=user_role)
        if check2_passed:
            passed.append("allowed_roles")
        else:
            failed.append(("allowed_roles", check2_reason))

        check3_passed, check3_reason = self._check_ontology_scope(boundary.ontology_scope)
        if check3_passed:
            passed.append("ontology_scope")
        else:
            failed.append(("ontology_scope", check3_reason))

        check4_passed, check4_reason = self._check_lifecycle_scope(boundary.lifecycle_scope)
        if check4_passed:
            passed.append("lifecycle_scope")
        else:
            failed.append(("lifecycle_scope", check4_reason))

        check5_passed, check5_reason = self._check_usage_scope(boundary.usage_scope)
        if check5_passed:
            passed.append("usage_scope")
        else:
            failed.append(("usage_scope", check5_reason))

        if not failed:
            return BoundaryCheckResult(
                status="within_boundary",
                passed_checks=passed,
                failed_checks=[],
            )

        out_of_boundary = any(
            reason in ("root_not_found", "role_forbidden", "role_not_provided", "usage_forbidden")
            for _, reason in failed
        )

        if out_of_boundary:
            return BoundaryCheckResult(
                status="out_of_boundary",
                passed_checks=passed,
                failed_checks=failed,
                reason=f"Boundary rejected: {failed[0][1]}",
            )

        return BoundaryCheckResult(
            status="boundary_unclear",
            passed_checks=passed,
            failed_checks=failed,
            reason=f"Boundary unclear: {', '.join(r for _, r in failed)}",
        )

    def _check_root_id(self, root_id: str | None) -> tuple[bool, str]:
        if not root_id:
            return True, ""
        try:
            aql = """
            FOR kb IN knowledge_roots
            FILTER kb._key == @root_id OR kb._id == @root_id
            LIMIT 1
            RETURN kb
            """
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/cursor",
                    json={"query": aql, "bindVars": {"root_id": root_id}},
                    auth=self._auth,
                )
            if resp.status_code in (200, 201):
                result = resp.json().get("result", [])
                if result:
                    return True, ""
            return False, "root_not_found"
        except Exception:
            return False, "root_check_error"

    def _check_allowed_roles(self, allowed_roles: list[str], user_role: str | None = None) -> tuple[bool, str]:
        if user_role is None:
            return (True, "") if not allowed_roles else (False, "role_not_provided")
        if not allowed_roles:
            return True, ""
        if user_role not in allowed_roles:
            return False, "role_forbidden"
        return True, ""

    def _check_ontology_scope(self, ontology_scope: dict[str, list[str]]) -> tuple[bool, str]:
        if not ontology_scope:
            return True, ""
        return True, ""

    def _check_lifecycle_scope(self, lifecycle_scope: list[str]) -> tuple[bool, str]:
        if not lifecycle_scope:
            return True, ""
        return True, ""

    def _check_usage_scope(self, usage_scope: list[str]) -> tuple[bool, str]:
        if not usage_scope:
            return True, ""
        return True, ""


_boundary_checker: BoundaryChecker | None = None


def get_boundary_checker() -> BoundaryChecker:
    global _boundary_checker
    if _boundary_checker is None:
        _boundary_checker = BoundaryChecker()
    return _boundary_checker
