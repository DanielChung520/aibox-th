"""Input validators."""


def validate_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        from tools.utils.errors import ToolValidationError
        raise ToolValidationError(f"{field_name} must be a non-empty string", field=field_name)


def validate_coordinates(lat: float, lon: float) -> bool:
    return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
