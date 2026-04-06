"""
Knowledge graph extraction using LLM.

@lastUpdate  2026-04-04 10:45:00
@author      Daniel Chung
@version     1.5.0
"""

from __future__ import annotations

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

import httpx

logger = logging.getLogger(__name__)

# Chunk size for graph extraction (per LLM call)
_CHUNK_SIZE = 3000
# Maximum chunks to process in parallel (avoid overwhelming LLM)
_MAX_PARALLEL_CHUNKS = 5


def _sanitize_llm_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]
    elif brace_start != -1:
        text = _repair_truncated_json(text[brace_start:])
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _repair_truncated_json(text: str) -> str:
    bracket_end = text.rfind("]")
    if bracket_end == -1:
        return text
    text = text[: bracket_end + 1]
    last_complete = text.rfind("}")
    if last_complete != -1:
        after = text[last_complete + 1 : bracket_end].strip().rstrip(",").strip()
        if after:
            text = text[: last_complete + 1] + text[bracket_end:]
    open_brackets = text.count("[") - text.count("]")
    text += "]" * max(0, open_brackets)
    open_braces = text.count("{") - text.count("}")
    text += "}" * max(0, open_braces)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _build_ontology_section(ontology: dict[str, object]) -> str:
    entity_classes = cast(list[dict[str, object]], ontology.get("entity_classes", []))
    object_properties = cast(
        list[dict[str, object]], ontology.get("object_properties", [])
    )

    if not entity_classes and not object_properties:
        return ""

    lines = ["\n\n【知識本體 schema】（請優先使用以下類型抽取）："]
    lines.append("\n## 實體類別（Entity Types）：")
    for ec in entity_classes:
        name = ec.get("name", "")
        base_class = ec.get("base_class", "")
        description = ec.get("description", "")
        lines.append(f"- [{name}]  基礎類別：{base_class}  說明：{description}")

    if object_properties:
        lines.append("\n## 物件屬性（Object Properties）：")
        for op in object_properties:
            name = op.get("name", "")
            domain = op.get("domain", [])
            rng = op.get("range", [])
            description = op.get("description", "")
            domain_list = cast(list[str], domain)
            range_list = cast(list[str], rng)
            lines.append(
                f"- {name}  來源：{', '.join(domain_list)}  →  目標：{', '.join(range_list)}"
                + (f"  說明：{description}" if description else "")
            )

    return "\n".join(lines)


