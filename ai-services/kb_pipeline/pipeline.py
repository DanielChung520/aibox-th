"""Pipeline orchestrator — composes vectorization and graph extraction."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

from kb_pipeline.arango_ops import ArangoOps
from kb_pipeline.chunker import chunk_text
from kb_pipeline.embedder import Embedder
from kb_pipeline.graph import GraphExtractor
from kb_pipeline.qdrant_ops import Point, QdrantStore

_BINARY_EXTS = {".xlsx", ".xls", ".docx", ".pdf"}
# Maximum chunks to vectorize (Qdrant payload limit ~32MB)
MAX_VECTOR_CHUNKS = 100


def _merge_ontologies(onts: list[dict[str, object]]) -> dict[str, object]:
    seen_entities: dict[str, dict[str, object]] = {}
    seen_props: dict[str, dict[str, object]] = {}

    for ont in onts:
        for ec in cast(list[dict[str, object]], ont.get("entity_classes", [])):
            if (
                isinstance(ec, dict)
                and (name := cast(str, ec.get("name") or ""))
                and name not in seen_entities
            ):
                seen_entities[name] = ec
        for op in cast(list[dict[str, object]], ont.get("object_properties", [])):
            if (
                isinstance(op, dict)
                and (pname := cast(str, op.get("name") or ""))
                and pname not in seen_props
            ):
                seen_props[pname] = op

    return {
        "entity_classes": list(seen_entities.values()),
        "object_properties": list(seen_props.values()),
    }


class VectorizeResult(TypedDict):
    chunks: int
    status: str


class GraphResult(TypedDict):
    entities: int
    relations: int
    status: str


def _is_binary_file(local_path: str) -> bool:
    return Path(local_path).suffix.lower() in _BINARY_EXTS


class Pipeline:
    def __init__(
        self,
        arango: ArangoOps | None = None,
        embedder: Embedder | None = None,
        qdrant: QdrantStore | None = None,
        graph: GraphExtractor | None = None,
    ) -> None:
        self.arango = arango or ArangoOps()
        self.embedder = embedder or Embedder()
        self.qdrant = qdrant or QdrantStore()
        self.graph = graph or GraphExtractor()

    def vectorize(self, file_id: str, local_path: str, root_id: str) -> VectorizeResult:
        self.arango.update_status(file_id, vector_status="processing")
        self.arango.log_event(
            file_id, "vectorize", "start", f"Starting vectorization for {file_id}"
        )
        try:
            raw_text = self.arango.read_file(file_id)
            if raw_text is None:
                chunks_raw = self.arango.read_file_chunks(file_id)
                if chunks_raw:
                    raw_text = " ".join(chunks_raw)
                elif _is_binary_file(local_path):
                    reason = (
                        f"vectorize: binary file ({Path(local_path).suffix}) "
                        f"could not be parsed by read_file"
                    )
                    self.arango.update_status(
                        file_id, vector_status="failed", failed_reason=reason
                    )
                    self.arango.log_event(file_id, "vectorize", "error", reason)
                    return VectorizeResult(chunks=0, status="parse_failed")
                else:
                    raw_text = Path(local_path).read_text(
                        encoding="utf-8", errors="replace"
                    )
            text = raw_text.strip()
            if not text:
                self.arango.update_status(file_id, vector_status="completed")
                self.arango.log_event(
                    file_id, "vectorize", "end", "No content to vectorize"
                )
                return VectorizeResult(chunks=0, status="no_content")

            chunks = chunk_text(text)
            if len(chunks) > MAX_VECTOR_CHUNKS:
                self.arango.log_event(
                    file_id, "vectorize", "step",
                    f"Chunked into {len(chunks)} pieces, limiting to {MAX_VECTOR_CHUNKS} for vectorization"
                )
                chunks = chunks[:MAX_VECTOR_CHUNKS]
            else:
                self.arango.log_event(
                    file_id, "vectorize", "step", f"Chunked into {len(chunks)} pieces"
                )
            embeddings = []
            BATCH_SIZE = 10
            for batch_start in range(0, len(chunks), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(chunks))
                batch = chunks[batch_start:batch_end]
                try:
                    batch_embeddings = self.embedder.embed_batch(batch)
                    for j, emb in enumerate(batch_embeddings):
                        if emb:
                            embeddings.append((batch_start + j, emb))
                except Exception as exc:
                    self.arango.log_event(
                        file_id, "vectorize", "step",
                        f"Batch embedding failed at {batch_start}: {exc}"
                    )
                if batch_start % 20 == 0:
                    self.arango.log_event(
                        file_id,
                        "vectorize",
                        "step",
                        f"Embedded {batch_start + len(batch)}/{len(chunks)} chunks",
                    )

            if not embeddings:
                reason = "vectorize: no embeddings generated (embedding service returned empty)"
                self.arango.update_status(
                    file_id, vector_status="failed", failed_reason=reason
                )
                self.arango.log_event(file_id, "vectorize", "error", reason)
                return VectorizeResult(chunks=0, status="embedding_failed")

            # Count unique successful embeddings
            successful_count = len(embeddings)
            if successful_count == 0:
                reason = "vectorize: no embeddings generated (embedding service returned empty)"
                self.arango.update_status(
                    file_id, vector_status="failed", failed_reason=reason
                )
                self.arango.log_event(file_id, "vectorize", "error", reason)
                return VectorizeResult(chunks=0, status="embedding_failed")

            collection = f"knowledge_{root_id}"
            self.qdrant.ensure_collection(collection)
            import hashlib

            BATCH_SIZE = 100
            total_count = 0
            for batch_start in range(0, len(chunks), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(chunks))
                # Only create points for chunks that have successful embeddings
                batch_points = [
                    Point(
                        id=int(hashlib.md5(f"{file_id}_{idx}".encode()).hexdigest()[:12], 16),
                        vector=emb,
                        file_id=file_id,
                        root_id=root_id,
                        chunk_index=idx,
                        text=chunks[idx][:500],
                        text_full=chunks[idx],
                    )
                    for idx, emb in embeddings
                    if batch_start <= idx < batch_end
                ]
                if batch_points:
                    count = self.qdrant.upsert(collection, batch_points)
                    total_count += count
                if batch_start % 500 == 0:
                    self.arango.log_event(
                        file_id,
                        "vectorize",
                        "step",
                        f"Upserted {batch_start}/{len(chunks)} chunks",
                    )
            count = total_count
            self.arango.update_status(file_id, vector_status="completed")
            self.arango.log_event(
                file_id,
                "vectorize",
                "end",
                f"Completed: {count} vectors indexed in collection '{collection}'",
            )
            return VectorizeResult(chunks=count, status="completed")

        except Exception as exc:
            reason = f"vectorize: {type(exc).__name__}: {exc}"
            self.arango.update_status(
                file_id, vector_status="failed", failed_reason=reason
            )
            self.arango.log_error(file_id, "vectorize", reason, exc)
            return VectorizeResult(chunks=0, status="failed")

    def extract_graph(self, file_id: str, local_path: str) -> GraphResult:
        self.arango.update_status(file_id, graph_status="processing")
        self.arango.log_event(
            file_id, "graph", "start", f"Starting graph extraction for {file_id}"
        )
        try:
            raw_text = self.arango.read_file(file_id)
            if raw_text is None:
                chunks_raw = self.arango.read_file_chunks(file_id)
                if chunks_raw:
                    raw_text = " ".join(chunks_raw)
                elif _is_binary_file(local_path):
                    reason = (
                        f"graph: binary file ({Path(local_path).suffix}) "
                        f"could not be parsed by read_file"
                    )
                    self.arango.update_status(
                        file_id, graph_status="failed", failed_reason=reason
                    )
                    self.arango.log_event(file_id, "graph", "error", reason)
                    return GraphResult(entities=0, relations=0, status="parse_failed")
                else:
                    raw_text = Path(local_path).read_text(
                        encoding="utf-8", errors="replace"
                    )
            text = raw_text.strip()
            if not text:
                self.arango.update_status(file_id, graph_status="completed")
                self.arango.log_event(
                    file_id, "graph", "end", "No content to extract graph from"
                )
                return GraphResult(entities=0, relations=0, status="no_content")

            primary_major: str | None = None
            try:
                file_doc = self.arango.get_file(file_id)
                root_id = file_doc.get("knowledge_root_id") if file_doc else None
                if root_id:
                    root_doc = self.arango.get_root(str(root_id))
                    majors = cast(
                        list[str],
                        root_doc.get("ontology_majors", []) if root_doc else [],
                    )
                    primary_major = majors[0] if majors else None

                self.arango.log_event(
                    file_id,
                    "graph",
                    "step",
                    "Classifying document type and generating summary",
                )
                doc_types, doc_summary = self.graph.classify_and_summarize(text)
                self.arango.update_document_metadata(
                    file_id,
                    document_type=doc_types,
                    document_summary=doc_summary,
                    ontology_major=primary_major,
                )
                self.arango.log_event(
                    file_id,
                    "graph",
                    "step",
                    f"Document type: {doc_types}, summary: {doc_summary[:80]}...",
                )
            except Exception as cls_exc:
                self.arango.log_event(
                    file_id, "graph", "step", f"Classify/summarize failed: {cls_exc}"
                )

            ontology: dict[str, object] | None = None
            try:
                file_doc = self.arango.get_file(file_id)
                root_id = file_doc.get("knowledge_root_id") if file_doc else None
                if root_id:
                    root_doc = self.arango.get_root(str(root_id))
                    majors = cast(
                        list[str],
                        root_doc.get("ontology_majors", []) if root_doc else [],
                    )
                    primary_major = majors[0] if majors else None

                    ontologies_to_merge: list[dict[str, object]] = []
                    domain_name: str | None = None

                    if primary_major:
                        major_ont = self.arango.get_ontology_by_name(primary_major)
                        if major_ont:
                            ontologies_to_merge.append(major_ont)
                            self.arango.log_event(
                                file_id,
                                "graph",
                                "step",
                                f"Loaded major ontology '{primary_major}'",
                            )
                            inherits = cast(
                                list[str], major_ont.get("inherits_from", [])
                            )
                            if inherits:
                                domain_name = inherits[0]

                    if root_doc:
                        domain = cast(str, root_doc.get("ontology_domain") or "")
                        if domain and domain != domain_name:
                            domain_ont = self.arango.get_ontology_by_name(domain)
                            if domain_ont:
                                ontologies_to_merge.append(domain_ont)
                                self.arango.log_event(
                                    file_id,
                                    "graph",
                                    "step",
                                    f"Loaded domain ontology '{domain}'",
                                )

                    basic_ont = self.arango.get_ontology_by_name(
                        "5W1H_Base_Ontology_OWL"
                    )
                    if basic_ont:
                        ontologies_to_merge.append(basic_ont)
                        self.arango.log_event(
                            file_id,
                            "graph",
                            "step",
                            "Loaded basic ontology '5W1H_Base_Ontology_OWL'",
                        )

                    if ontologies_to_merge:
                        ontology = _merge_ontologies(ontologies_to_merge)
                        total_entities = sum(
                            len(cast(list, o.get("entity_classes", [])))
                            for o in ontologies_to_merge
                        )
                        total_props = sum(
                            len(cast(list, o.get("object_properties", [])))
                            for o in ontologies_to_merge
                        )
                        self.arango.log_event(
                            file_id,
                            "graph",
                            "step",
                            f"Merged {len(ontologies_to_merge)} ontology layers ({total_entities} entities, {total_props} properties)",
                        )
            except Exception as log_exc:
                self.arango.log_event(
                    file_id,
                    "graph",
                    "step",
                    f"Could not load ontology (falling back to generic): {log_exc}",
                )

            self.arango.log_event(
                file_id,
                "graph",
                "step",
                f"Calling LLM for entity/relation extraction ({len(text)} chars, parallel chunking enabled)",
            )
            entities, relations = self.graph.extract_chunks(text, ontology)
            self.arango.log_event(
                file_id,
                "graph",
                "step",
                f"LLM returned {len(entities)} entities, {len(relations)} relations",
            )
            if entities or relations:
                self.arango.upsert_graph(file_id, entities, relations)
                self.arango.update_status(file_id, graph_status="completed")
                self.arango.log_event(
                    file_id,
                    "graph",
                    "end",
                    f"Completed: {len(entities)} entities, {len(relations)} relations stored",
                )
                return GraphResult(
                    entities=len(entities),
                    relations=len(relations),
                    status="completed",
                )

            reason = "graph: LLM returned 0 entities and 0 relations"
            self.arango.update_status(
                file_id, graph_status="failed", failed_reason=reason
            )
            self.arango.log_event(file_id, "graph", "error", reason)
            return GraphResult(entities=0, relations=0, status="failed")

        except Exception as exc:
            reason = f"graph: {type(exc).__name__}: {exc}"
            self.arango.update_status(
                file_id, graph_status="failed", failed_reason=reason
            )
            self.arango.log_error(file_id, "graph", reason, exc)
            return GraphResult(entities=0, relations=0, status="failed")
