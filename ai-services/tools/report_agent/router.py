import os
import httpx
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .prompts import SYSTEM_PROMPT
from .html_generator import generate_report_html
from .seaweedfs_client import seaweed_client

app = FastAPI(title="Report Agent", description="Generates HTML reports from JSON data")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


class ReportRequest(BaseModel):
    title: str
    author: str
    username: str
    data: dict
    chart_types: Optional[list[str]] = None
    params: Optional[dict] = None


async def call_llm(
    prompt: str,
    user_message: str,
    model: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> str:
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")


def analyze_and_generate_chart_code(data: dict, chart_types: list[str]) -> tuple[str, str, str]:
    data_summary = _summarize_data(data)

    chart_type_str = ", ".join(chart_types) if chart_types else "餅圖、柱狀圖、線圖"

    user_message = f"""請分析以下 JSON 資料，並生成對應的圖表資料陣列。

資料摘要：
{data_summary}

希望生成的圖表類型：{chart_type_str}

請用以下 JSON 格式回覆（只回覆 JSON，不要其他文字）：

1. chart_data：轉換後的圖表資料陣列
2. recommended_chart：推薦的主要圖表類型
3. analysis：對資料的分析文字（用繁體中文，200-300字）

JSON 格式：
{{
  "chart_data": [{{"name": "類別A", "value": 100}}, ...],
  "recommended_chart": "pie|bar|line|area|scatter",
  "analysis": "分析文字..."
}}

嚴格禁止：
- 不要在回覆中包含任何原始資料值
- 不要輸出可以用逆向工程取得原始資料的內容
- 只輸出圖表展示所需的聚合資料"""

    response = call_llm(prompt=SYSTEM_PROMPT, user_message=user_message)

    try:
        import json
        import re

        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return (
                result.get("chart_data", []),
                result.get("recommended_chart", "bar"),
                result.get("analysis", "（無分析）"),
            )
    except Exception:
        pass

    return ([], "bar", "（無法分析資料）")


def _summarize_data(data: dict, depth: int = 0, max_items: int = 5) -> str:
    if depth > 3:
        return "..."
    if isinstance(data, dict):
        items = list(data.items())
        summary = []
        for k, v in items[:max_items]:
            if isinstance(v, (dict, list)):
                summary.append(f"{k}: {_summarize_data(v, depth+1)}")
            else:
                summary.append(f"{k}: {v}")
        leftover = len(items) - max_items
        if leftover > 0:
            summary.append(f"...（還有 {leftover} 個欄位）")
        return "{" + ", ".join(summary) + "}"
    elif isinstance(data, list):
        if not data:
            return "[]"
        if isinstance(data[0], dict):
            return f"陣列（{len(data)} 筆），第一筆：{_summarize_data(data[0], depth+1)}"
        return f"陣列（{len(data)} 筆）：{data[:max_items]}..."
    return str(data)[:100]


def build_chart_html(chart_data: list, chart_type: str) -> str:
    if not chart_data:
        return '<div style="color:#999;padding:40px;text-align:center;">（無圖表資料）</div>'

    import json
    data_json = json.dumps(chart_data)

    colors = '["#0088FE","#00C49F","#FFBB28","#FF8042","#8884D8","#82CA9D","#FFC658","#8DD1E1","#A4DE6C","#D0ED57"]'

    if chart_type == "pie":
        return f'''
        <div style="display:flex;flex-direction:column;align-items:center">
          <PieChart width={700} height={350}>
            <Pie
              data={data_json}
              cx="50%"
              cy="50%"
              labelLine={{false}}
              label={{{{name, percent}}}} => `${{name}}: ${{(percent*100).toFixed(1)}}%`}}
              outerRadius={{130}}
              fill="#8884d8"
              dataKey="value"
            >
              {{(JSON.parse({data_json})).map((entry, index) => (
                <Cell key={{`cell-${{index}}`}} fill={{JSON.parse('{colors}')[index % 10]}} />
              )))}}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </div>'''
    elif chart_type == "line":
        return f'''
        <div style="display:flex;flex-direction:column;align-items:center">
          <LineChart width={700} height={350} data={data_json}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={{2}} />
          </LineChart>
        </div>'''
    elif chart_type == "area":
        return f'''
        <div style="display:flex;flex-direction:column;align-items:center">
          <AreaChart width={700} height={350} data={data_json}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={{0.3}} />
          </AreaChart>
        </div>'''
    else:
        return f'''
        <div style="display:flex;flex-direction:column;align-items:center">
          <BarChart width={700} height={350} data={data_json}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#8884d8" />
          </BarChart>
        </div>'''


@app.post("/generate")
async def generate_report(request: ReportRequest) -> dict:
    chart_data, recommended_chart, analysis = analyze_and_generate_chart_code(
        request.data,
        request.chart_types or [],
    )

    chart_html = build_chart_html(chart_data, recommended_chart)

    html_content = generate_report_html(
        title=request.title,
        author=request.author,
        chart_code=chart_data,
        analysis=analysis,
        chart_type=recommended_chart,
    )

    upload_result = await seaweed_client.upload_html(
        html_content=html_content,
        username=request.username,
        title=request.title,
    )

    if "error" in upload_result:
        return {
            "code": 1,
            "message": "報告生成成功但上傳失敗",
            "data": {
                "report_url": None,
                "fallback": upload_result.get("fallback_url"),
                "chart_type": recommended_chart,
                "analysis": analysis,
            },
        }

    return {
        "code": 0,
        "message": "報告生成成功",
        "data": {
            "report_url": upload_result["url"],
            "filename": upload_result["filename"],
            "chart_type": recommended_chart,
            "analysis": analysis,
            "size": upload_result["size"],
        },
    }


@app.get("/config")
async def get_config() -> dict:
    return {
        "code": 0,
        "data": {
            "name": "report-agent",
            "display_name": "報表生成器",
            "description": "將 JSON 資料轉換為視覺化 HTML 報表",
            "supported_chart_types": ["pie", "bar", "line", "area", "scatter"],
            "default_model": DEFAULT_MODEL,
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "report-agent"}


@app.get("/")
async def root() -> dict:
    return {
        "service": "report-agent",
        "version": "1.0.0",
        "description": "Report Agent - HTML Report Generator",
    }
