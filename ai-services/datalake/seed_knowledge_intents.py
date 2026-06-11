#!/usr/bin/env python3
"""
@file        seed_knowledge_intents.py
@description Knowledge domain intents for HybridRAG intent catalog seeding.
             These intents are used by the Knowledge Agent for query classification
             and HybridRAG retrieval (vector + graph fusion).
@lastUpdate  2026-04-05 12:00:00
@author      Daniel Chung
@version     1.0.0
"""

from .seed_intent_catalog_shared import insert_batch

ARANGO_URL = "http://localhost:8529"
DB = "abc_desktop"
AUTH = "root:abc_desktop_2026"
COLLECTION = "intent_catalog"
TS = "2026-04-05T00:00:00Z"

KNOWLEDGE = "knowledge"


# ---------------------------------------------------------------------------
# Knowledge Intent Builder
# ---------------------------------------------------------------------------


def make_knowledge_doc(
    intent_id: str,
    name: str,
    description: str,
    query_type: str,
    nl_examples: list[str],
    priority: int = 0,
) -> dict:
    """Build a Knowledge domain intent document for HybridRAG.

    Args:
        intent_id: Unique intent identifier (e.g., "knowledge.structured_query")
        name: Human-readable intent name
        description: Description of what this intent handles
        query_type: HybridRAG query type - "structure_query", "entity_query", or "semantic_query"
        nl_examples: List of natural language example queries
        priority: Intent priority (higher = matched first)
    """
    return {
        "_key": intent_id,
        "intent_id": intent_id,
        "agent_scope": KNOWLEDGE,
        "name": name,
        "description": description,
        "intent_type": "query",
        "query_type": query_type,
        "nl_examples": nl_examples,
        "status": "enabled",
        "priority": priority,
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    }


# ---------------------------------------------------------------------------
# Knowledge Intents — Group A: Structure Query (框架/步驟/流程)
# ---------------------------------------------------------------------------

GROUP_A_STRUCTURE_QUERY = [
    make_knowledge_doc(
        intent_id="knowledge.structured_query.process",
        name="流程步驟查詢",
        description="查詢知識庫中的流程、步驟、階段、順序等結構化內容",
        query_type="structure_query",
        nl_examples=[
            "AI需求分析的步驟是什麼？",
            "系統架構設計的流程",
            "這個框架包含哪些階段？",
            "專案執行的流程說明",
            "申請流程的步驟",
            "知識庫中關於系統架構的流程說明",
        ],
        priority=10,
    ),
    make_knowledge_doc(
        intent_id="knowledge.structured_query.framework",
        name="框架結構查詢",
        description="查詢知識庫中的框架、方法論、架構設計等結構化內容",
        query_type="structure_query",
        nl_examples=[
            "解釋一下 Scrum 框架",
            "這個系統的架構設計是什麼？",
            "微服務架構的組成部分",
            "DevOps 流程框架",
        ],
        priority=9,
    ),
    make_knowledge_doc(
        intent_id="knowledge.structured_query.hierarchy",
        name="組織層次查詢",
        description="查詢知識庫中的組織結構、階層、分類等層次內容",
        query_type="structure_query",
        nl_examples=[
            "公司組織架構是什麼？",
            "這個部門的層級結構",
            "產品分類的層次",
        ],
        priority=8,
    ),
]

# ---------------------------------------------------------------------------
# Knowledge Intents — Group B: Entity Query (實體關係)
# ---------------------------------------------------------------------------

GROUP_B_ENTITY_QUERY = [
    make_knowledge_doc(
        intent_id="knowledge.entity_query.relation",
        name="實體關係查詢",
        description="查詢兩個實體之間的關係、連接、包含等",
        query_type="entity_query",
        nl_examples=[
            "X和Y之間的關係是什麼？",
            "這個概念和那個概念有什麼關聯？",
            "A 與 B 的差異",
            "兩者的區別是什麼？",
            "這個包含哪些組成部分？",
        ],
        priority=10,
    ),
    make_knowledge_doc(
        intent_id="knowledge.entity_query.membership",
        name="歸屬關係查詢",
        description="查詢實體的歸屬、分類、屬於等關係",
        query_type="entity_query",
        nl_examples=[
            "這是哪個部門的系統？",
            "這個模組屬於什麼層？",
            "該功能屬於哪個子系統？",
        ],
        priority=9,
    ),
    make_knowledge_doc(
        intent_id="knowledge.entity_query.comparison",
        name="實體比較查詢",
        description="比較兩個或多個實體的異同",
        query_type="entity_query",
        nl_examples=[
            "比較 A 和 B 的優缺點",
            "這兩種方案有什麼不同？",
            "傳統與現代方法的差異",
        ],
        priority=8,
    ),
]

# ---------------------------------------------------------------------------
# Knowledge Intents — Group C: Semantic Query (語義理解)
# ---------------------------------------------------------------------------

