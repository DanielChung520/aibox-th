from typing import Any

from .html_generator import generate_report_html
from .input_model import ToolReportsInput
from .llm_analyzer import analyze_and_generate
from .output_model import ToolReportsOutput
from .seaweedfs_client import seaweed_client


async def tool_reports_execute(params: dict[str, Any]) -> ToolReportsOutput:
    input_data = ToolReportsInput.from_dict(params)
    valid, msg = input_data.validate()
    if not valid:
        return ToolReportsOutput(success=False, error=msg)

    llm_result = await analyze_and_generate(
        dataset=input_data.dataset,
        report_goal=input_data.report_goal,
        preferred_chart=input_data.preferred_chart,
        domain_context=None,
    )

    title = input_data.title or input_data.report_goal[:30]

    html_content = generate_report_html(
        title=title,
        chart_data=llm_result["chart_data"],
        chart_type=llm_result["chart_type"],
        analysis_summary=llm_result["analysis_summary"],
        author=input_data.author,
        hints=input_data.hints,
    )

    upload_result = await seaweed_client.upload_html(
        html_content=html_content,
        username=input_data.username,
        title=title,
    )

    if "error" in upload_result:
        return ToolReportsOutput(
            success=True,
            report_url=None,
            filename=None,
            title=title,
            chart_type=llm_result["chart_type"],
            analysis_summary=llm_result["analysis_summary"],
            size_bytes=len(html_content),
            warnings=[f"報告上傳失敗: {upload_result['error']}"],
        )

    return ToolReportsOutput(
        success=True,
        report_url=upload_result["url"],
        filename=upload_result["filename"],
        title=title,
        chart_type=llm_result["chart_type"],
        analysis_summary=llm_result["analysis_summary"],
        size_bytes=upload_result["size"],
    )
