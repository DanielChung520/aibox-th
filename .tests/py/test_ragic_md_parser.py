"""
@file        test_ragic_md_parser.py
@description RED phase TDD tests for Ragic MD parser — RagicMDParser class
@lastUpdate  2026-04-11 16:58:26
@author      Daniel Chung
@version     1.0.0
"""

import textwrap
import pytest
from data_agent.ragic.models import ParsedTable, ParsedField, LinkedFieldRef, LoadedFieldRef
from data_agent.ragic.md_parser import RagicMDParser


@pytest.fixture
def single_table_md() -> str:
    return textwrap.dedent("""
        ## 頁籤： 資料庫

        ### 表單: 鄉鎮區+郵遞區號

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 縣市及鄉鎮市區 | 1015367 | 文字 | 唯讀 | 任意文字 | 唯讀不可重複 |
        | 郵遞區號 | 1015368 | 文字 | 唯讀 | 任意文字 | 唯讀 |
    """).strip()


@pytest.fixture
def subtable_md() -> str:
    return textwrap.dedent("""
        ## 頁籤： 主要資料

        ### 表單: 主表單

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 名稱 | 1015367 | 文字 | 可寫入 | 任意文字 | 主欄位 |

        #### 子表格欄位標頭 (子表格Key: 1015442)

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 品項 | 1015443 | 文字 | 可寫入 | 任意文字 | 子表格欄位1 |
        | 數量 | 1015444 | 數字 | 可寫入 | 數字 | 子表格欄位2 |
    """).strip()


@pytest.fixture
def linked_field_md() -> str:
    return textwrap.dedent("""
        ## 頁籤： 參考資料

        ### 表單: 編碼表

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 編碼 | 1015367 | 文字 | 可寫入 | 任意文字 | 連結到編碼原則定義表單上的編碼 |
    """).strip()


@pytest.fixture
def loaded_field_md() -> str:
    return textwrap.dedent("""
        ## 頁籤： 參考資料

        ### 表單: 編碼表

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 類別 | 1015367 | 文字 | 可寫入 | 任意文字 | 從編碼原則定義表單上的類別載入欄位值 (設定為隨時同步) |
    """).strip()


@pytest.fixture
def multi_tab_md() -> str:
    return textwrap.dedent("""
        ## 頁籤： 基本資料維護檔

        ### 表單: 使用者資料

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 姓名 | 1015367 | 文字 | 可寫入 | 任意文字 | 必填 |

        ### 表單: 部門資料

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/2
        - API 網址: https://ap15.ragic.com/2025shianyong/database/2?api
        - 主表單Key: 1015370

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 部門名 | 1015368 | 文字 | 可寫入 | 任意文字 | 部門 |
    """).strip()


def test_parse_single_table(single_table_md: str) -> None:
    tables = RagicMDParser.parse(single_table_md)
    assert len(tables) == 1
    table = tables[0]
    assert table.table_name == "鄉鎮區+郵遞區號"
    assert table.tab_name == "資料庫"
    assert len(table.fields) == 2
    assert table.main_form_key == "1015369"


def test_parse_fields(single_table_md: str) -> None:
    tables = RagicMDParser.parse(single_table_md)
    table = tables[0]
    fields = table.fields
    
    assert fields[0].name == "縣市及鄉鎮市區"
    assert fields[0].field_id == "1015367"
    assert fields[0].field_type == "文字"
    assert fields[0].writable is False
    assert fields[0].memo == "唯讀不可重複"
    
    assert fields[1].name == "郵遞區號"
    assert fields[1].field_id == "1015368"
    assert fields[1].field_type == "文字"
    assert fields[1].writable is False


def test_parse_subtable(subtable_md: str) -> None:
    tables = RagicMDParser.parse(subtable_md)
    table = tables[0]
    
    assert "1015442" in table.subtables
    subtable = table.subtables["1015442"]
    assert len(subtable) == 2
    assert subtable[0].name == "品項"
    assert subtable[0].field_id == "1015443"
    assert subtable[1].name == "數量"
    assert subtable[1].field_id == "1015444"


def test_parse_linked_field_memo(linked_field_md: str) -> None:
    tables = RagicMDParser.parse(linked_field_md)
    field = tables[0].fields[0]
    
    assert field.linked_to is not None
    assert field.linked_to.target_form == "編碼原則定義"
    assert field.linked_to.target_field == "編碼"


def test_parse_loaded_field_memo(loaded_field_md: str) -> None:
    tables = RagicMDParser.parse(loaded_field_md)
    field = tables[0].fields[0]
    
    assert field.loaded_from is not None
    assert field.loaded_from.source_form == "編碼原則定義"
    assert field.loaded_from.source_field == "類別"
    assert field.loaded_from.sync_mode == "隨時同步"


def test_parse_tab_grouping(multi_tab_md: str) -> None:
    tables = RagicMDParser.parse(multi_tab_md)
    assert len(tables) == 2
    
    assert tables[0].tab_name == "基本資料維護檔"
    assert tables[0].table_name == "使用者資料"
    
    assert tables[1].tab_name == "基本資料維護檔"
    assert tables[1].table_name == "部門資料"


def test_parse_url_extraction(single_table_md: str) -> None:
    tables = RagicMDParser.parse(single_table_md)
    table = tables[0]
    
    assert table.tab_path == "database"
    assert table.sheet_index == 1
    assert table.account == "2025shianyong"


def test_parse_writable_mapping(multi_tab_md: str) -> None:
    tables = RagicMDParser.parse(multi_tab_md)
    
    user_table = tables[0]
    assert user_table.fields[0].writable is True
    
    dept_table = tables[1]
    assert dept_table.fields[0].writable is True


def test_parse_empty_input() -> None:
    result = RagicMDParser.parse("")
    assert result == []


def test_parse_malformed_row() -> None:
    malformed_md = textwrap.dedent("""
        ## 頁籤： 測試

        ### 表單: 測試表單

        - 表單網址: https://ap15.ragic.com/2025shianyong/database/1
        - API 網址: https://ap15.ragic.com/2025shianyong/database/1?api
        - 主表單Key: 1015369

        | Field Name | Field ID | Type | Writable | Write Format | Memo |
        | --- | --- | --- | --- | --- | --- |
        | 欄位1 | 1015367 | 文字 | 可寫入 | 任意文字 | 正常 |
        | 欄位2 | 唯讀 | 缺少欄位 |
        | 欄位3 | 1015368 | 文字 | 可寫入 | 任意文字 | 正常 |
    """).strip()
    
    tables = RagicMDParser.parse(malformed_md)
    assert len(tables) == 1
    assert len(tables[0].fields) >= 2
