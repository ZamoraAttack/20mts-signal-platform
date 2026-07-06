from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class Tick:
    symbol: str
    price: float
    timestamp: datetime
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None


class DataFeed(ABC):
    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None: ...

    @abstractmethod
    def stream(self) -> AsyncIterator[Tick]: ...

    @abstractmethod
    async def disconnect(self) -> None: ...
