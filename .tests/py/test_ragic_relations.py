"""
@file        test_ragic_relations.py
@description RED phase TDD test skeleton for RAGIC relation extractor
@lastUpdate  2026-04-11 16:58:26
@author      Daniel Chung
@version     1.0.0
"""

import pytest
from data_agent.ragic.models import (
    ParsedTable,
    ParsedField,
    LinkedFieldRef,
    LoadedFieldRef,
    TableRelationEdge,
)
from data_agent.ragic.md_parser_relations import RelationExtractor


@pytest.fixture
def org_table_with_links() -> ParsedTable:
    return ParsedTable(
        table_name="組織部門",
        fields=[
            ParsedField(
                name="建檔代碼",
                field_id="1015395",
                field_type="連結欄位",
                writable=True,
                linked_to=LinkedFieldRef(
                    target_form="編碼原則定義",
                    target_field="編碼",
                ),
            ),
        ],
    )


@pytest.fixture
def org_table_with_load() -> ParsedTable:
    return ParsedTable(
        table_name="組織部門",
        fields=[
            ParsedField(
                name="上級部門",
                field_id="1022588",
                field_type="文字",
                writable=True,
                loaded_from=LoadedFieldRef(
                    source_form="編碼原則定義",
                    source_field="類別",
                    sync_mode="隨時同步",
                ),
            ),
        ],
    )


@pytest.fixture
def employee_table_self_ref() -> ParsedTable:
    return ParsedTable(
        table_name="員工管理",
        fields=[
            ParsedField(
                name="代理人編號",
                field_id="1015500",
                field_type="連結欄位",
                writable=True,
                linked_to=LinkedFieldRef(
                    target_form="員工管理",
                    target_field="員工編號",
                ),
            ),
        ],
    )


@pytest.fixture
def table_no_relations() -> ParsedTable:
    return ParsedTable(
        table_name="基礎表單",
        fields=[
            ParsedField(name="名稱", field_id="100001", field_type="文字", writable=True),
            ParsedField(name="描述", field_id="100002", field_type="文字", writable=True),
        ],
    )


@pytest.fixture
def customer_table_with_parens() -> ParsedTable:
    return ParsedTable(
        table_name="交易紀錄",
        fields=[
            ParsedField(
                name="交易對象",
                field_id="100003",
                field_type="連結欄位",
                writable=True,
                linked_to=LinkedFieldRef(
                    target_form="交易對象(客戶/供應商)",
                    target_field="對象編號",
                ),
            ),
        ],
    )


def test_extract_link_relations(org_table_with_links: ParsedTable) -> None:
    edges = RelationExtractor.extract([org_table_with_links])

    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_table == "組織部門"
    assert edge.from_field == "建檔代碼"
    assert edge.to_table == "編碼原則定義"
    assert edge.to_field == "編碼"
    assert edge.relation_type == "link"


def test_extract_load_relations(org_table_with_load: ParsedTable) -> None:
    edges = RelationExtractor.extract([org_table_with_load])

    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_table == "組織部門"
    assert edge.from_field == "上級部門"
    assert edge.to_table == "編碼原則定義"
    assert edge.to_field == "類別"
    assert edge.relation_type == "load"
    assert edge.sync_mode == "隨時同步"


def test_extract_self_reference(employee_table_self_ref: ParsedTable) -> None:
    edges = RelationExtractor.extract([employee_table_self_ref])

    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_table == "員工管理"
    assert edge.to_table == "員工管理"
    assert edge.from_field == "代理人編號"
    assert edge.to_field == "員工編號"
    assert edge.relation_type == "link"


def test_extract_no_relations(table_no_relations: ParsedTable) -> None:
    edges = RelationExtractor.extract([table_no_relations])
    assert len(edges) == 0


def test_fuzzy_form_name_match(customer_table_with_parens: ParsedTable) -> None:
    edges = RelationExtractor.extract([customer_table_with_parens])

    assert len(edges) == 1
    edge = edges[0]
    assert edge.from_table == "交易紀錄"
    assert edge.to_table == "交易對象(客戶/供應商)"
    assert edge.relation_type == "link"


def test_extract_counts() -> None:
    tables = [
        ParsedTable(
            table_name="表單A",
            fields=[
                ParsedField(
                    name="連結字段1", field_id="f1", field_type="連結欄位", writable=True,
                    linked_to=LinkedFieldRef(target_form="表單B", target_field="編號"),
                ),
                ParsedField(
                    name="連結字段2", field_id="f2", field_type="連結欄位", writable=True,
                    linked_to=LinkedFieldRef(target_form="表單C", target_field="識別碼"),
                ),
            ],
        ),
        ParsedTable(
            table_name="表單D",
            fields=[
                ParsedField(
                    name="載入字段", field_id="f3", field_type="文字", writable=True,
                    loaded_from=LoadedFieldRef(
                        source_form="表單E", source_field="數據", sync_mode="每小時同步",
                    ),
                ),
            ],
        ),
    ]

    edges = RelationExtractor.extract(tables)
    assert len(edges) == 3
