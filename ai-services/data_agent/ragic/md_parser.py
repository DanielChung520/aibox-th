"""
@file        md_parser.py
@description Parse Ragic schema definitions from Markdown documents.
             Extracts tables, fields, subtables, and link/load references.
@lastUpdate  2026-04-11 17:08:22
@author      Daniel Chung
@version     1.0.0
"""

import logging
import re
from urllib.parse import urlparse

from data_agent.ragic.models_phase9 import (
    LinkedFieldRef,
    LoadedFieldRef,
    ParsedField,
    ParsedTable,
)

logger = logging.getLogger(__name__)

# --- regex: 連結到<form>表單上的<field> ---
_LINK_RE = re.compile(r"連結到(?P<form>.+?)表單上的(?P<field>\S+)")
# --- regex: 從<form>表單上的<field>載入欄位值 (設定為<sync>) ---
_LOAD_RE = re.compile(
    r"從(?P<form>.+?)表單上的(?P<field>[^\s載]+)載入欄位值"
    r"(?:\s*\(設定為(?P<sync>[^)]+)\))?"
)

_TAB_RE = re.compile(r"^##\s+頁籤[：:]\s*(.+)$")
_FORM_RE = re.compile(r"^###\s+表單[：:]\s*(.+)$")
_SUBTABLE_RE = re.compile(r"^####\s+子表格欄位標頭\s*\(子表格Key:\s*(\S+)\)")
_META_URL_RE = re.compile(r"^-\s*表單網址:\s*(.+)$")
_META_API_RE = re.compile(r"^-\s*API\s*網址:\s*(.+)$")
_META_KEY_RE = re.compile(r"^-\s*主表單Key:\s*(\S+)$")

_WRITABLE_TRUE = {"可寫入", "可寫入（空值時自動帶入）"}
_WRITABLE_FALSE = {"唯讀", "唯讀（自動產生）"}


class RagicMDParser:

    @staticmethod
    def parse(content: str) -> list[ParsedTable]:
        if not content.strip():
            return []

        lines = content.split("\n")
        tables: list[ParsedTable] = []
        current_tab = ""
        current_table: ParsedTable | None = None
        current_subtable_key: str | None = None
        in_field_table = False
        field_header_seen = False

        for line in lines:
            stripped = line.strip()

            tab_m = _TAB_RE.match(stripped)
            if tab_m:
                _finalize(current_table, tables)
                current_table = None
                current_tab = tab_m.group(1).strip()
                in_field_table = False
                current_subtable_key = None
                continue

            form_m = _FORM_RE.match(stripped)
            if form_m:
                _finalize(current_table, tables)
                current_table = ParsedTable(
                    table_name=form_m.group(1).strip(),
                    tab_name=current_tab,
                )
                in_field_table = False
                field_header_seen = False
                current_subtable_key = None
                continue

            if current_table is None:
                continue

            url_m = _META_URL_RE.match(stripped)
            if url_m:
                current_table.form_url = url_m.group(1).strip()
                continue

            api_m = _META_API_RE.match(stripped)
            if api_m:
                raw = api_m.group(1).strip()
                current_table.api_url = raw
                _extract_url_parts(raw, current_table)
                continue

            key_m = _META_KEY_RE.match(stripped)
            if key_m:
                current_table.main_form_key = key_m.group(1).strip()
                continue

            sub_m = _SUBTABLE_RE.match(stripped)
            if sub_m:
                current_subtable_key = sub_m.group(1).strip()
                current_table.subtables[current_subtable_key] = []
                in_field_table = False
                field_header_seen = False
                continue

            if stripped.startswith("####"):
                if current_subtable_key is not None:
                    current_subtable_key = None
                    in_field_table = False
                    field_header_seen = False
                continue

            if _is_pipe_header(stripped):
                in_field_table = True
                field_header_seen = False
                continue

            if in_field_table and _is_separator_row(stripped):
                field_header_seen = True
                continue

            if in_field_table and field_header_seen and stripped.startswith("|"):
                field = _parse_field_row(stripped)
                if field is not None:
                    if current_subtable_key is not None:
                        current_table.subtables[current_subtable_key].append(field)
                    else:
                        current_table.fields.append(field)
                continue

            if in_field_table and not stripped.startswith("|") and stripped:
                in_field_table = False
                field_header_seen = False

        _finalize(current_table, tables)
        return tables


def _finalize(table: ParsedTable | None, tables: list[ParsedTable]) -> None:
    if table is not None and table.table_name:
        tables.append(table)


def _extract_url_parts(api_url: str, table: ParsedTable) -> None:
    clean = api_url.split("?")[0].rstrip("/")
    parsed = urlparse(clean)
    parts = [p for p in parsed.path.split("/") if p]
    # pattern: /<account>/<tab_path>/<sheet_index>
    if len(parts) >= 3:
        table.account = parts[0]
        table.tab_path = parts[1]
        try:
            table.sheet_index = int(parts[2])
        except ValueError:
            logger.warning("Non-integer sheet index in URL: %s", api_url)


def _is_pipe_header(line: str) -> bool:
    if not line.startswith("|"):
        return False
    lower = line.lower()
    return "field name" in lower and "field id" in lower


def _is_separator_row(line: str) -> bool:
    return bool(line.startswith("|") and re.match(r"^\|[\s\-|]+\|$", line))


def _parse_field_row(line: str) -> ParsedField | None:
    cells = [c.strip() for c in line.split("|")]
    cells = [c for c in cells if c != ""]

    if len(cells) < 4:
        logger.debug("Skipping malformed row (< 4 cols): %s", line[:80])
        return None

    name = cells[0]
    field_id = cells[1]
    field_type = cells[2]
    writable_raw = cells[3] if len(cells) > 3 else ""
    write_format = cells[4] if len(cells) > 4 else ""
    memo = cells[5] if len(cells) > 5 else ""

    writable = _parse_writable(writable_raw)
    linked_to = _parse_link_memo(memo)
    loaded_from = _parse_load_memo(memo)

    return ParsedField(
        name=name,
        field_id=field_id,
        field_type=field_type,
        writable=writable,
        write_format=write_format,
        memo=memo,
        linked_to=linked_to,
        loaded_from=loaded_from,
    )


def _parse_writable(raw: str) -> bool:
    cleaned = raw.strip()
    if cleaned in _WRITABLE_TRUE:
        return True
    if cleaned in _WRITABLE_FALSE:
        return False
    return "可寫入" in cleaned


def _parse_link_memo(memo: str) -> LinkedFieldRef | None:
    m = _LINK_RE.search(memo)
    if m:
        return LinkedFieldRef(
            target_form=m.group("form").strip(),
            target_field=m.group("field").strip(),
        )
    return None


def _parse_load_memo(memo: str) -> LoadedFieldRef | None:
    m = _LOAD_RE.search(memo)
    if m:
        return LoadedFieldRef(
            source_form=m.group("form").strip(),
            source_field=m.group("field").strip(),
            sync_mode=(m.group("sync") or "").strip(),
        )
    return None