class GraphExtractor:
    def _get_model(self) -> str:
        from kb_pipeline.arango_ops import ArangoOps

        arango = ArangoOps()
        db_model = arango.get_system_param("knowledge.graph_model")
        if db_model:
            return db_model
        return os.getenv("OLLAMA_LLM_MODEL", "llama3.2:latest")

    def _get_num_predict(self) -> int:
        from kb_pipeline.arango_ops import ArangoOps

        arango = ArangoOps()
        val = arango.get_system_param("knowledge.graph_num_predict")
        if val:
            try:
                return int(val)
            except ValueError:
                pass
        return 8192

    BASE_PROMPT = """你是一個知識圖譜提取專家。請從以下文本中提取實體和關係。

文本：
{text}

請以JSON格式返回，結構如下（只返回JSON，不要任何其他文字）：
{{
  "entities": [
    {{"entity": "實體名稱", "entity_type": "人物|組織|概念|技術|地點|事件", "description": "簡短描述"}}
  ],
  "relations": [
    {{"source": "實體A名稱", "target": "實體B名稱", "relation": "關係描述"}}
  ]
}}

規則：
- 只提取與文本內容直接相關的實體
- 實體類型必須是上述類型之一
- 關係應反映實體之間的實際聯繫
- entities 和 relations 都可以為空陣列
"""

    def _build_prompt(
        self, text: str, ontology: dict[str, object] | None = None
    ) -> str:
        base = self.BASE_PROMPT.format(text=text[:3000])
        if ontology:
            ont_section = _build_ontology_section(ontology)
            if ont_section:
                base = (
                    "你是一個知識圖譜提取專家。請從以下文本中提取實體和關係。\n\n"
                    + "請充分利用【知識本體 schema】中的實體類別和物件屬性來指導抽取。\n"
                    + "entity_type 欄位優先使用 schema 中的 base_class（如 Concept、Document、Process 等）。\n"
                    + "relation 欄位優先使用 schema 中的屬性名稱。\n"
                    + ont_section
                    + f"\n\n文本：\n{text[:3000]}\n\n"
                    + "請以JSON格式返回，結構如下（只返回JSON，不要任何其他文字）：\n"
                    + '{\n  "entities": [\n'
                    + '    {"entity": "實體名稱", "entity_type": "實體類型", "description": "簡短描述"}\n'
                    + "  ],\n"
                    + '  "relations": [\n'
                    + '    {"source": "實體A名稱", "target": "實體B名稱", "relation": "關係名稱"}\n'
                    + "  ]\n}\n\n"
                    + "規則：\n"
                    + "- 優先使用 schema 中定義的實體類型和屬性名稱\n"
                    + "- entity_type 必須是 base_class 之一（Concept/Document/Process/Agent/Requirement/Tool/Event/Metadata）\n"
                    + "- 當文本內容符合 schema 中的實體描述時，應抽取為對應類型\n"
                    + "- 當關係符合 schema 中的物件屬性時，使用該屬性名稱作為 relation\n"
                    + "- 關係不存在於 schema 時，可自行根據文本推斷合理的關係描述\n"
                    + "- entities 和 relations 都可以為空陣列\n"
                )
        return base

    def _split_text_into_chunks(
        self, text: str, chunk_size: int = _CHUNK_SIZE
    ) -> list[str]:
        """Split text into overlapping chunks to avoid cutting mid-sentence.

        Chunks have 200-character overlap to ensure entities spanning chunk
        boundaries are not lost.
        """
        overlap = 200
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end < text_len:
                cutoff = text.rfind("。", start + chunk_size - 50, end + 50)
                if cutoff > start + chunk_size // 2:
                    end = cutoff + 1
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap if end < text_len else text_len

        return chunks

    def _extract_single_chunk(
        self,
        chunk: str,
        chunk_index: int,
        total_chunks: int,
        ontology: dict[str, object] | None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Extract entities/relations from a single chunk."""
        prompt = self._build_prompt(chunk, ontology)
        num_predict = self._get_num_predict()

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": num_predict},
                },
            )
            response.raise_for_status()
            result_text = response.json().get("response", "").strip()

        if not result_text:
            logger.warning(
                "Chunk %d/%d: LLM returned empty response",
                chunk_index + 1,
                total_chunks,
            )
            return [], []

        sanitized = _sanitize_llm_json(result_text)
        parsed: dict[str, object] = json.loads(sanitized)
        raw_entities = parsed.get("entities", [])
        raw_relations = parsed.get("relations", [])
        entities = (
            cast(list[dict[str, object]], raw_entities)
            if isinstance(raw_entities, list)
            else []
        )
        relations = (
            cast(list[dict[str, object]], raw_relations)
            if isinstance(raw_relations, list)
            else []
        )

        logger.debug(
            "Chunk %d/%d: extracted %d entities, %d relations",
            chunk_index + 1,
            total_chunks,
            len(entities),
            len(relations),
        )

        return entities, relations

    def extract_chunks(
        self,
        text: str,
        ontology: dict[str, object] | None = None,
        max_parallel: int = _MAX_PARALLEL_CHUNKS,
        max_chunks: int = 50,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Extract entities and relations from text by processing chunks in parallel.

        This method splits the input text into chunks, processes them concurrently
        using multiple LLM calls, then merges and deduplicates the results.

        Args:
            text: Full source document text to extract from.
            ontology: Optional ontology schema to guide extraction.
            max_parallel: Maximum number of chunks to process concurrently (default 5).
            max_chunks: Maximum number of chunks to process (default 50). For large
                documents, processing more chunks increases coverage but also processing
                time and LLM API calls. A value of 50 provides good coverage while
                keeping processing time reasonable.

        Returns:
            Tuple of (entities list, relations list) with duplicates removed.
        """
        chunks = self._split_text_into_chunks(text)
        if not chunks:
            return [], []

        logger.info(
            "Processing %d chunks for graph extraction (parallel=%d)",
            len(chunks),
            min(max_parallel, len(chunks)),
        )

        all_entities: list[dict[str, object]] = []
        all_relations: list[dict[str, object]] = []

        with ThreadPoolExecutor(max_workers=max_parallel) as executor:
            futures = {
                executor.submit(
                    self._extract_single_chunk,
                    chunk,
                    i,
                    len(chunks),
                    ontology,
                ): i
                for i, chunk in enumerate(chunks[:max_chunks])
            }

            for future in as_completed(futures):
                chunk_idx = futures[future]
                try:
                    entities, relations = future.result()
                    all_entities.extend(entities)
                    all_relations.extend(relations)
                except Exception as exc:
                    logger.error(
                        "Chunk %d/%d extraction failed: %s",
                        chunk_idx + 1,
                        len(chunks),
                        exc,
                    )

        merged_entities = self._deduplicate_entities(all_entities)
        merged_relations = self._deduplicate_relations(all_relations, merged_entities)

        chunks_processed = min(len(chunks), max_chunks)
        logger.info(
            "Graph extraction complete: %d unique entities, %d unique relations from %d/%d chunks",
            len(merged_entities),
            len(merged_relations),
            chunks_processed,
            len(chunks),
        )

        return merged_entities, merged_relations

    def _deduplicate_entities(
        self, entities: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Deduplicate entities by name (case-insensitive)."""
        seen: dict[str, dict[str, object]] = {}
        for ent in entities:
            name = str(ent.get("entity", "")).strip()
            if not name:
                continue
            key = name.lower()
            if key not in seen:
                seen[key] = ent
            else:
                existing = seen[key]
                if not existing.get("description") and ent.get("description"):
                    existing["description"] = ent["description"]
                if not existing.get("entity_type") and ent.get("entity_type"):
                    existing["entity_type"] = ent["entity_type"]
        return list(seen.values())

    def _deduplicate_relations(
        self,
        relations: list[dict[str, object]],
        entities: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Deduplicate relations, normalizing entity names to match deduped entities."""
        entity_names: set[str] = {
            str(e.get("entity", "")).strip().lower() for e in entities
        }

        seen: dict[str, dict[str, object]] = {}
        for rel in relations:
            src = str(rel.get("source", "")).strip()
            tgt = str(rel.get("target", "")).strip()
            rel_text = str(rel.get("relation", "")).strip()
            if not src or not tgt or not rel_text:
                continue
            key = f"{src.lower()}::{tgt.lower()}::{rel_text.lower()}"
            if key not in seen:
                src_norm = self._normalize_entity_name(src, entity_names) or src
                tgt_norm = self._normalize_entity_name(tgt, entity_names) or tgt
                seen[key] = {
                    "source": src_norm,
                    "target": tgt_norm,
                    "relation": rel_text,
                }
        return list(seen.values())

    def _normalize_entity_name(self, name: str, entity_names: set[str]) -> str | None:
        """Find matching entity name from deduped set (case-insensitive)."""
        name_lower = name.strip().lower()
        if name_lower in entity_names:
            for e in entity_names:
                if e == name_lower:
                    return next((en for en in entity_names if en == name_lower), name)
        return None

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.ollama_url = ollama_url or os.getenv(
            "OLLAMA_BASE_URL", "http://localhost:11434"
        )
        self.timeout = timeout
        self._model = model or self._get_model()

    @property
    def model(self) -> str:
        return self._model

    def extract(
        self,
        text: str,
        ontology: dict[str, object] | None = None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Extract entities and relations from text via LLM.

        Args:
            text: Source document text to extract from.
            ontology: Optional ontology schema (from ontologies collection) to guide extraction.
                When provided, the extraction prompt will include entity_classes and
                object_properties to improve type consistency.

        Returns:
            Tuple of (entities list, relations list).

        Raises:
            ValueError: If LLM returns empty or unparseable response.
        """
        prompt = self._build_prompt(text, ontology)
        num_predict = self._get_num_predict()
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": num_predict},
                },
            )
            response.raise_for_status()
            result_text = response.json().get("response", "").strip()
        if not result_text:
            raise ValueError("LLM returned empty response")
        sanitized = _sanitize_llm_json(result_text)
        parsed: dict[str, object] = json.loads(sanitized)
        entities = parsed.get("entities", [])
        relations = parsed.get("relations", [])
        return (
            list(entities) if isinstance(entities, list) else [],
            list(relations) if isinstance(relations, list) else [],
        )

    def classify_and_summarize(self, text: str) -> tuple[list[str], str]:
        """Classify document type(s) and generate a summary.

        Returns:
            Tuple of (document_types list, summary string).
        """
        prompt = (
            "你是一個文件分析專家。請分析以下文件，輸出 JSON 格式：\n\n"
            '{\n  "document_types": ["類型1", "類型2", ...],\n  "summary": "50-200字的簡短摘要"\n}\n\n'
            "可選文件類型：流程文件、會議記錄、工程文件、廣告宣傳、政策規範、產品規格、財務報告、需求提案、技術架構、操作手冊、測試報告、其它\n\n"
            "document_types 最多選 3 個，summary 必須是中文且不超過 200 字。\n"
            "只返回 JSON，不要任何其他文字。\n\n"
            f"文件內容：\n{text[:4000]}"
        )
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 1024},
                },
            )
            response.raise_for_status()
            result_text = response.json().get("response", "").strip()

        if not result_text:
            return (["其它"], "")

        try:
            sanitized = _sanitize_llm_json(result_text)
            parsed: dict[str, object] = json.loads(sanitized)
            types = parsed.get("document_types", [])
            summary = str(parsed.get("summary", ""))
            valid_types = list(types) if isinstance(types, list) else []
            return (valid_types if valid_types else ["其它"], summary)
        except (json.JSONDecodeError, ValueError):
            return (["其它"], "")
