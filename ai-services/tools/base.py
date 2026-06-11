from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

T_in = TypeVar("T_in", bound="ToolInput")
T_out = TypeVar("T_out", bound="ToolOutput")


class ToolInput(BaseModel, ABC):
    pass


class ToolOutput(BaseModel, ABC):
    pass


class BaseTool(ABC, Generic[T_in, T_out]):

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        raise NotImplementedError

    @property
    def version(self) -> str:
        return "1.0.0"

    @abstractmethod
    async def execute(self, input_data: T_in) -> T_out:
        raise NotImplementedError
