#!/usr/bin/env python3
"""
Top-level orchestrator intents for basic conversation.
Seeds greeting, thanks, apology, blessing, and web search intents.
"""

from seed_intent_catalog_shared import ORCH, insert_batch, make_orch_doc

TOP_INTENTS = [

    # ── 打招呼 ──────────────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_greeting",
        name="打招呼",
        description="用戶問候、打招呼、寒暄",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=["打招呼", "寒暄", "問候"],
        nl_examples=[
            "你好",
            "嗨",
            "哈囉",
            "早安",
            "午安",
            "晚安",
            "你好嗎",
            "今天好嗎",
        ],
        nl_patterns=[
            "你好", "嗨", "哈囉", "早安", "午安", "晚安",
            "你好嗎", "今天好嗎", "最近如何",
        ],
        action_type="direct_answer",
        target_agent="chat",
        response_strategy="direct_llm",
        priority=10,
    ),

    # ── 感謝 ────────────────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_thanks",
        name="感謝",
        description="用戶表達感謝、謝意",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=["表達謝意", "感謝"],
        nl_examples=[
            "謝謝",
            "謝謝你",
            "非常感謝",
            "多謝",
            "感恩",
            "感激不盡",
        ],
        nl_patterns=[
            "謝謝", "謝", "感謝", "多謝", "感恩", "感激",
        ],
        action_type="direct_answer",
        target_agent="chat",
        response_strategy="direct_llm",
        priority=10,
    ),

    # ── 抱歉 ────────────────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_apology",
        name="抱歉",
        description="用戶表達歉意、抱歉",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=["表達歉意", "抱歉"],
        nl_examples=[
            "抱歉",
            "對不起",
            "不好意思",
            "抱歉打擾了",
            "抱歉請見諒",
        ],
        nl_patterns=[
            "抱歉", "對不起", "不好意思", "抱歉打擾",
        ],
        action_type="direct_answer",
        target_agent="chat",
        response_strategy="direct_llm",
        priority=10,
    ),

    # ── 祝福 ────────────────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_blessing",
        name="祝福",
        description="用戶表達祝賀、祝福",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=["祝賀", "祝福"],
        nl_examples=[
            "生日快樂",
            "佳節愉快",
            "新年快樂",
            "恭喜",
            "祝好運",
            "祝福你",
        ],
        nl_patterns=[
            "生日快樂", "佳節愉快", "新年快樂", "恭喜",
            "祝好運", "祝福", "祝賀",
        ],
        action_type="direct_answer",
        target_agent="chat",
        response_strategy="direct_llm",
        priority=10,
    ),

    # ── 上網搜尋 ────────────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_web_search",
        name="上網搜尋",
        description="用戶要求上網搜尋資訊",
        intent_type="task",
        domain="general",
        bpa_id=None,
        capabilities=["上網搜尋", "網頁搜尋", "查資料"],
        nl_examples=[
            "幫我上網查一下",
            "幫我搜尋",
            "上網查",
            "查一下這個",
            "幫我找資料",
            "上網找一下",
            "謝謝，幫我上網查一下",
            "抱歉打擾，幫我上網查一下",
            "不好意思，幫我搜尋一下",
        ],
        nl_patterns=[
            "上網", "搜尋", "查一下", "找資料", "查資料",
            "上網查", "網頁搜尋",
        ],
        action_type="tool_call",
        target_agent="tool",
        tool_category="web_search",
        tool_name="web_search",
        response_strategy="direct_llm",
        priority=20,
    ),

    # ── 不知道/不理解 ──────────────────────────────────────────────────────
    make_orch_doc(
        intent_id="orch_unknown",
        name="未知/不理解",
        description="用戶表示不知道或不理解",
        intent_type="chat",
        domain="general",
        bpa_id=None,
        capabilities=["表示不解", "不知道"],
        nl_examples=[
            "我不知道",
            "我不清楚",
            "不了解",
            "聽不懂",
            "這是什麼意思",
        ],
        nl_patterns=[
            "不知道", "不清楚", "不了解", "聽不懂",
            "什麼意思", "不懂",
        ],
        action_type="direct_answer",
        target_agent="chat",
        response_strategy="direct_llm",
        priority=5,
    ),

]


if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print("Seeding Top Orchestrator intents")
    print(f"{'=' * 60}")
    print(f"\n[Top Orchestrator intents — {len(TOP_INTENTS)} docs]")
    insert_batch(TOP_INTENTS, "orchestrator top intents")
    print(f"\n{'=' * 60}")
    print("✅ Seeding complete")
    print(f"{'=' * 60}")
