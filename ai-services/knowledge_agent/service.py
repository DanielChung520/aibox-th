from __future__ import annotations

import os
from typing import Any

import httpx

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


class KnowledgeManagementService:
    def __init__(
        self,
        arango_url: str | None = None,
        arango_db: str | None = None,
        arango_user: str | None = None,
        arango_password: str | None = None,
    ) -> None:
        self._arango_url = arango_url or ARANGO_URL
        self._arango_db = arango_db or ARANGO_DB
        self._auth = (arango_user or ARANGO_USER, arango_password or ARANGO_PASSWORD)

    def check_access(
        self, root_id: str | None, user_role: str | None, operation: str
    ) -> None:
        if not root_id:
            return
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/"
                    f"knowledge_roots/{root_id}",
                    auth=self._auth,
                )
                if resp.status_code == 404:
                    raise ValueError(f"knowledge root '{root_id}' not found")
                if resp.status_code not in (200, 201):
                    raise ValueError(f"failed to load knowledge root: {resp.status_code}")
                doc = resp.json()
                allowed_roles: list[str] | None = doc.get("allowed_roles")
                if allowed_roles:
                    if user_role is None:
                        raise ValueError(
                            f"operation '{operation}' requires a user_role but none provided"
                        )
                    if user_role not in allowed_roles:
                        raise ValueError(
                            f"user_role '{user_role}' is not permitted for operation "
                            f"'{operation}' on knowledge root '{root_id}'"
                        )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"access check failed: {exc}") from exc

    def check_and_get_root(self, root_id: str) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(
                    f"{self._arango_url}/_db/{self._arango_db}/_api/document/"
                    f"knowledge_roots/{root_id}",
                    auth=self._auth,
                )
                if resp.status_code == 404:
                    raise ValueError(f"knowledge root '{root_id}' not found")
                if resp.status_code not in (200, 201):
                    raise ValueError(f"failed to load knowledge root: {resp.status_code}")
                return dict(resp.json())
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"failed to fetch root: {exc}") from exc


_kms: KnowledgeManagementService | None = None


def get_knowledge_management_service() -> KnowledgeManagementService:
    global _kms
    if _kms is None:
        _kms = KnowledgeManagementService()
    return _kms
