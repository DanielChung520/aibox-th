from typing import Optional

from tools.base import BaseTool, ToolInput, ToolOutput
from tools.utils.cache import generate_cache_key, get_cache
from tools.utils.errors import ToolValidationError
from tools.utils.validator import validate_coordinates, validate_non_empty_string
from tools.weather.providers.openweathermap import OpenWeatherMapProvider

WEATHER_CACHE_TTL = 600.0


class WeatherInput(ToolInput):
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    units: str = "metric"


class WeatherOutput(ToolOutput):
    city: str
    country: str
    temperature: float
    feels_like: float
    humidity: int
    pressure: int
    description: str
    icon: str
    wind_speed: float
    wind_direction: int
    visibility: Optional[int] = None
    uv_index: Optional[float] = None
    timestamp: float


class WeatherTool(BaseTool[WeatherInput, WeatherOutput]):
    def __init__(self) -> None:
        self._provider = OpenWeatherMapProvider()

    @property
    def name(self) -> str:
        return "weather"

    @property
    def description(self) -> str:
        return "Get current weather by city name or coordinates"

    async def execute(self, input_data: WeatherInput) -> WeatherOutput:
        if not input_data.city and (input_data.lat is None or input_data.lon is None):
            raise ToolValidationError("Either city or lat/lon must be provided", field="city")
        if input_data.city:
            validate_non_empty_string(input_data.city, "city")
        if input_data.lat is not None and input_data.lon is not None:
            if not validate_coordinates(input_data.lat, input_data.lon):
                raise ToolValidationError("Invalid coordinates", field="lat")
        if input_data.units not in ("metric", "imperial"):
            raise ToolValidationError("units must be 'metric' or 'imperial'", field="units")

        cache_key = generate_cache_key(
            "weather",
            city=input_data.city or "",
            lat=input_data.lat or 0.0,
            lon=input_data.lon or 0.0,
            units=input_data.units,
        )
        cache = get_cache()
        cached = cache.get(cache_key)
        if cached:
            return WeatherOutput(**cached)

        data = await self._provider.get_current_weather(
            city=input_data.city, lat=input_data.lat, lon=input_data.lon, units=input_data.units
        )
        output = WeatherOutput(
            city=data.city,
            country=data.country,
            temperature=data.temperature,
            feels_like=data.feels_like,
            humidity=data.humidity,
            pressure=data.pressure,
            description=data.description,
            icon=data.icon,
            wind_speed=data.wind_speed,
            wind_direction=data.wind_direction,
            visibility=data.visibility,
            uv_index=data.uv_index,
            timestamp=data.timestamp,
        )
        cache.set(cache_key, output.model_dump(), ttl=WEATHER_CACHE_TTL)
        return output
