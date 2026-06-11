"""
@file        md_parser_relations.py
@description Extract inter-table relations (link/load) from ParsedTable list.
@lastUpdate  2026-04-11 17:12:44
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from data_agent.ragic.models_phase9 import TableRelationEdge

if TYPE_CHECKING:
    from data_agent.ragic.models_phase9 import ParsedField, ParsedTable

logger = logging.getLogger(__name__)


class RelationExtractor:

    @staticmethod
    def extract(tables: list[ParsedTable]) -> list[TableRelationEdge]:
        table_name_index: dict[str, ParsedTable] = {t.table_name: t for t in tables}
        seen: set[tuple[str, str, str, str]] = set()
        edges: list[TableRelationEdge] = []

        for table in tables:
            RelationExtractor._process_fields(
                table.table_name, table.fields, table_name_index, seen, edges
            )
            for sub_fields in table.subtables.values():
                RelationExtractor._process_fields(
                    table.table_name, sub_fields, table_name_index, seen, edges
                )

        edges.sort(key=lambda e: (e.from_table, e.from_field))
        return edges

    @staticmethod
    def _process_fields(
        table_name: str,
        fields: list[ParsedField],
        table_name_index: dict[str, ParsedTable],
        seen: set[tuple[str, str, str, str]],
        edges: list[TableRelationEdge],
    ) -> None:
        for field in fields:
            if field.linked_to is not None:
                dedup_key = (
                    table_name, field.name,
                    field.linked_to.target_form, field.linked_to.target_field,
                )
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    if field.linked_to.target_form not in table_name_index:
                        logger.debug(
                            "Dangling link: %s.%s -> %s (not found in parsed tables)",
                            table_name, field.name, field.linked_to.target_form,
                        )
                    edges.append(TableRelationEdge(
                        from_table=table_name,
                        from_field=field.name,
                        from_field_id=field.field_id,
                        to_table=field.linked_to.target_form,
                        to_field=field.linked_to.target_field,
                        relation_type="link",
                    ))

            if field.loaded_from is not None:
                dedup_key = (
                    table_name, field.name,
                    field.loaded_from.source_form, field.loaded_from.source_field,
                )
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    if field.loaded_from.source_form not in table_name_index:
                        logger.debug(
                            "Dangling load: %s.%s -> %s (not found in parsed tables)",
                            table_name, field.name, field.loaded_from.source_form,
                        )
                    edges.append(TableRelationEdge(
                        from_table=table_name,
                        from_field=field.name,
                        from_field_id=field.field_id,
                        to_table=field.loaded_from.source_form,
                        to_field=field.loaded_from.source_field,
                        relation_type="load",
                        sync_mode=field.loaded_from.sync_mode or None,
                    ))
