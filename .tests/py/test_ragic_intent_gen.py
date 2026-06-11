"""
@file        test_ragic_intent_gen.py
@description RED phase TDD skeleton for auto-intent generator
@lastUpdate  2026-04-11 16:58:26
@author      Daniel Chung
@version     1.0.0
"""

import pytest
from data_agent.ragic.models import ParsedTable, ParsedField, RagicIntent
from data_agent.ragic.intent_generator import IntentGenerator


@pytest.fixture
def purchasing_table() -> ParsedTable:
    return ParsedTable(
        table_name="採購單",
        tab_path="purchasing",
        sheet_index=5,
        account="2025shianyong",
        fields=[],
    )


@pytest.fixture
def purchasing_table_with_fields() -> ParsedTable:
    return ParsedTable(
        table_name="採購單",
        tab_path="purchasing",
        sheet_index=5,
        account="2025shianyong",
        fields=[
            ParsedField(name="供應商", field_id="1015576", field_type="text", writable=True),
            ParsedField(name="品項名稱", field_id="1015577", field_type="text", writable=True),
        ],
    )


@pytest.fixture
def intent_generator() -> IntentGenerator:
    return IntentGenerator()


class TestIntentGeneration:

    def test_generate_intents_single_table(
        self, intent_generator: IntentGenerator, purchasing_table: ParsedTable
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table], account="2025shianyong"
        )
        # 3 actions (list, count, search) × 3 languages (zh_tw, zh_cn, en)
        assert len(intents) == 9
        assert all(isinstance(intent, RagicIntent) for intent in intents)
        assert all(intent.account == "2025shianyong" for intent in intents)
        assert all(intent.table_key == "purchasing/5" for intent in intents)

    def test_intent_nl_patterns_traditional(
        self, intent_generator: IntentGenerator, purchasing_table: ParsedTable
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table], account="2025shianyong"
        )

        zh_tw_intents = [i for i in intents if i.intent_id.endswith("_zh_tw")]
        assert len(zh_tw_intents) == 3

        # Check for expected patterns
        all_patterns = []
        for intent in zh_tw_intents:
            all_patterns.extend(intent.nl_patterns)

        patterns_to_check = ["列出所有採購單", "查詢採購單資料", "顯示採購單清單"]
        for pattern in patterns_to_check:
            assert any(pattern in p for p in all_patterns)

    def test_intent_nl_patterns_simplified(
        self, intent_generator: IntentGenerator, purchasing_table: ParsedTable
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table], account="2025shianyong"
        )

        zh_cn_intents = [i for i in intents if i.intent_id.endswith("_zh_cn")]
        assert len(zh_cn_intents) == 3

        all_patterns = []
        for intent in zh_cn_intents:
            all_patterns.extend(intent.nl_patterns)

        patterns_to_check = ["列出所有采购单", "查询采购单数据"]
        for pattern in patterns_to_check:
            assert any(pattern in p for p in all_patterns)

    def test_intent_nl_patterns_english(
        self, intent_generator: IntentGenerator, purchasing_table: ParsedTable
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table], account="2025shianyong"
        )

        en_intents = [i for i in intents if i.intent_id.endswith("_en")]
        assert len(en_intents) == 3

        all_patterns = []
        for intent in en_intents:
            all_patterns.extend(intent.nl_patterns)

        patterns_to_check = ["List all 採購單", "Show 採購單 data"]
        for pattern in patterns_to_check:
            assert any(pattern in p for p in all_patterns)

    def test_intent_id_format(
        self, intent_generator: IntentGenerator, purchasing_table: ParsedTable
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table], account="2025shianyong"
        )

        expected_ids = {
            "rgc_purchasing_5_list_zh_tw",
            "rgc_purchasing_5_list_zh_cn",
            "rgc_purchasing_5_list_en",
            "rgc_purchasing_5_count_zh_tw",
            "rgc_purchasing_5_count_zh_cn",
            "rgc_purchasing_5_count_en",
            "rgc_purchasing_5_search_zh_tw",
            "rgc_purchasing_5_search_zh_cn",
            "rgc_purchasing_5_search_en",
        }

        actual_ids = {intent.intent_id for intent in intents}
        assert actual_ids == expected_ids

    def test_generate_intents_with_fields(
        self,
        intent_generator: IntentGenerator,
        purchasing_table_with_fields: ParsedTable,
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[purchasing_table_with_fields], account="2025shianyong"
        )

        search_intents = [
            i for i in intents if "search" in i.intent_id and i.intent_id.endswith("_zh_tw")
        ]
        assert len(search_intents) == 1

        search_intent = search_intents[0]

        field_patterns = ["供應商", "品項名稱"]
        for field_pattern in field_patterns:
            assert any(
                field_pattern in pattern for pattern in search_intent.nl_patterns
            )

    def test_generate_empty_tables(
        self, intent_generator: IntentGenerator
    ) -> None:
        intents: list[RagicIntent] = intent_generator.generate(
            tables=[], account="2025shianyong"
        )

        assert intents == []
