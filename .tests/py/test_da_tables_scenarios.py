"""
@test file        da_tables/da_expressions pipeline 499 場景測試
@description     解析 Markdown 場景，批次呼叫 /ragic/query，生成統計報告
@lastUpdate      2026-04-13 06:50:00
@author          Daniel Chung
@version         1.0.0
"""

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

DATA_AGENT_URL = "http://localhost:8003"
QUERY_URL = f"{DATA_AGENT_URL}/ragic/query"
CONCURRENT_LIMIT = 10
REQUEST_TIMEOUT = 30.0


@dataclass
class Scenario:
    sid: str
    query: str
    expected_intent: str
    expected_query_type: str
    verification: str
    domain: str = ""


@dataclass
class TestResult:
    sid: str
    query: str
    expected_intent: str
    expected_query_type: str
    actual_intent: str = ""
    actual_query_type: str = ""
    actual_score: float = 0.0
    code: int = -1
    status: str = ""
    records_count: int = -1
    latency_ms: float = 0.0
    passed: bool = False
    error_msg: str = ""


def parse_scenarios(md_path: str) -> list[Scenario]:
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    scenarios: list[Scenario] = []
    current_domain = "UNKNOWN"

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            current_domain = stripped.lstrip("# ").strip()
            continue
        if not stripped.startswith("| ") or stripped.startswith("| ---"):
            continue
        cols = [c.strip() for c in stripped.split("|")]
        if len(cols) >= 6 and cols[1] and not cols[1].startswith("ID"):
            query = cols[2]
            expected_intent = cols[3]
            if query and expected_intent:
                scenarios.append(
                    Scenario(
                        sid=cols[1],
                        query=query,
                        expected_intent=expected_intent,
                        expected_query_type=cols[4],
                        verification=cols[5],
                        domain=current_domain,
                    )
                )
    return scenarios


async def run_single(client: httpx.AsyncClient, scenario: Scenario) -> TestResult:
    start = time.monotonic()
    try:
        response = await client.post(
            QUERY_URL,
            json={"query": scenario.query},
            timeout=REQUEST_TIMEOUT,
        )
        latency = (time.monotonic() - start) * 1000
        if response.status_code != 200:
            return TestResult(sid=scenario.sid, query=scenario.query,
                              expected_intent=scenario.expected_intent,
                              expected_query_type=scenario.expected_query_type,
                              latency_ms=latency, error_msg=f"HTTP {response.status_code}")

        data = response.json()
        code = data.get("code", -1)
        status = data.get("status", "")
        intent_block = data.get("intent", {}) or {}
        result_block = data.get("result", {}) or {}

        actual_intent = intent_block.get("intent_id", "")
        actual_score = intent_block.get("score", 0.0)
        records = result_block.get("records", []) or []
        records_count = len(records) if isinstance(records, list) else -1

        passed = code == 0 and actual_intent == scenario.expected_intent
        return TestResult(
            sid=scenario.sid, query=scenario.query,
            expected_intent=scenario.expected_intent,
            expected_query_type=scenario.expected_query_type,
            actual_intent=actual_intent, actual_score=actual_score,
            code=code, status=status, records_count=records_count,
            latency_ms=round(latency, 1), passed=passed,
        )
    except asyncio.TimeoutError:
        return TestResult(sid=scenario.sid, query=scenario.query,
                          expected_intent=scenario.expected_intent,
                          expected_query_type=scenario.expected_query_type,
                          latency_ms=(time.monotonic() - start) * 1000,
                          error_msg="TIMEOUT")
    except Exception as exc:
        return TestResult(sid=scenario.sid, query=scenario.query,
                          expected_intent=scenario.expected_intent,
                          expected_query_type=scenario.expected_query_type,
                          latency_ms=(time.monotonic() - start) * 1000,
                          error_msg=str(exc)[:100])


async def run_all(scenarios: list[Scenario]) -> list[TestResult]:
    async def bounded(s: Scenario) -> TestResult:
        async with httpx.AsyncClient() as client:
            return await run_single(client, s)

    tasks = [bounded(s) for s in scenarios]
    results: list[TestResult] = []
    for i, coro in enumerate(asyncio.as_completed(tasks)):
        result = await coro
        results.append(result)
        icon = "PASS" if result.passed else "FAIL"
        print(f"  [{i+1}/{len(scenarios)}] {result.sid}: {icon} "
              f"(code={result.code}, score={result.actual_score:.3f}, "
              f"intent={result.actual_intent[:30] if result.actual_intent else 'N/A'}, "
              f"latency={result.latency_ms:.0f}ms)")
    return results


