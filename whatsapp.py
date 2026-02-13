import logging
import re

import httpx

from config import WHATSAPP_CHAT_ID, WHATSAPP_SERVICE_URL

log = logging.getLogger(__name__)


def to_whatsapp_text(text: str) -> str:
    """Convert Telegram markdown links [label](url) to plain URLs for WhatsApp."""
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\2', text)


async def post_to_whatsapp(text: str, chat_id: str = WHATSAPP_CHAT_ID) -> None:
    if not chat_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{WHATSAPP_SERVICE_URL}/send",
                json={"chatId": chat_id, "message": text},
            )
            if resp.status_code != 200:
                log.warning("WhatsApp send failed: %s %s", resp.status_code, resp.text)
    except Exception:
        log.warning("WhatsApp send failed", exc_info=True)
