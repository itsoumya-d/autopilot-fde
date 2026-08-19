from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime
from ..models.schema import Message, ChannelType

class ChannelConnector(ABC):
    def __init__(self, config: Dict[str, str]):
        self.config = config

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection with the channel."""
        pass

    @abstractmethod
    async def fetch_messages(self, since: datetime) -> List[Message]:
        """Fetch messages since the given timestamp."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the connection is healthy."""
        pass
    
    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """Return the channel type."""
        pass