GROUP_C_SEMANTIC_QUERY = [
    make_knowledge_doc(
        intent_id="knowledge.semantic_query.explanation",
        name="語義解釋查詢",
        description="解釋概念、術語、原理等語義內容",
        query_type="semantic_query",
        nl_examples=[
            "解釋一下區塊鏈是什麼",
            "什麼是雲端運算？",
            "AI 是怎麼運作的？",
            "微服務的原理",
        ],
        priority=10,
    ),
    make_knowledge_doc(
        intent_id="knowledge.semantic_query.summary",
        name="內容摘要查詢",
        description="獲取文件、文章、報告的摘要或重點",
        query_type="semantic_query",
        nl_examples=[
            "這份文件在說什麼？",
            "總結一下這篇文章的重點",
            "給我這份報告的摘要",
            "這份文件的主要內容",
        ],
        priority=9,
    ),
    make_knowledge_doc(
        intent_id="knowledge.semantic_query.related",
        name="相關內容查詢",
        description="查詢與關鍵詞相關的知識內容",
        query_type="semantic_query",
        nl_examples=[
            "關於系統安全的相关内容",
            "與知識管理相關的文章",
            "相關的技術文章有哪些？",
            "這個主題還有哪些參考資料？",
        ],
        priority=8,
    ),
    make_knowledge_doc(
        intent_id="knowledge.semantic_query.definition",
        name="術語定義查詢",
        description="查詢專業術語、名詞的定義",
        query_type="semantic_query",
        nl_examples=[
            "什麼是 RESTful API？",
            "定義一下敏捷開發",
            "這個術語的意思",
        ],
        priority=7,
    ),
]

# ---------------------------------------------------------------------------
# Orchestrator Routing Intents — Knowledge Domain
# ---------------------------------------------------------------------------

KNOWLEDGE_ORCHESTRATOR_INTENTS = [
    {
        "_key": "orch.knowledge.search",
        "intent_id": "orch.knowledge.search",
        "agent_scope": "orchestrator",
        "name": "知識庫搜尋",
        "description": "搜尋知識庫中的相關內容，支援 HybridRAG 混合檢索",
        "intent_type": "task",
        "domain": "knowledge",
        "bpa_id": None,
        "capabilities": ["hybrid_rag", "vector_search", "graph_search"],
        "nl_examples": [
            "在知識庫中搜尋相關資料",
            "查一下知識庫中關於系統架構的內容",
            "知識庫中有哪些關於這個主題的文件",
        ],
        "confidence_threshold": 0.7,
        "priority": 50,
        "status": "enabled",
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    },
    {
        "_key": "orch.knowledge.structured",
        "intent_id": "orch.knowledge.structured",
        "agent_scope": "orchestrator",
        "name": "結構化知識查詢",
        "description": "查詢知識庫中的流程、步驟、框架等結構化內容",
        "intent_type": "task",
        "domain": "knowledge",
        "bpa_id": None,
        "capabilities": ["hybrid_rag", "structure_query"],
        "nl_examples": [
            "查詢系統架構的設計步驟",
            "知識庫中這個流程包含哪些階段",
        ],
        "confidence_threshold": 0.7,
        "priority": 45,
        "status": "enabled",
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    },
    {
        "_key": "orch.knowledge.entity_relation",
        "intent_id": "orch.knowledge.entity_relation",
        "agent_scope": "orchestrator",
        "name": "實體關係查詢",
        "description": "查詢知識庫中實體之間的關係",
        "intent_type": "task",
        "domain": "knowledge",
        "bpa_id": None,
        "capabilities": ["hybrid_rag", "entity_query"],
        "nl_examples": [
            "X 和 Y 的關係是什麼",
            "這個概念包含哪些部分",
        ],
        "confidence_threshold": 0.7,
        "priority": 45,
        "status": "enabled",
        "created_at": TS,
        "updated_at": TS,
        "updated_by": "system",
    },
]


# ---------------------------------------------------------------------------
# All Knowledge Intents
# ---------------------------------------------------------------------------

ALL_KNOWLEDGE = (
    GROUP_A_STRUCTURE_QUERY
    + GROUP_B_ENTITY_QUERY
    + GROUP_C_SEMANTIC_QUERY
)


# ---------------------------------------------------------------------------
# Main Seeder
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print("Seeding Knowledge Agent intents (HybridRAG)")
    print(f"{'=' * 60}")

    print(f"\n[Structure Query intents — {len(GROUP_A_STRUCTURE_QUERY)} docs]")
    insert_batch(GROUP_A_STRUCTURE_QUERY, "knowledge structure_query intents")

    print(f"\n[Entity Query intents — {len(GROUP_B_ENTITY_QUERY)} docs]")
    insert_batch(GROUP_B_ENTITY_QUERY, "knowledge entity_query intents")

    print(f"\n[Semantic Query intents — {len(GROUP_C_SEMANTIC_QUERY)} docs]")
    insert_batch(GROUP_C_SEMANTIC_QUERY, "knowledge semantic_query intents")

    print(f"\n[Orchestrator Knowledge intents — {len(KNOWLEDGE_ORCHESTRATOR_INTENTS)} docs]")
    insert_batch(KNOWLEDGE_ORCHESTRATOR_INTENTS, "orchestrator knowledge intents")

    total = len(ALL_KNOWLEDGE) + len(KNOWLEDGE_ORCHESTRATOR_INTENTS)
    print(f"\n{'=' * 60}")
    print(f"✅ Seeding complete: {total} intents total")
    print(f"   Knowledge Agent:    {len(ALL_KNOWLEDGE)} (Groups A-C)")
    print(f"   Orchestrator:      {len(KNOWLEDGE_ORCHESTRATOR_INTENTS)}")
    print(f"{'=' * 60}")
