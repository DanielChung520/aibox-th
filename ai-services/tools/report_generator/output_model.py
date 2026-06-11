from typing import Any


class ToolReportsOutput:
    def __init__(
        self,
        success: bool,
        report_url: str | None = None,
        filename: str | None = None,
        title: str = "",
        chart_type: str = "",
        analysis_summary: str = "",
        domain_context: str | None = None,
        size_bytes: int | None = None,
        warnings: list[str] | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.report_url = report_url
        self.filename = filename
        self.title = title
        self.chart_type = chart_type
        self.analysis_summary = analysis_summary
        self.domain_context = domain_context
        self.size_bytes = size_bytes
        self.warnings = warnings or []
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "report_url": self.report_url,
            "filename": self.filename,
            "title": self.title,
            "chart_type": self.chart_type,
            "analysis_summary": self.analysis_summary,
            "domain_context": self.domain_context,
            "size_bytes": self.size_bytes,
            "warnings": self.warnings,
            "error": self.error,
        }
