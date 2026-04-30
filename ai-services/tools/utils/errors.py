"""Error types for tools."""


class ToolError(Exception):
    def __init__(self, message: str, tool_name: str | None = None) -> None:
        self.message = message
        self.tool_name = tool_name
        super().__init__(message)


class ToolConfigurationError(ToolError):
    pass


class ToolValidationError(ToolError):
    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        field: str | None = None,
    ) -> None:
        self.field = field
        super().__init__(message, tool_name=tool_name)


class ToolExecutionError(ToolError):
    pass
