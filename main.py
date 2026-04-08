import re
import os
import logging
import html
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ───────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DECRYPT_API = os.getenv("DECRYPT_API", "")
HAPP_API_KEY = os.getenv("HAPP_API_KEY", "")

NOTIFY_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

BLOCKED_DOMAINS = [
    "not.stilluploading.sbs",
]

HAPP_PATTERN = re.compile(r"(happ://crypt[0-5]?/[^\s]+)")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Happ Decrypt API",
    description="API that decrypts happ:// encrypted subscription links.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ──────────────────────────────────────────────────────────────────
class DecryptRequest(BaseModel):
    link: str


class DecryptResponse(BaseModel):
    success: bool
    original_link: str
    decrypted_url: Optional[str] = None
    error: Optional[str] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────
def h(text: str) -> str:
    return html.escape(text)


async def _notify(channel_id: int, text: str) -> bool:
    """Internal notification."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{NOTIFY_API}/sendMessage",
                json={
                    "chat_id": channel_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
            )
            result = resp.json()
            if not result.get("ok"):
                logger.error("Notify failed: %s", result)
                return False
            return True
    except Exception as exc:
        logger.error("Notify error: %s", exc)
        return False


async def decrypt_link(happ_link: str) -> dict:
    """Perform decryption on the given link."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            DECRYPT_API,
            headers={"x-api-key": HAPP_API_KEY},
            json={"link": happ_link},
        )
        return resp.json()


# ─── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "Happ Decrypt API",
        "version": "1.0.0",
        "endpoints": {
            "POST /decrypt": "Decrypt a happ:// subscription link",
            "GET /health": "Health check",
        },
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/decrypt", response_model=DecryptResponse)
async def decrypt(req: DecryptRequest):
    """
    Decrypt a happ:// subscription link.

    - Validates the link format
    - Decrypts the subscription
    - Returns the decrypted URL to the caller
    """
    # Validate link format
    match = HAPP_PATTERN.search(req.link)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Invalid link format. Expected happ://crypt[0-5]/...",
        )

    happ_link = match.group(1)
    logger.info("API decrypt request: %s", happ_link)

    # Decrypt
    try:
        data = await decrypt_link(happ_link)
    except Exception as exc:
        logger.error("Decrypt API error: %s", exc)
        return DecryptResponse(
            success=False,
            original_link=happ_link,
            error="Decryption service temporarily unavailable. Please try again later.",
        )

    if not data.get("success") or not data.get("result"):
        return DecryptResponse(
            success=False,
            original_link=happ_link,
            error="Decryption failed. The link may be invalid or expired.",
        )

    decrypted_url = data["result"]

    # Check blocked domains
    if any(domain in decrypted_url for domain in BLOCKED_DOMAINS):
        return DecryptResponse(
            success=False,
            original_link=happ_link,
            error="This subscription is protected and cannot be decrypted.",
        )

    # Internal logging
    notify_msg = (
        "<b>\U0001f513 New API Decryption</b>\n\n"
        f"<b>\U0001f517 Original:</b>  <code>{h(happ_link)}</code>\n"
        f"<b>\u2705 Decrypted:</b>\n<code>{h(decrypted_url)}</code>\n\n"
        f"<b>\U0001f550 Time:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    await _notify(CHANNEL_ID, notify_msg)

    logger.info("Decrypted: %s", decrypted_url)

    return DecryptResponse(
        success=True,
        original_link=happ_link,
        decrypted_url=decrypted_url,
    )


# ─── Run ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