def generate_report(scenarios: list[Scenario], results: list[TestResult],
                   output_path: str) -> dict:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    pass_rate = passed / total * 100 if total > 0 else 0

    by_domain: dict = {}
    for s, r in zip(scenarios, results):
        d = by_domain.setdefault(s.domain, {"total": 0, "passed": 0, "failed": 0})
        d["total"] += 1
        if r.passed:
            d["passed"] += 1
        else:
            d["failed"] += 1

    by_qtype: dict = {}
    for s, r in zip(scenarios, results):
        qt = s.expected_query_type
        d = by_qtype.setdefault(qt, {"total": 0, "passed": 0, "failed": 0})
        d["total"] += 1
        if r.passed:
            d["passed"] += 1
        else:
            d["failed"] += 1

    code_dist: dict = {}
    for r in results:
        code_dist[r.code] = code_dist.get(r.code, 0) + 1

    latencies = [r.latency_ms for r in results if r.latency_ms > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    max_lat = max(latencies) if latencies else 0
    min_lat = min(latencies) if latencies else 0

    failed_results = [r for r in results if not r.passed]

    report = {
        "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": total, "passed": passed, "failed": failed,
        "pass_rate": round(pass_rate, 1),
        "avg_latency_ms": round(avg_lat, 1),
        "max_latency_ms": round(max_lat, 1),
        "min_latency_ms": round(min_lat, 1),
        "by_domain": by_domain,
        "by_query_type": by_qtype,
        "code_distribution": code_dist,
        "failed_results": [
            {"sid": r.sid, "query": r.query[:50], "expected_intent": r.expected_intent,
             "actual_intent": r.actual_intent, "code": r.code,
             "score": round(r.actual_score, 3), "error": r.error_msg}
            for r in failed_results[:30]
        ],
    }

    json_path = output_path.replace(".md", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"lastUpdate: {report['test_date']}\n")
        f.write("author: Daniel Chung\n")
        f.write("version: 1.0.0\n")
        f.write("---\n\n# Data Agent da_tables 測試報告\n\n")
        f.write("## 測試摘要\n\n")
        f.write(f"| 項目 | 值 |\n|------|-----|\n")
        f.write(f"| 測試日期 | {report['test_date']} |\n")
        f.write(f"| 總場景數 | {report['total']} |\n")
        f.write(f"| 通過 | {report['passed']} ({report['pass_rate']}%)\n")
        f.write(f"| 失敗 | {report['failed']} |\n")
        f.write(f"| 平均延遲 | {report['avg_latency_ms']}ms |\n")
        f.write(f"| 最大延遲 | {report['max_latency_ms']}ms |\n\n")

        f.write("## 按領域統計\n\n")
        f.write("| 領域 | 總數 | 通過 | 失敗 | 通過率 |\n")
        f.write("|------|------|------|------|--------|\n")
        for domain, stats in sorted(by_domain.items()):
            pr = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            f.write(f"| {domain} | {stats['total']} | {stats['passed']} | "
                    f"{stats['failed']} | {pr:.1f}% |\n")
        f.write("\n")

        f.write("## 按 query_type 統計\n\n")
        f.write("| query_type | 總數 | 通過 | 失敗 | 通過率 |\n")
        f.write("|------------|------|------|------|--------|\n")
        for qt, stats in sorted(by_qtype.items()):
            pr = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            f.write(f"| {qt} | {stats['total']} | {stats['passed']} | "
                    f"{stats['failed']} | {pr:.1f}% |\n")
        f.write("\n")

        f.write("## 回應代碼分佈\n\n")
        f.write("| code | 數量 | 說明 |\n")
        f.write("|------|------|------|\n")
        code_names = {0: "成功", 3: "Clarification needed", 4: "table_key 格式錯誤", 5: "Clarification"}
        for code, count in sorted(code_dist.items()):
            f.write(f"| {code} | {count} | {code_names.get(code, '未知')} |\n")
        f.write("\n")

        if failed_results:
            f.write(f"## 失敗場景（前 {min(30, len(failed_results))} 項）\n\n")
            f.write("| ID | 查詢 | 預期意圖 | 實際意圖 | code | score | 原因 |\n")
            f.write("|----|------|---------|---------|------|-------|------|\n")
            for r in failed_results[:30]:
                reason = r.error_msg or f"intent mismatch (expected={r.expected_intent})"
                f.write(f"| {r.sid} | {r.query[:30]} | {r.expected_intent} | "
                        f"{r.actual_intent or 'N/A'} | {r.code} | "
                        f"{r.actual_score:.3f} | {reason} |\n")
            f.write("\n")

        scores = [r.actual_score for r in results if r.actual_score > 0]
        if scores:
            buckets = {"0.9+": 0, "0.7-0.9": 0, "0.5-0.7": 0, "0.3-0.5": 0, "<0.3": 0}
            for s in scores:
                if s >= 0.9: buckets["0.9+"] += 1
                elif s >= 0.7: buckets["0.7-0.9"] += 1
                elif s >= 0.5: buckets["0.5-0.7"] += 1
                elif s >= 0.3: buckets["0.3-0.5"] += 1
                else: buckets["<0.3"] += 1
            f.write("## 分數分佈\n\n")
            f.write("| 分數區間 | 數量 |\n|----------|------|\n")
            for bucket, count in buckets.items():
                f.write(f"| {bucket} | {count} |\n")
            f.write("\n")

        f.write(f"\n*報告生成時間: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n")

    print(f"\nReport saved to: {output_path}")
    print(f"JSON saved to: {json_path}")
    return report


async def main():
    script_dir = Path(__file__).parent
    scenario_file = script_dir.parent / ".senario" / "data-agent-da-tables-scenarios.md"
    output_file = script_dir.parent / ".senario" / "da-tables-test-report.md"

    print(f"Parsing scenarios from: {scenario_file}")
    scenarios = parse_scenarios(str(scenario_file))
    print(f"Loaded {len(scenarios)} scenarios\nRunning tests...")
    results = await run_all(scenarios)
    report = generate_report(scenarios, results, str(output_file))

    print(f"\n{'='*60}")
    print(f"  TOTAL: {report['total']}  |  PASSED: {report['passed']}  |  FAILED: {report['failed']}")
    print(f"  PASS RATE: {report['pass_rate']}%")
    print(f"  AVG LATENCY: {report['avg_latency_ms']}ms")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
