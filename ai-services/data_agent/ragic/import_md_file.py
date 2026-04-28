"""
@file        import_md_file.py
@description Import a local Ragic Markdown schema file into ArangoDB/Qdrant via the existing orchestrator.
@lastUpdate  2026-04-24 10:25:51
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx

from data_agent.ragic.arango_writer import RagicArangoWriter
from data_agent.ragic.import_orchestrator import RagicImportOrchestrator
from data_agent.ragic.intent_store import IntentVectorStore
from data_agent.ragic.md_parser import RagicMDParser
from data_agent.ragic.schema_store import RagicSchemaStore

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


def _default_md_path() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / ".docs" / "Ragic" / "dawnlink" / "dawnlink202604.md"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse or import a Ragic Markdown schema file. "
            "Dry-run by default; add --apply to actually update ArangoDB/Qdrant."
        )
    )
    parser.add_argument(
        "--file",
        default=str(_default_md_path()),
        help="Path to the Ragic markdown file",
    )
    parser.add_argument(
        "--account",
        default="",
        help="Override Ragic account. If omitted, infer from API URLs in the markdown.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually run the import and update ArangoDB/Qdrant.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def _infer_account(markdown: str, override: str) -> str:
    if override.strip():
        return override.strip()

    tables = RagicMDParser.parse(markdown)
    accounts = sorted({table.account.strip() for table in tables if table.account.strip()})
    if len(accounts) == 1:
        return accounts[0]
    if not accounts:
        raise ValueError("Cannot infer account from markdown; please provide --account")
    raise ValueError(
        "Multiple accounts found in markdown: " + ", ".join(accounts) + ". Please provide --account"
    )


def _build_parse_summary(markdown: str, account: str, file_path: Path) -> dict[str, object]:
    tables = RagicMDParser.parse(markdown)
    field_count = 0
    linked_field_count = 0
    loaded_field_count = 0
    subtable_field_count = 0

    for table in tables:
        field_count += len(table.fields)
        linked_field_count += sum(1 for field in table.fields if field.linked_to is not None)
        loaded_field_count += sum(1 for field in table.fields if field.loaded_from is not None)

        for sub_fields in table.subtables.values():
            subtable_field_count += len(sub_fields)
            field_count += len(sub_fields)
            linked_field_count += sum(1 for field in sub_fields if field.linked_to is not None)
            loaded_field_count += sum(1 for field in sub_fields if field.loaded_from is not None)

    return {
        "mode": "dry-run",
        "file": str(file_path),
        "account": account,
        "tables_parsed": len(tables),
        "fields_parsed": field_count,
        "subtable_fields_parsed": subtable_field_count,
        "linked_fields_parsed": linked_field_count,
        "loaded_fields_parsed": loaded_field_count,
    }


async def _verify_linked_field_persistence(account: str) -> dict[str, int]:
    query = (
        "LET linked = LENGTH(FOR d IN da_field_info_ragic FILTER d.account == @account "
        "AND d.linked_to != null RETURN 1) "
        "LET loaded = LENGTH(FOR d IN da_field_info_ragic FILTER d.account == @account "
        "AND d.loaded_from != null RETURN 1) "
        "LET memo = LENGTH(FOR d IN da_field_info_ragic FILTER d.account == @account "
        "AND d.memo != null AND d.memo != '' RETURN 1) "
        "RETURN {linked_fields_persisted: linked, loaded_fields_persisted: loaded, memo_fields_persisted: memo}"
    )
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{ARANGO_URL}/_db/{ARANGO_DB}/_api/cursor",
            json={"query": query, "bindVars": {"account": account}},
            auth=(ARANGO_USER, ARANGO_PASSWORD),
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        if isinstance(result, list) and result:
            row = result[0]
            if isinstance(row, dict):
                return {
                    "linked_fields_persisted": int(row.get("linked_fields_persisted", 0)),
                    "loaded_fields_persisted": int(row.get("loaded_fields_persisted", 0)),
                    "memo_fields_persisted": int(row.get("memo_fields_persisted", 0)),
                }
    return {
        "linked_fields_persisted": 0,
        "loaded_fields_persisted": 0,
        "memo_fields_persisted": 0,
    }


async def _run_apply(markdown: str, account: str, file_path: Path) -> dict[str, object]:
    orchestrator = RagicImportOrchestrator(
        schema_store=RagicSchemaStore(),
        intent_store=IntentVectorStore(),
        arango_writer=RagicArangoWriter(),
    )
    result = await orchestrator.run_import(markdown, account)
    verify = await _verify_linked_field_persistence(account)

    return {
        "mode": "apply",
        "file": str(file_path),
        "account": account,
        "import_result": result.model_dump(),
        "verification": verify,
    }


async def _async_main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    file_path = Path(args.file).expanduser().resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    markdown = file_path.read_text(encoding="utf-8")
    account = _infer_account(markdown, args.account)

    if args.apply:
        payload = await _run_apply(markdown, account, file_path)
    else:
        payload = _build_parse_summary(markdown, account, file_path)

    if args.pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


def main() -> int:
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
