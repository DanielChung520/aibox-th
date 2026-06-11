from typing import List, Optional

from pydantic import BaseModel

from tools.base import BaseTool, ToolInput, ToolOutput
from tools.utils.cache import generate_cache_key, get_cache
from tools.utils.errors import ToolValidationError
from tools.utils.validator import validate_coordinates, validate_non_empty_string
from tools.weather.providers.openweathermap import OpenWeatherMapProvider

FORECAST_CACHE_TTL = 3600.0


class HourlyForecast(BaseModel):
    time: str
    temperature: float
    description: str
    icon: str
    humidity: int
    wind_speed: float
    precipitation: Optional[float] = None
    timestamp: float


class ForecastItem(BaseModel):
    date: str
    temperature: float
    min_temp: float
    max_temp: float
    description: str
    icon: str
    humidity: int
    wind_speed: float
    precipitation: Optional[float] = None
    hourly: Optional[List[HourlyForecast]] = None
    timestamp: float


class ForecastInput(ToolInput):
    city: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    days: int = 3
    hourly: bool = False
    units: str = "metric"


class ForecastOutput(ToolOutput):
    city: str
    country: str
    forecasts: List[ForecastItem]


class ForecastTool(BaseTool[ForecastInput, ForecastOutput]):
    def __init__(self) -> None:
        self._provider = OpenWeatherMapProvider()

    @property
    def name(self) -> str:
        return "forecast"

    @property
    def description(self) -> str:
        return "Get weather forecast for the next few days"

    async def execute(self, input_data: ForecastInput) -> ForecastOutput:
        if not input_data.city and (input_data.lat is None or input_data.lon is None):
            raise ToolValidationError("Either city or lat/lon must be provided", field="city")
        if input_data.city:
            validate_non_empty_string(input_data.city, "city")
        if input_data.lat is not None and input_data.lon is not None:
            if not validate_coordinates(input_data.lat, input_data.lon):
                raise ToolValidationError("Invalid coordinates", field="lat")
        if input_data.days < 1 or input_data.days > 7:
            raise ToolValidationError("days must be between 1 and 7", field="days")
        if input_data.units not in ("metric", "imperial"):
            raise ToolValidationError("units must be 'metric' or 'imperial'", field="units")

        cache_key = generate_cache_key(
            "forecast",
            city=input_data.city or "",
            lat=input_data.lat or 0.0,
            lon=input_data.lon or 0.0,
            days=input_data.days,
            hourly=input_data.hourly,
            units=input_data.units,
        )
        cache = get_cache()
        cached = cache.get(cache_key)
        if cached:
            return ForecastOutput(**cached)

        data = await self._provider.get_forecast(
            city=input_data.city,
            lat=input_data.lat,
            lon=input_data.lon,
            days=input_data.days,
            hourly=input_data.hourly,
            units=input_data.units,
        )

        hourly_by_date: dict[str, List[HourlyForecast]] = {}
        if data.hourly_forecasts:
            from datetime import datetime

            for h in data.hourly_forecasts:
                dk = datetime.fromtimestamp(h.timestamp).strftime("%Y-%m-%d")
                if dk not in hourly_by_date:
                    hourly_by_date[dk] = []
                hourly_by_date[dk].append(
                    HourlyForecast(
                        time=h.time,
                        temperature=h.temperature,
                        description=h.description,
                        icon=h.icon,
                        humidity=h.humidity,
                        wind_speed=h.wind_speed,
                        precipitation=h.precipitation,
                        timestamp=h.timestamp,
                    )
                )

        forecast_items: List[ForecastItem] = []
        for item in data.forecasts:
            forecast_items.append(
                ForecastItem(
                    date=item.date,
                    temperature=item.temperature,
                    min_temp=item.min_temp,
                    max_temp=item.max_temp,
                    description=item.description,
                    icon=item.icon,
                    humidity=item.humidity,
                    wind_speed=item.wind_speed,
                    precipitation=item.precipitation,
                    hourly=hourly_by_date.get(item.date),
                    timestamp=item.timestamp,
                )
            )

        output = ForecastOutput(city=data.city, country=data.country, forecasts=forecast_items)
        cache.set(cache_key, output.model_dump(), ttl=FORECAST_CACHE_TTL)
        return output
