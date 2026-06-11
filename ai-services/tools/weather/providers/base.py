from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import BaseModel


class WeatherData(BaseModel):
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


class ForecastItemData(BaseModel):
    date: str
    temperature: float
    min_temp: float
    max_temp: float
    description: str
    icon: str
    humidity: int
    wind_speed: float
    precipitation: Optional[float] = None
    timestamp: float


class HourlyForecastData(BaseModel):
    time: str
    temperature: float
    description: str
    icon: str
    humidity: int
    wind_speed: float
    precipitation: Optional[float] = None
    timestamp: float


class ForecastData(BaseModel):
    city: str
    country: str
    forecasts: List[ForecastItemData]
    hourly_forecasts: Optional[List[HourlyForecastData]] = None


class WeatherProvider(ABC):
    @abstractmethod
    async def get_current_weather(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        units: str = "metric",
    ) -> WeatherData:
        pass

    @abstractmethod
    async def get_forecast(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        days: int = 3,
        hourly: bool = False,
        units: str = "metric",
    ) -> ForecastData:
        pass
