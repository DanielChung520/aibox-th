"""
@file        intent_generator.py
@description Auto-generate RagicIntent objects from ParsedTable list.
             Generates 3 actions × 3 languages = 9 intents per table.
@lastUpdate  2026-04-13 01:43:49
@author      Daniel Chung
@version     1.1.0
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from data_agent.ragic.models import RagicIntent

if TYPE_CHECKING:
    from data_agent.ragic.models_phase9 import ParsedTable

logger = logging.getLogger(__name__)

_TRAD_TO_SIMP: dict[str, str] = {
    "採購": "采购", "銷售": "销售", "庫存": "库存", "供應商": "供应商",
    "應收": "应收", "應付": "应付", "報價": "报价", "訂單": "订单",
    "發票": "发票", "倉庫": "仓库", "產品": "产品", "員工": "员工",
    "薪資": "薪资", "請假": "请假", "審核": "审核", "簽核": "签核",
    "資料": "资料", "數據": "数据", "設備": "设备", "維修": "维修",
    "客戶": "客户", "廠商": "厂商", "查詢": "查询", "顯示": "显示",
    "清單": "清单", "搜尋": "搜寻", "篩選": "筛选", "統計": "统计",
    "報表": "报表", "匯出": "汇出", "品項": "品项", "名稱": "名称",
    "編號": "编号", "規格": "规格", "數量": "数量", "金額": "金额",
    "狀態": "状态", "備註": "备注", "電話": "电话", "管理": "管理",
    "系統": "系统", "權限": "权限", "流程": "流程", "單據": "单据",
    "結算": "结算", "記錄": "记录", "預算": "预算", "進貨": "进货",
    "單": "单", "項": "项", "條": "条", "張": "张", "號": "号",
    "類": "类", "價": "价", "計": "计", "總": "总", "費": "费",
}

_ACTIONS = ("list", "count", "search", "filter")
_LANGS = ("zh_tw", "zh_cn", "en")


def _to_simplified(text: str) -> str:
    result = text
    for trad, simp in sorted(_TRAD_TO_SIMP.items(), key=lambda x: -len(x[0])):
        result = result.replace(trad, simp)
    return result


def _list_patterns_zh_tw(name: str) -> list[str]:
    return [
        f"列出所有{name}",
        f"查詢{name}資料",
        f"顯示{name}清單",
        f"{name}有哪些",
    ]


def _count_patterns_zh_tw(name: str) -> list[str]:
    return [
        f"{name}有幾筆",
        f"統計{name}數量",
        f"{name}共幾筆資料",
    ]


def _search_patterns_zh_tw(name: str, field_names: list[str]) -> list[str]:
    patterns = [
        f"搜尋{name}",
        f"篩選{name}資料",
    ]
    for fname in field_names[:3]:
        patterns.append(f"查詢{name}的{fname}")
    return patterns


def _list_patterns_zh_cn(name: str) -> list[str]:
    cn = _to_simplified(name)
    return [
        f"列出所有{cn}",
        f"查询{cn}数据",
        f"显示{cn}清单",
    ]


def _count_patterns_zh_cn(name: str) -> list[str]:
    cn = _to_simplified(name)
    return [
        f"{cn}有几笔",
        f"统计{cn}数量",
        f"{cn}共几笔数据",
    ]


def _search_patterns_zh_cn(name: str, field_names: list[str]) -> list[str]:
    cn = _to_simplified(name)
    patterns = [
        f"搜寻{cn}",
        f"筛选{cn}数据",
    ]
    for fname in field_names[:3]:
        patterns.append(f"查询{cn}的{_to_simplified(fname)}")
    return patterns


def _list_patterns_en(name: str) -> list[str]:
    return [
        f"List all {name}",
        f"Show {name} data",
        f"Get {name} records",
    ]


def _count_patterns_en(name: str) -> list[str]:
    return [
        f"Count {name}",
        f"How many {name}",
        f"Total {name} records",
    ]


def _search_patterns_en(name: str, field_names: list[str]) -> list[str]:
    patterns = [
        f"Search {name}",
        f"Filter {name}",
    ]
    for fname in field_names[:3]:
        patterns.append(f"Find {name} by {fname}")
    return patterns


def _filter_patterns_zh_tw(name: str, field_names: list[str]) -> list[str]:
    patterns = [f"篩選{name}"]
    for fname in field_names[:3]:
        patterns.append(f"查詢{fname}是什麼的{name}")
    return patterns


def _filter_patterns_zh_cn(name: str, field_names: list[str]) -> list[str]:
    cn = _to_simplified(name)
    patterns = [f"筛选{cn}"]
    for fname in field_names[:3]:
        patterns.append(f"查询{_to_simplified(fname)}是什么的{cn}")
    return patterns


def _filter_patterns_en(name: str, field_names: list[str]) -> list[str]:
    patterns = [f"Filter {name} by criteria"]
    for fname in field_names[:3]:
        patterns.append(f"Find {name} where {fname} equals")
    return patterns


_PATTERN_FUNCS: dict[
    str, dict[str, object]
] = {
    "list_zh_tw": {"fn": _list_patterns_zh_tw, "needs_fields": False},
    "list_zh_cn": {"fn": _list_patterns_zh_cn, "needs_fields": False},
    "list_en": {"fn": _list_patterns_en, "needs_fields": False},
    "count_zh_tw": {"fn": _count_patterns_zh_tw, "needs_fields": False},
    "count_zh_cn": {"fn": _count_patterns_zh_cn, "needs_fields": False},
    "count_en": {"fn": _count_patterns_en, "needs_fields": False},
    "search_zh_tw": {"fn": _search_patterns_zh_tw, "needs_fields": True},
    "search_zh_cn": {"fn": _search_patterns_zh_cn, "needs_fields": True},
    "search_en": {"fn": _search_patterns_en, "needs_fields": True},
    "filter_zh_tw": {"fn": _filter_patterns_zh_tw, "needs_fields": True},
    "filter_zh_cn": {"fn": _filter_patterns_zh_cn, "needs_fields": True},
    "filter_en": {"fn": _filter_patterns_en, "needs_fields": True},
}

_DESC_TEMPLATES: dict[str, str] = {
    "list": "列出{name}所有記錄",
    "count": "統計{name}記錄數量",
    "search": "搜尋/篩選{name}記錄",
    "filter": "依條件篩選{name}記錄",
}

_ACTION_QUERY_TYPE: dict[str, str] = {
    "list": "simple_filter",
    "count": "aggregate",
    "search": "simple_filter",
    "filter": "simple_filter",
}

_ACTION_GENERATION_STRATEGY: dict[str, str] = {
    "list": "tool_calling",
    "count": "tool_calling",
    "search": "tool_calling",
    "filter": "tool_calling",
}


class IntentGenerator:

    def generate(
        self,
        tables: list[ParsedTable],
        account: str,
        table_id_map: dict[str, dict[str, str]] | None = None,
    ) -> list[RagicIntent]:
        id_map = table_id_map or {}
        intents: list[RagicIntent] = []
        for table in tables:
            table_key = f"{table.tab_path}/{table.sheet_index}"
            mapped = id_map.get(table_key, {})
            table_id = mapped.get("table_id", "")
            sheet_key = mapped.get("sheet_key", "")
            field_names = [f.name for f in table.fields]
            core = field_names[:5]
            group = f"{table.tab_name}-{table.table_name}" if table.tab_name else table.table_name
            for action in _ACTIONS:
                for lang in _LANGS:
                    key = f"{action}_{lang}"
                    intent_id = f"rgc_{table.tab_path}_{table.sheet_index}_{key}"
                    cfg = _PATTERN_FUNCS[key]
                    fn = cfg["fn"]
                    if cfg["needs_fields"]:
                        patterns = fn(table.table_name, field_names)  # type: ignore[operator]
                    else:
                        patterns = fn(table.table_name)  # type: ignore[operator]
                    intents.append(
                        RagicIntent(
                            intent_id=intent_id,
                            agent_scope="data_agent",
                            account=account,
                            name=f"{table.table_name}-{action}",
                            nl_patterns=patterns,
                            description=_DESC_TEMPLATES[action].format(name=table.table_name),
                            action=action,
                            table_key=table_key,
                            table_id=table_id,
                            sheet_key=sheet_key,
                            tables=[table_id] if table_id else [],
                            group=group,
                            core_fields=core,
                            query_type=_ACTION_QUERY_TYPE[action],
                            generation_strategy=_ACTION_GENERATION_STRATEGY[action],
                        )
                    )
        return intents
