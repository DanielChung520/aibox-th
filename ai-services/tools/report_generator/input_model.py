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
        legend_show: bool = True,
        legend_position: str = "bottom",
        field_hints: str | None = None,
        special_notes: str | None = None,
        schedule_type: str | None = None,
        schedule_time: str | None = None,
        schedule_days: list[int] | None = None,
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
        self.legend_show = legend_show
        self.legend_position = legend_position
        self.field_hints = field_hints
        self.special_notes = special_notes
        self.schedule_type = schedule_type
        self.schedule_time = schedule_time
        self.schedule_days = schedule_days

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
            legend_show=data.get("legend_show", True),
            legend_position=data.get("legend_position", "bottom"),
            field_hints=data.get("field_hints"),
            special_notes=data.get("special_notes"),
            schedule_type=data.get("schedule_type"),
            schedule_time=data.get("schedule_time"),
            schedule_days=data.get("schedule_days"),
        )

    def validate(self) -> tuple[bool, str]:
        if not self.dataset:
            return False, "dataset不得為空"
        if not self.report_goal:
            return False, "report_goal不得為空"
        if self.preferred_chart and self.preferred_chart not in VALID_CHART_TYPES:
            return False, f"不支援的圖表類別: {self.preferred_chart}"
        if self.legend_position not in VALID_LEGEND_POSITIONS:
            return False, f"不支援的圖例位置: {self.legend_position}"
        try:
            dataset_size = len(__import__("json").dumps(self.dataset).encode("utf-8"))
            if dataset_size > MAX_DATASET_SIZE:
                return False, "資料集大小超過限制 (1MB)"
        except Exception:
            pass
        return True, ""


VALID_CHART_TYPES = {"pie", "bar", "line", "area", "scatter", "combo"}
VALID_LEGEND_POSITIONS = {"top", "bottom", "left", "right"}
MAX_DATASET_SIZE = 1024 * 1024
