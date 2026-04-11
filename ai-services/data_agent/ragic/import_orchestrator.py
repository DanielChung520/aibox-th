"""
@file        import_orchestrator.py
@description Orchestrate end-to-end MD schema import: parse → ArangoDB → Qdrant → intents.
@lastUpdate  2026-04-11 17:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from data_agent.ragic.arango_writer import RagicArangoWriter
from data_agent.ragic.intent_generator import IntentGenerator
from data_agent.ragic.intent_store import RagicIntentStore
from data_agent.ragic.md_parser import RagicMDParser
from data_agent.ragic.models_phase9 import ImportResult
from data_agent.ragic.schema_store import RagicSchemaStore

if TYPE_CHECKING:
    from data_agent.ragic.models_phase9 import ParsedTable

logger = logging.getLogger(__name__)

_INTENT_BATCH = 20


class RagicImportOrchestrator:

    def __init__(
        self,
        schema_store: RagicSchemaStore,
        intent_store: RagicIntentStore,
        arango_writer: RagicArangoWriter,
    ) -> None:
        self._schema_store = schema_store
        self._intent_store = intent_store
        self._arango_writer = arango_writer

    async def run_import(self, content: str, account: str) -> ImportResult:
        t0 = time.monotonic()
        result = ImportResult(account=account)

        tables = RagicMDParser.parse(content)
        result.tables_parsed = len(tables)
        logger.info("Parsed %d tables from MD content", len(tables))
        if not tables:
            result.duration_ms = (time.monotonic() - t0) * 1000
            return result

        await self._clear_existing(account, result)
        await self._write_arango(tables, account, result)
        await self._vectorize_schemas(tables, account, result)
        await self._generate_and_vectorize_intents(tables, account, result)
        await self._extract_relations_optional(tables, account, result)

        result.duration_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "Import complete: %d tables, %d schemas, %d intents, %.0fms",
            result.tables_parsed, result.schemas_vectorized,
            result.intents_generated, result.duration_ms,
        )
        return result

    async def _clear_existing(self, account: str, result: ImportResult) -> None:
        try:
            await self._arango_writer.clear_collections(account)
            await self._schema_store.delete_by_account(account)
            await self._intent_store.delete_by_account(account)
            logger.info("Cleared existing data for account '%s'", account)
        except Exception as e:
            msg = f"Clear step failed: {e}"
            logger.warning(msg)
            result.errors.append(msg)

    async def _write_arango(
        self,
        tables: list[ParsedTable],
        account: str,
        result: ImportResult,
    ) -> None:
        try:
            await self._arango_writer.ensure_collections()
            result.arango_tables_written = await self._arango_writer.write_tables(tables, account)
            result.arango_fields_written = await self._arango_writer.write_fields(tables, account)
            logger.info(
                "ArangoDB: %d tables, %d fields written",
                result.arango_tables_written, result.arango_fields_written,
            )
        except Exception as e:
            msg = f"ArangoDB write failed: {e}"
            logger.warning(msg)
            result.errors.append(msg)

    async def _vectorize_schemas(
        self,
        tables: list[ParsedTable],
        account: str,
        result: ImportResult,
    ) -> None:
        try:
            result.schemas_vectorized = await self._schema_store.bulk_upsert_from_parsed(
                tables, account
            )
            logger.info("Qdrant: %d schemas vectorized", result.schemas_vectorized)
        except Exception as e:
            msg = f"Schema vectorization failed: {e}"
            logger.warning(msg)
            result.errors.append(msg)

    async def _generate_and_vectorize_intents(
        self,
        tables: list[ParsedTable],
        account: str,
        result: ImportResult,
    ) -> None:
        try:
            gen = IntentGenerator()
            intents = gen.generate(tables, account)
            result.intents_generated = len(intents)
            for i in range(0, len(intents), _INTENT_BATCH):
                batch = intents[i : i + _INTENT_BATCH]
                await self._intent_store.upsert(batch)
            logger.info("Qdrant: %d intents generated and vectorized", len(intents))
        except Exception as e:
            msg = f"Intent generation/vectorization failed: {e}"
            logger.warning(msg)
            result.errors.append(msg)

    async def _extract_relations_optional(
        self,
        tables: list[ParsedTable],
        account: str,
        result: ImportResult,
    ) -> None:
        try:
            from data_agent.ragic.md_parser_relations import RelationExtractor

            edges = RelationExtractor.extract(tables)
            if edges:
                result.relations_extracted = len(edges)
                result.arango_relations_written = await self._arango_writer.write_relations(
                    edges, account
                )
                logger.info("Relations: %d extracted, %d written", len(edges), result.arango_relations_written)
        except ImportError:
            logger.debug("Phase 10 not yet built — skipping relation extraction")
        except Exception as e:
            msg = f"Relation extraction failed: {e}"
            logger.warning(msg)
            result.errors.append(msg)
