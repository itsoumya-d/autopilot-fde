from typing import List, Dict, Any
from datetime import datetime
import logging
from .base import ChannelConnector
from ..models.schema import Message, ChannelType
import uuid
import httpx

logger = logging.getLogger(__name__)

class WhatsAppConnector(ChannelConnector):
    def __init__(self, config: Dict[str, str]):
        super().__init__(config)
        self.access_token = config.get("access_token")
        self.phone_number_id = config.get("phone_number_id")
        self.verify_token = config.get("verify_token") # For webhook setup
        
        if not self.access_token or not self.phone_number_id:
            raise ValueError("WhatsApp access_token and phone_number_id are required")

    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    async def connect(self) -> bool:
        # Check if the token is valid by making a simple API call
        url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"WhatsApp connect error: {e}")
            return False

    async def health_check(self) -> bool:
        return await self.connect()

    async def fetch_messages(self, since: datetime) -> List[Message]:
        # WhatsApp Cloud API primarily uses Webhooks for receiving messages.
        # Fetching historical messages directly is not straightforward.
        # For this connector, fetch_messages might be a no-op, relying instead 
        # on a webhook endpoint in the FastAPI app to push messages to the pipeline.
        logger.info("WhatsApp primarily uses webhooks. fetch_messages is a no-op.")
        return []
        
    def parse_webhook_payload(self, payload: Dict[str, Any]) -> List[Message]:
        """Utility to parse incoming webhook payload into Message objects."""
        messages = []
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    phone_number_id = metadata.get("phone_number_id")
                    
                    if phone_number_id != self.phone_number_id:
                        continue
                        
                    for msg in value.get("messages", []):
                        timestamp = datetime.fromtimestamp(int(msg.get("timestamp")))
                        sender = msg.get("from")
                        msg_id = msg.get("id")
                        
                        content = ""
                        msg_type = msg.get("type")
                        if msg_type == "text":
                            content = msg.get("text", {}).get("body", "")
                        elif msg_type == "image":
                            content = "[Image Attachment]"
                        elif msg_type == "document":
                            content = "[Document Attachment]"
                        else:
                            content = f"[{msg_type} message]"
                            
                        messages.append(Message(
                            id=msg_id or str(uuid.uuid4()),
                            channel_id=phone_number_id,
                            sender=sender,
                            content=content,
                            timestamp=timestamp,
                            metadata={"whatsapp_type": msg_type}
                        ))
        except Exception as e:
            logger.error(f"Error parsing WhatsApp webhook payload: {e}")
            
        return messages
