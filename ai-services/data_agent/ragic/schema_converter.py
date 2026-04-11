"""
@file        schema_converter.py
@description Convert ParsedTable (from MD parser) to RagicTableSchema (for Qdrant).
@lastUpdate  2026-04-11 17:12:44
@author      Daniel Chung
@version     1.0.0
"""

import logging

from data_agent.ragic.models import RagicFieldSchema, RagicTableSchema
from data_agent.ragic.models_phase9 import ParsedField, ParsedTable

logger = logging.getLogger(__name__)


def _field_to_schema(field: ParsedField, subtable_key: str = "") -> RagicFieldSchema:
    """Convert a ParsedField into a RagicFieldSchema."""
    description_parts: list[str] = []
    if field.memo:
        description_parts.append(field.memo)

    return RagicFieldSchema(
        name=field.name,
        field_type=field.field_type,
        options=[],
        description=" ".join(description_parts),
        business_aliases=[],
        writable=field.writable,
        is_subtable_field=bool(subtable_key),
        subtable_key=subtable_key,
    )


def parsed_table_to_schema(
    table: ParsedTable,
    account: str,
) -> RagicTableSchema:
    """Convert one ParsedTable into a RagicTableSchema for Qdrant upsert.

    Args:
        table: Parsed table from MD parser.
        account: Ragic account identifier.

    Returns:
        A RagicTableSchema ready for Qdrant storage.
    """
    fields: dict[str, RagicFieldSchema] = {}

    for field in table.fields:
        fields[field.field_id] = _field_to_schema(field)

    for sub_key, sub_fields in table.subtables.items():
        for field in sub_fields:
            fields[field.field_id] = _field_to_schema(field, subtable_key=sub_key)

    subtables_map: dict[str, str] = {
        k: k for k in table.subtables
    }

    table_key = f"{table.tab_path}/{table.sheet_index}" if table.tab_path else table.table_name

    return RagicTableSchema(
        account=account,
        table_key=table_key,
        table_name=table.table_name,
        tab_path=table.tab_path,
        sheet_index=table.sheet_index,
        description=f"{table.tab_name} - {table.table_name}" if table.tab_name else table.table_name,
        module=table.tab_name,
        version="md-import",
        fields=fields,
        subtables=subtables_map,
    )


def convert_parsed_tables(
    tables: list[ParsedTable],
    account: str,
) -> list[RagicTableSchema]:
    """Batch-convert ParsedTable list to RagicTableSchema list.

    Args:
        tables: Parsed tables from MD parser.
        account: Ragic account identifier.

    Returns:
        List of RagicTableSchema objects.
    """
    schemas: list[RagicTableSchema] = []
    for table in tables:
        try:
            schema = parsed_table_to_schema(table, account)
            schemas.append(schema)
        except Exception:
            logger.warning(
                "Failed to convert table '%s', skipping",
                table.table_name,
                exc_info=True,
            )
    return schemas
