"""
@file        result_merger.py
@description Merge results from multi-step Ragic queries.
             Provides FK-based join and simple concatenation strategies.
@lastUpdate  2026-04-11 17:26:16
@author      Daniel Chung
@version     1.0.0
"""

from __future__ import annotations

import logging

from data_agent.ragic.models_phase9 import GraphRelation, StepResult

logger = logging.getLogger(__name__)


class ResultMerger:

    def merge(
        self,
        steps: list[StepResult],
        relations: list[GraphRelation],
    ) -> list[dict[str, object]]:
        """Join step results using FK relationships from the knowledge graph.

        For single step: returns records with table-prefixed keys.
        For multi-step: matches records across steps using FK field values.
        Steps with errors are skipped.
        """
        valid_steps = [s for s in steps if s.error is None and s.records]
        if not valid_steps:
            return []
        if len(valid_steps) == 1:
            return self._prefix_records(valid_steps[0])

        rel_map = self._build_relation_map(relations)
        primary = valid_steps[0]
        merged: list[dict[str, object]] = []

        for rec in primary.records:
            row: dict[str, object] = self._prefix_single(primary.table_name, rec)
            for dep_step in valid_steps[1:]:
                fk_info = rel_map.get(
                    (primary.table_name, dep_step.table_name)
                )
                if fk_info is None:
                    continue
                src_field, tgt_field = fk_info
                src_val = rec.get(src_field)
                matched = self._find_match(
                    dep_step.records, tgt_field, src_val
                )
                if matched:
                    row.update(
                        self._prefix_single(dep_step.table_name, matched)
                    )
            merged.append(row)

        return merged

    def merge_simple(
        self, steps: list[StepResult]
    ) -> list[dict[str, object]]:
        """Concatenate records from all steps without FK joining.

        Each record gets a `_source_table` field indicating origin.
        Steps with errors are skipped.
        """
        result: list[dict[str, object]] = []
        for step in steps:
            if step.error is not None:
                continue
            for rec in step.records:
                row: dict[str, object] = {"_source_table": step.table_name}
                row.update(rec)
                result.append(row)
        return result

    @staticmethod
    def _prefix_records(step: StepResult) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for rec in step.records:
            prefixed: dict[str, object] = {
                f"{step.table_name}.{k}": v for k, v in rec.items()
            }
            out.append(prefixed)
        return out

    @staticmethod
    def _prefix_single(
        table_name: str, rec: dict[str, object]
    ) -> dict[str, object]:
        return {f"{table_name}.{k}": v for k, v in rec.items()}

    @staticmethod
    def _build_relation_map(
        relations: list[GraphRelation],
    ) -> dict[tuple[str, str], tuple[str, str]]:
        rel_map: dict[tuple[str, str], tuple[str, str]] = {}
        for rel in relations:
            key = (rel.source_field, rel.target_table)
            rel_map[(rel.source_field, rel.target_table)] = (
                rel.source_field,
                rel.target_field,
            )
            for variant in [key]:
                if variant not in rel_map:
                    rel_map[variant] = (
                        rel.source_field,
                        rel.target_field,
                    )
        return rel_map

    @staticmethod
    def _find_match(
        records: list[dict[str, object]],
        field: str,
        value: object,
    ) -> dict[str, object] | None:
        if value is None:
            return None
        str_value = str(value)
        for rec in records:
            if str(rec.get(field, "")) == str_value:
                return rec
        return None
