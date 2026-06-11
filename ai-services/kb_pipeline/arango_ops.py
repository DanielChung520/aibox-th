"""ArangoDB operations for knowledge base files."""

import logging
import os
import traceback as tb_module
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

ARANGO_URL = os.getenv("ARANGO_URL", "http://localhost:8529")
ARANGO_DB = os.getenv("ARANGO_DATABASE", "abc_desktop")
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD", "")


class ArangoOps:
    def __init__(
        self,
        url: str | None = None,
        db: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.url = url or ARANGO_URL
        self.db = db or ARANGO_DB
        self.user = user or ARANGO_USER
        self.password = password or ARANGO_PASSWORD
        self.auth = (self.user, self.password)

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=30.0, auth=self.auth)

    def read_file(self, file_id: str) -> str | None:
        with self._client() as client:
            doc_resp = client.get(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_files/{file_id}"
            )
            if doc_resp.status_code not in (200, 201):
                return None
            doc = doc_resp.json()
            local_path = doc.get("local_path")
            if not local_path:
                return None

            if local_path.startswith("http://") or local_path.startswith("https://"):
                try:
                    file_resp = client.get(local_path, timeout=60.0)
                    if file_resp.status_code != 200:
                        return None
                    content = file_resp.content
                except Exception:
                    return None
            elif Path(local_path).exists():
                content = Path(local_path).read_bytes()
            else:
                return None

            ext = local_path.rsplit(".", 1)[-1].lower() if "." in local_path else ""
            if ext == "pdf":
                try:
                    import io

                    import pdfplumber

                    with pdfplumber.open(io.BytesIO(content)) as pdf:
                        pages: list[str] = []
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text:
                                pages.append(text)
                        return "\n\n".join(pages) if pages else ""
                except Exception:
                    logger.exception("Failed to parse PDF: %s", file_id)
                    return None

            if ext in ("xlsx", "xls"):
                try:
                    import io

                    import openpyxl

                    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
                    parts: list[str] = []
                    for ws in wb.worksheets:
                        for row in ws.iter_rows(values_only=True):
                            cells = [str(c) if c is not None else "" for c in row]
                            line = " | ".join(cells).strip()
                            if line:
                                parts.append(line)
                    return "\n".join(parts) if parts else ""
                except Exception:
                    logger.exception("Failed to parse Excel: %s", file_id)
                    return None

            if ext == "docx":
                try:
                    import io

                    import docx

                    doc = docx.Document(io.BytesIO(content))
                    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
                    for table in doc.tables[:50]:
                        rows = []
                        for row in table.rows:
                            cells = [cell.text.strip() for cell in row.cells]
                            line = " | ".join(cells).strip()
                            if line:
                                rows.append(line)
                        if rows:
                            parts.append("\n".join(rows))
                    return "\n".join(parts) if parts else ""
                except Exception:
                    logger.exception("Failed to parse DOCX: %s", file_id)
                    return None

            if ext == "csv":
                try:
                    import io

                    import csv

                    decoded = content.decode("utf-8", errors="replace")
                    reader = csv.reader(io.StringIO(decoded))
                    parts = [" | ".join(row) for row in reader if row]
                    return "\n".join(parts) if parts else ""
                except Exception:
                    logger.exception("Failed to parse CSV: %s", file_id)
                    return None

            try:
                return content.decode("utf-8", errors="replace")
            except Exception:
                return None

    def read_file_chunks(self, file_id: str) -> list[str]:
        with self._client() as client:
            resp = client.post(
                f"{self.url}/_db/{self.db}/_api/cursor",
                json={
                    "query": """
                        FOR d IN knowledge_chunks
                        FILTER d.file_id == @file_id
                        SORT d.chunk_index
                        RETURN d.text
                    """,
                    "bindVars": {"file_id": file_id},
                },
            )
            if resp.status_code in (200, 201):
                result: list[str] = resp.json().get("result", [])
                return result
            return []

    def update_status(
        self,
        file_id: str,
        vector_status: str | None = None,
        graph_status: str | None = None,
        failed_reason: str | None = None,
    ) -> None:
        patch: dict[str, object] = {}
        if vector_status is not None:
            patch["vector_status"] = vector_status
        if graph_status is not None:
            patch["graph_status"] = graph_status
        if failed_reason is not None:
            patch["failed_reason"] = failed_reason
        if not patch:
            return
        with self._client() as client:
            client.patch(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_files/{file_id}",
                json=patch,
            )

    def update_document_metadata(
        self,
        file_id: str,
        document_type: list[str] | None = None,
        document_summary: str | None = None,
        ontology_major: str | None = None,
    ) -> None:
        patch: dict[str, object] = {}
        if document_type is not None:
            patch["document_type"] = document_type
        if document_summary is not None:
            patch["document_summary"] = document_summary
        if ontology_major is not None:
            patch["ontology_major"] = ontology_major
        if not patch:
            return
        with self._client() as client:
            client.patch(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_files/{file_id}",
                json=patch,
            )

    def set_task_id(
        self,
        file_id: str,
        vector_task_id: str | None = None,
        graph_task_id: str | None = None,
    ) -> None:
        patch: dict[str, object] = {}
        if vector_task_id is not None:
            patch["vector_task_id"] = vector_task_id
        if graph_task_id is not None:
            patch["graph_task_id"] = graph_task_id
        if not patch:
            return
        with self._client() as client:
            client.patch(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_files/{file_id}",
                json=patch,
            )

    def get_file(self, file_id: str) -> dict[str, object] | None:
        with self._client() as client:
            resp = client.get(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_files/{file_id}"
            )
            if resp.status_code == 200:
                return dict(resp.json())
            return None

    def get_root(self, root_id: str) -> dict[str, object] | None:
        with self._client() as client:
            resp = client.get(
                f"{self.url}/_db/{self.db}/_api/document/knowledge_roots/{root_id}"
            )
            if resp.status_code == 200:
                return dict(resp.json())
            return None

    def get_ontology(self, ontology_name: str) -> dict[str, object] | None:
        with self._client() as client:
            resp = client.get(
                f"{self.url}/_db/{self.db}/_api/document/ontologies/{ontology_name}"
            )
            if resp.status_code == 200:
                return dict(resp.json())
            return None

    def get_ontology_by_name(self, name: str) -> dict[str, object] | None:
        with self._client() as client:
            cursor_resp = client.post(
                f"{self.url}/_db/{self.db}/_api/cursor",
                json={
                    "query": "FOR o IN ontologies FILTER o.name == @name LIMIT 1 RETURN o",
                    "bindVars": {"name": name},
                },
            )
            if cursor_resp.status_code == 201:
                result = cursor_resp.json().get("result", [])
                if result:
                    return dict(result[0])
            return None

    def get_system_param(self, key: str) -> str | None:
        with self._client() as client:
            resp = client.get(
                f"{self.url}/_db/{self.db}/_api/document/system_params/{key}"
            )
            if resp.status_code == 200:
                return str(resp.json().get("param_value", ""))
            return None

    def ensure_graph_collections(self) -> None:
        with self._client() as client:
            for name, edge_type in [
                ("knowledge_graphs", 3),
                ("knowledge_graph_edges", 2),
            ]:
                resp = client.get(f"{self.url}/_db/{self.db}/_api/collection/{name}")
                if resp.status_code == 404:
                    client.post(
                        f"{self.url}/_db/{self.db}/_api/collection",
                        json={"name": name, "type": edge_type},
                    )

    def upsert_graph(
        self,
        file_id: str,
        nodes: list[dict[str, object]],
        edges: list[dict[str, object]],
        root_id: str | None = None,
    ) -> None:
        self.ensure_graph_collections()
        nodes_data = [
            {
                "_key": f"{file_id}_node_{i}",
                "file_id": file_id,
                "root_id": root_id,
                "entity": n["entity"],
                "entity_type": n.get("entity_type", "concept"),
                "description": n.get("description", ""),
            }
            for i, n in enumerate(nodes)
        ]
        # Case-insensitive entity index for matching relations
        entity_index_lower: dict[str, int] = {
            str(n["entity"]).strip().lower(): i for i, n in enumerate(nodes)
        }
        edges_data = []
        skipped_edges = 0
        for i, e in enumerate(edges):
            src_raw = str(e["source"]).strip()
            tgt_raw = str(e["target"]).strip()
            src_idx = entity_index_lower.get(
                src_raw.lower(), int(src_raw) if src_raw.isdigit() else -1
            )
            tgt_idx = entity_index_lower.get(
                tgt_raw.lower(), int(tgt_raw) if tgt_raw.isdigit() else -1
            )
            if (
                src_idx < 0
                or tgt_idx < 0
                or src_idx >= len(nodes)
                or tgt_idx >= len(nodes)
            ):
                skipped_edges += 1
                continue
            edges_data.append(
                {
                    "_key": f"{file_id}_edge_{i}",
                    "_from": f"knowledge_graphs/{file_id}_node_{src_idx}",
                    "_to": f"knowledge_graphs/{file_id}_node_{tgt_idx}",
                    "file_id": file_id,
                    "root_id": root_id,
                    "relation": e.get("relation", "related_to"),
                    "source": f"{file_id}_node_{src_idx}",
                    "target": f"{file_id}_node_{tgt_idx}",
                }
            )
        with self._client() as client:
            for node in nodes_data:
                resp = client.post(
                    f"{self.url}/_db/{self.db}/_api/document/knowledge_graphs",
                    json=node,
                )
                if resp.status_code not in (200, 201, 202, 409):
                    raise RuntimeError(
                        f"Failed to insert node {node['_key']}: "
                        f"{resp.status_code} {resp.text}"
                    )
            for edge in edges_data:
                aql_resp = client.post(
                    f"{self.url}/_db/{self.db}/_api/cursor",
                    json={
                        "query": """
                            INSERT {
                                _key: @key,
                                _from: @from,
                                _to: @to,
                                file_id: @file_id,
                                relation: @relation,
                                source: @source,
                                target: @target
                            } INTO knowledge_graph_edges
                            OPTIONS { ignoreErrors: true }
                        """,
                        "bindVars": {
                            "key": edge["_key"],
                            "from": edge["_from"],
                            "to": edge["_to"],
                            "file_id": edge["file_id"],
                            "relation": edge["relation"],
                            "source": edge["source"],
                            "target": edge["target"],
                        },
                    },
                )
                if aql_resp.status_code not in (200, 201):
                    raise RuntimeError(
                        f"Failed to insert edge {edge['_key']}: "
                        f"{aql_resp.status_code} {aql_resp.text}"
                    )
        if skipped_edges > 0:
            logger.warning(
                "upsert_graph: skipped %d/%d edges due to unmatched entity names",
                skipped_edges,
                len(edges),
            )

    def ensure_job_logs_collection(self) -> None:
        with self._client() as client:
            resp = client.get(f"{self.url}/_db/{self.db}/_api/collection/job_logs")
            if resp.status_code == 404:
                client.post(
                    f"{self.url}/_db/{self.db}/_api/collection",
                    json={"name": "job_logs"},
                )

    def log_event(
        self,
        file_id: str,
        task_type: str,
        event: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.ensure_job_logs_collection()
        doc: dict[str, object] = {
            "file_id": file_id,
            "task_type": task_type,
            "event": event,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if detail:
            doc["detail"] = detail
        with self._client() as client:
            client.post(
                f"{self.url}/_db/{self.db}/_api/document/job_logs",
                json=doc,
            )

    def log_error(
        self,
        file_id: str,
        task_type: str,
        message: str,
        exc: BaseException,
    ) -> None:
        self.log_event(
            file_id=file_id,
            task_type=task_type,
            event="error",
            message=message,
            detail=tb_module.format_exc(),
        )

    def get_job_logs(self, file_id: str) -> list[dict[str, object]]:
        with self._client() as client:
            resp = client.post(
                f"{self.url}/_db/{self.db}/_api/cursor",
                json={
                    "query": """
                        FOR log IN job_logs
                        FILTER log.file_id == @file_id
                        SORT log.timestamp ASC
                        RETURN log
                    """,
                    "bindVars": {"file_id": file_id},
                },
            )
            if resp.status_code in (200, 201):
                return resp.json().get("result", [])
            return []

    def get_graph(self, file_id: str) -> dict[str, object]:
        with self._client() as client:
            # Fetch nodes from knowledge_graphs collection
            nodes_resp = client.post(
                f"{self.url}/_db/{self.db}/_api/cursor",
                json={
                    "query": "FOR n IN knowledge_graphs FILTER n.file_id == @file_id RETURN n",
                    "bindVars": {"file_id": file_id},
                },
            )
            raw_nodes: list[dict[str, object]] = []
            if nodes_resp.status_code in (200, 201):
                raw_nodes = nodes_resp.json().get("result", [])

            # Fetch edges from knowledge_graph_edges collection
            edges_resp = client.post(
                f"{self.url}/_db/{self.db}/_api/cursor",
                json={
                    "query": "FOR e IN knowledge_graph_edges FILTER e.file_id == @file_id RETURN e",
                    "bindVars": {"file_id": file_id},
                },
            )
            raw_edges: list[dict[str, object]] = []
            if edges_resp.status_code in (200, 201):
                raw_edges = edges_resp.json().get("result", [])

        nodes: list[dict[str, object]] = []
        node_id_map: dict[int, str] = {}
        for i, n in enumerate(raw_nodes):
            node_id_map[i] = str(n.get("_key", f"node_{i}"))
            nodes.append(
                {
                    "id": node_id_map[i],
                    "label": str(n.get("entity", "unknown")),
                    "type": str(n.get("entity_type", "concept")),
                    "properties": {
                        "description": str(n.get("description", "")),
                    },
                }
            )

        edges: list[dict[str, object]] = []
        for e in raw_edges:
            src_node_id = str(e.get("source", ""))
            tgt_node_id = str(e.get("target", ""))
            if src_node_id and tgt_node_id:
                edges.append(
                    {
                        "source": src_node_id,
                        "target": tgt_node_id,
                        "label": str(e.get("relation", "related_to")),
                    }
                )

        return {"nodes": nodes, "edges": edges}

    def delete_file_data(self, file_id: str) -> dict[str, int]:
        removed: dict[str, int] = {}
        collections = [
            "knowledge_chunks",
            "knowledge_graphs",
            "knowledge_graph_edges",
            "job_logs",
        ]
        with self._client() as client:
            for col in collections:
                resp = client.post(
                    f"{self.url}/_db/{self.db}/_api/cursor",
                    json={
                        "query": f"FOR d IN {col} FILTER d.file_id == @fid REMOVE d IN {col} RETURN 1",
                        "bindVars": {"fid": file_id},
                    },
                )
                count = 0
                if resp.status_code in (200, 201):
                    count = len(resp.json().get("result", []))
                removed[col] = count
        return removed
