from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from tools.utils.errors import ToolExecutionError
from tools.weather.providers.base import (
    ForecastData,
    ForecastItemData,
    HourlyForecastData,
    WeatherData,
    WeatherProvider,
)

WEATHER_CONFIG_URL = "http://localhost:6500/api/v1/weather/config"


class OpenWeatherMapProvider(WeatherProvider):
    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
    FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key

    def _load_from_rust(self) -> str:
        try:
            resp = httpx.get(WEATHER_CONFIG_URL, timeout=5.0)
            resp.raise_for_status()
            json_resp = resp.json()
            data = json_resp.get("data", {})
            return data.get("openweathermap_api_key", "")
        except Exception:
            return ""

    async def get_current_weather(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        units: str = "metric",
    ) -> WeatherData:
        api_key = self._api_key or self._load_from_rust()
        if not api_key:
            raise ToolExecutionError(
                "OpenWeatherMap API key not configured. Set via system_params or provide api_key.",
                tool_name="OpenWeatherMapProvider",
            )
        params: Dict[str, Any] = {"appid": api_key, "units": units}
        if city:
            params["q"] = city
        elif lat is not None and lon is not None:
            params["lat"] = str(lat)
            params["lon"] = str(lon)
        else:
            raise ToolExecutionError("Either city or lat/lon must be provided", tool_name="OpenWeatherMapProvider")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            return self._parse_response(data, units)
        except httpx.HTTPError as e:
            raise ToolExecutionError(f"OpenWeatherMap API error: {e}", tool_name="OpenWeatherMapProvider") from e

    def _parse_response(self, data: Dict[str, Any], units: str) -> WeatherData:
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        sys_data = data.get("sys", {})
        return WeatherData(
            city=data.get("name", "Unknown"),
            country=sys_data.get("country", "Unknown"),
            temperature=main.get("temp", 0.0),
            feels_like=main.get("feels_like", 0.0),
            humidity=main.get("humidity", 0),
            pressure=main.get("pressure", 0),
            description=weather.get("description", ""),
            icon=weather.get("icon", ""),
            wind_speed=wind.get("speed", 0.0),
            wind_direction=wind.get("deg", 0),
            visibility=data.get("visibility"),
            uv_index=None,
            timestamp=float(data.get("dt", 0)),
        )

    async def get_forecast(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        days: int = 3,
        hourly: bool = False,
        units: str = "metric",
    ) -> ForecastData:
        if days < 1 or days > 7:
            raise ToolExecutionError("days must be between 1 and 7", tool_name="OpenWeatherMapProvider")
        api_key = self._api_key or self._load_from_rust()
        if not api_key:
            raise ToolExecutionError("OpenWeatherMap API key not configured.", tool_name="OpenWeatherMapProvider")
        params: Dict[str, Any] = {"appid": api_key, "units": units}
        if city:
            params["q"] = city
        elif lat is not None and lon is not None:
            params["lat"] = str(lat)
            params["lon"] = str(lon)
        else:
            raise ToolExecutionError("Either city or lat/lon must be provided", tool_name="OpenWeatherMapProvider")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.FORECAST_URL, params=params)
                response.raise_for_status()
                data = response.json()
            return self._parse_forecast_response(data, days, hourly, units)
        except httpx.HTTPError as e:
            raise ToolExecutionError(f"OpenWeatherMap forecast API error: {e}", tool_name="OpenWeatherMapProvider") from e

    def _parse_forecast_response(self, data: Dict[str, Any], days: int, hourly: bool, units: str) -> ForecastData:
        city_info = data.get("city", {})
        list_data = data.get("list", [])

        daily_forecasts: Dict[str, list[Dict[str, Any]]] = defaultdict(list)
        for item in list_data:
            ts = item.get("dt", 0)
            dt = datetime.fromtimestamp(ts)
            date_key = dt.strftime("%Y-%m-%d")
            daily_forecasts[date_key].append(item)

        forecast_items: list[ForecastItemData] = []
        hourly_list: list[HourlyForecastData] = []

        for date_key in sorted(daily_forecasts.keys())[:days]:
            day_items = daily_forecasts[date_key]
            noon_item = min(day_items, key=lambda x: abs(datetime.fromtimestamp(x.get("dt", 0)).hour - 12))
            m = noon_item.get("main", {})
            w = noon_item.get("weather", [{}])[0]
            wn = noon_item.get("wind", {})

            min_temps = [x.get("main", {}).get("temp_min", 0.0) for x in day_items]
            max_temps = [x.get("main", {}).get("temp_max", 0.0) for x in day_items]

            precip = None
            if rain := noon_item.get("rain"):
                precip = rain.get("3h")
            elif snow := noon_item.get("snow"):
                precip = snow.get("3h")

            forecast_items.append(
                ForecastItemData(
                    date=date_key,
                    temperature=m.get("temp", 0.0),
                    min_temp=min(min_temps) if min_temps else m.get("temp_min", 0.0),
                    max_temp=max(max_temps) if max_temps else m.get("temp_max", 0.0),
                    description=w.get("description", ""),
                    icon=w.get("icon", ""),
                    humidity=m.get("humidity", 0),
                    wind_speed=wn.get("speed", 0.0),
                    precipitation=precip,
                    timestamp=float(noon_item.get("dt", 0)),
                )
            )

            if hourly:
                for item in day_items:
                    im = item.get("main", {})
                    iw = item.get("weather", [{}])[0]
                    iwn = item.get("wind", {})
                    iprecip = None
                    if irain := item.get("rain"):
                        iprecip = irain.get("3h")
                    elif isnow := item.get("snow"):
                        iprecip = isnow.get("3h")
                    hourly_list.append(
                        HourlyForecastData(
                            time=datetime.fromtimestamp(item.get("dt", 0)).isoformat(),
                            temperature=im.get("temp", 0.0),
                            description=iw.get("description", ""),
                            icon=iw.get("icon", ""),
                            humidity=im.get("humidity", 0),
                            wind_speed=iwn.get("speed", 0.0),
                            precipitation=iprecip,
                            timestamp=float(item.get("dt", 0)),
                        )
                    )

        return ForecastData(
            city=city_info.get("name", "Unknown"),
            country=city_info.get("country", "Unknown"),
            forecasts=forecast_items,
            hourly_forecasts=hourly_list if hourly else None,
        )
