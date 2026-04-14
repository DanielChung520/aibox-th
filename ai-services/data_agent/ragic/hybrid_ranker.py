from typing import Any

AGGREGATE_KEYWORDS = {
    "統計", "平均", "總和", "最大", "最小",
    "count", "sum", "avg", "max", "min",
    "各", "排名", "匯總", "計數"
}
COMPLEX_KEYWORDS = {
    "且", "或者", "和", "或", "但是",
    "而且", "其中", "只", "如果", "條件"
}


class QueryComplexity:
    SIMPLE = "simple"
    COMPLEX = "complex"


class HybridRankResult:
    table_key: str
    score: float
    complexity: str
    related_tables: list[str]

    def __init__(
        self,
        table_key: str,
        score: float,
        complexity: str,
        related_tables: list[str],
    ) -> None:
        self.table_key = table_key
        self.score = score
        self.complexity = complexity
        self.related_tables = related_tables


class RagicHybridRanker:
    def __init__(self) -> None:
        self._vectors: Any = None
        self._graph: Any = None

    def _get_vectors(self) -> Any:
        if self._vectors is None:
            from data_agent.ragic.intent_store import IntentVectorStore
            self._vectors = IntentVectorStore()
        return self._vectors

    def _get_graph(self) -> Any:
        if self._graph is None:
            from data_agent.ragic.graph_query import RagicGraphQuery
            self._graph = RagicGraphQuery()
        return self._graph

    def _classify_complexity(self, query: str) -> str:
        q_lower = query.lower()
        if any(kw in q_lower for kw in AGGREGATE_KEYWORDS):
            return QueryComplexity.COMPLEX
        if any(kw in q_lower for kw in COMPLEX_KEYWORDS):
            return QueryComplexity.COMPLEX
        return QueryComplexity.SIMPLE

    async def rank(
        self,
        query: str,
        account: str,
        top_k: int = 8,
    ) -> list[HybridRankResult]:
        vectors = self._get_vectors()
        graph = self._get_graph()

        vector_hits = await vectors.search(
            query=query,
            account=None,
            top_k=top_k * 2,
            score_threshold=0.25,
        )
        if not vector_hits:
            return []

        top_table = ""
        first_payload = vector_hits[0].get("payload")
        if isinstance(first_payload, dict):
            top_table = str(first_payload.get("table_key", ""))

        related: list[str] = []
        if top_table:
            graph_result = await graph.get_related_tables(top_table, account, depth=1)
            related = [r.target_table for r in graph_result.relations if r.target_table]

        complexity = self._classify_complexity(query)
        boosted = self._boost_related(vector_hits, related)

        results: list[HybridRankResult] = []
        for hit in boosted[:top_k]:
            payload = hit.get("payload")
            if not isinstance(payload, dict):
                continue
            tk = str(payload.get("table_key", ""))
            if not tk:
                continue
            score = hit.get("score", 0.0)
            results.append(HybridRankResult(
                table_key=tk,
                score=float(score) if isinstance(score, (int | float)) else 0.0,
                complexity=complexity,
                related_tables=related,
            ))
        return results

    def _boost_related(
        self,
        hits: list[dict[str, Any]],
        related: list[str],
    ) -> list[dict[str, Any]]:
        if not related:
            return sorted(hits, key=lambda x: float(x.get("score", 0.0) or 0.0), reverse=True)
        boosted: list[dict[str, Any]] = []
        for hit in hits:
            payload = hit.get("payload", {})
            tk = str(payload.get("table_key", "") if isinstance(payload, dict) else "")
            if tk in related:
                score = hit.get("score", 0.0)
                new_score = float(score) * 1.1 if isinstance(score, (int | float)) else 0.0
                boosted.append({**hit, "score": new_score})
            else:
                boosted.append(hit)
        return sorted(boosted, key=lambda x: float(x.get("score", 0.0) or 0.0), reverse=True)
