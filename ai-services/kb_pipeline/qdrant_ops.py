"""Qdrant vector store operations."""

import os
from dataclasses import dataclass
from typing import cast

import httpx

_EMBEDDING_DIM: int | None = None


def _get_embedding_dim() -> int:
    global _EMBEDDING_DIM
    if _EMBEDDING_DIM is not None:
        return _EMBEDDING_DIM
    from kb_pipeline.arango_ops import ArangoOps
    from kb_pipeline.embedder import Embedder

    arango = ArangoOps()
    embedder = Embedder()
    model = embedder.model
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/v1/embeddings",
                json={"model": model, "input": "dim"},
            )
            resp.raise_for_status()
            embeddings = resp.json().get("embeddings", [])
            if embeddings and embeddings[0]:
                _EMBEDDING_DIM = len(embeddings[0])
                return _EMBEDDING_DIM
    except Exception:
        pass
    _EMBEDDING_DIM = 4096
    return _EMBEDDING_DIM


@dataclass
class Point:
    id: int
    vector: list[float]
    file_id: str
    root_id: str
    chunk_index: int
    text: str
    text_full: str


class QdrantStore:
    def __init__(self, url: str | None = None, timeout: float = 60.0) -> None:
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout)

    def ensure_collection(self, name: str) -> None:
        with self._client() as client:
            resp = client.get(f"{self.url}/collections/{name}")
            if resp.status_code == 200:
                return
            dim = _get_embedding_dim()
            client.put(
                f"{self.url}/collections/{name}",
                json={
                    "vectors": {"size": dim, "distance": "Cosine"},
                    "optimizers_config": {"indexing_threshold": 10000},
                },
            )

    def upsert(self, collection: str, points: list[Point]) -> int:
        if not points:
            return 0
        payload = {
            "points": [
                {
                    "id": p.id,
                    "vector": p.vector,
                    "payload": {
                        "file_id": p.file_id,
                        "root_id": p.root_id,
                        "chunk_index": p.chunk_index,
                        "text": p.text[:500],
                        "text_full": p.text_full,
                    },
                }
                for p in points
            ]
        }
        with self._client() as client:
            resp = client.put(
                f"{self.url}/collections/{collection}/points", json=payload
            )
            if resp.status_code >= 400:
                raise Exception(f"Qdrant upsert failed: {resp.status_code} {resp.text}")
            result = resp.json()
            op_status = result.get("result", {}).get("status", "")
            if op_status not in ("acknowledged", "completed"):
                raise Exception(f"Qdrant upsert status={op_status}: {resp.text}")
        return len(points)

    def search(
        self, collection: str, vector: list[float], limit: int = 5
    ) -> list[dict[str, object]]:
        with self._client() as client:
            resp = client.post(
                f"{self.url}/collections/{collection}/points/search",
                json={"vector": vector, "limit": limit, "with_payload": True},
            )
            resp.raise_for_status()
            result_data = resp.json().get("result")
            return list(result_data) if result_data else []

    def get_chunks(
        self, collection: str, file_id: str, limit: int = 50, offset: int = 0
    ) -> list[dict[str, object]]:
        with self._client() as client:
            resp = client.post(
                f"{self.url}/collections/{collection}/points/scroll",
                json={
                    "filter": {
                        "must": [
                            {"key": "file_id", "match": {"value": file_id}}
                        ]
                    },
                    "limit": limit,
                    "offset": offset,
                    "with_payload": True,
                },
            )
            if resp.status_code >= 400:
                return []
            raw = resp.json()
            result = cast(dict[str, object], raw.get("result", {}) if isinstance(raw, dict) else {})
            points = cast(list[dict[str, object]], result.get("points", []) or [])
            chunks: list[dict[str, object]] = []
            for point in points:
                pld = cast(dict[str, object], point.get("payload") or {})
                chunks.append({
                    "chunk_id": str(point.get("id", "")),
                    "text": str(pld.get("text_full") or pld.get("text") or ""),
                    "chunk_index": cast(int, pld.get("chunk_index") or 0),
                    "score": 1.0,
                })
            chunks.sort(key=lambda x: cast(int, x["chunk_index"]))
            return chunks

    def count(self, collection: str) -> int:
        with self._client() as client:
            resp = client.post(
                f"{self.url}/collections/{collection}/points/count", json={}
            )
            if resp.status_code == 200:
                result: dict[str, object] = resp.json().get("result", {})
                raw_count = result.get("count", 0)
                if isinstance(raw_count, (int, float)):
                    return int(raw_count)
            return 0

    def recommend(
        self, collection: str, positive_id: int, limit: int = 10, score_threshold: float | None = None
    ) -> list[dict[str, object]]:
        body: dict[str, object] = {
            "positive": [positive_id],
            "limit": limit,
            "with_payload": True,
        }
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        with self._client() as client:
            resp = client.post(
                f"{self.url}/collections/{collection}/points/recommend", json=body
            )
            if resp.status_code >= 400:
                raise Exception(f"Qdrant recommend failed: {resp.status_code} {resp.text}")
            result_data = resp.json().get("result")
            return list(result_data) if result_data else []

    def delete_by_file(self, collection: str, file_id: str) -> int:
        """Delete all points matching file_id from collection."""
        with self._client() as client:
            resp = client.post(
                f"{self.url}/collections/{collection}/points/delete",
                json={
                    "filter": {
                        "must": [
                            {"key": "file_id", "match": {"value": file_id}}
                        ]
                    }
                },
            )
            if resp.status_code >= 400:
                raise Exception(
                    f"Qdrant delete failed: {resp.status_code} {resp.text}"
                )
        return 0
