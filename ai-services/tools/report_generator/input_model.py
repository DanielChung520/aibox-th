class ToolReportsInput:
    def __init__(
        self,
        dataset: dict | list[dict],
        report_goal: str,
        preferred_chart: str | None = None,
        knowledge_domain: str | None = None,
        hints: str | None = None,
        title: str | None = None,
        author: str = "system",
        username: str = "anonymous",
        chart_options: dict | None = None,
    ):
        self.dataset = dataset
        self.report_goal = report_goal
        self.preferred_chart = preferred_chart
        self.knowledge_domain = knowledge_domain
        self.hints = hints
        self.title = title
        self.author = author
        self.username = username
        self.chart_options = chart_options or {}

    @classmethod
    def from_dict(cls, data: dict) -> "ToolReportsInput":
        return cls(
            dataset=data["dataset"],
            report_goal=data["report_goal"],
            preferred_chart=data.get("preferred_chart"),
            knowledge_domain=data.get("knowledge_domain"),
            hints=data.get("hints"),
            title=data.get("title"),
            author=data.get("author", "system"),
            username=data.get("username", "anonymous"),
            chart_options=data.get("chart_options"),
        )

    def validate(self) -> tuple[bool, str]:
        if not self.dataset:
            return False, "dataset不得為空"
        if not self.report_goal:
            return False, "report_goal不得為空"
        if self.preferred_chart and self.preferred_chart not in VALID_CHART_TYPES:
            return False, f"不支援的圖表類別: {self.preferred_chart}"
        try:
            dataset_size = len(__import__("json").dumps(self.dataset).encode("utf-8"))
            if dataset_size > MAX_DATASET_SIZE:
                return False, "資料集大小超過限制 (1MB)"
        except Exception:
            pass
        return True, ""


VALID_CHART_TYPES = {"pie", "bar", "line", "area", "scatter", "combo"}
MAX_DATASET_SIZE = 1024 * 1024
