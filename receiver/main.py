"""
JCF Webhook Receiver  —  Railway service
Accepts TradingView alerts and Alpaca events, enriches them with live
chart context from the co-located TV MCP service, then forwards to the
local relay (exposed via ngrok).
"""
import os
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, BackgroundTasks, Header, HTTPException, Request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jcf-receiver")

app = FastAPI(title="JCF Webhook Receiver")

# ── env vars (set in Railway dashboard) ───────────────────────────────────────
LOCAL_RELAY_URL   = os.environ["LOCAL_RELAY_URL"].rstrip("/")  # ngrok tunnel URL
RELAY_SECRET      = os.environ["RELAY_SECRET"]                 # shared Bearer token
TV_MCP_URL        = os.environ["TV_MCP_URL"].rstrip("/")       # internal Railway URL of the TV MCP service
TV_WEBHOOK_SECRET = os.environ.get("TV_WEBHOOK_SECRET", "")   # query-param secret for TradingView

# Alpaca HMAC signing secret — optional; from Alpaca dashboard → Webhooks
ALPACA_SIGNING_SECRET = os.environ.get("ALPACA_SIGNING_SECRET", "")


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "relay": LOCAL_RELAY_URL, "tv_mcp": TV_MCP_URL}


@app.post("/webhook/tradingview")
async def tradingview(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str = "",
):
    if TV_WEBHOOK_SECRET and secret != TV_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    event = {
        "source": "tradingview",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": body,
    }
    background_tasks.add_task(_process_tradingview, event)
    return {"status": "queued"}


@app.post("/webhook/alpaca")
async def alpaca(request: Request, background_tasks: BackgroundTasks):
    raw = await request.body()

    if ALPACA_SIGNING_SECRET:
        import hmac, hashlib
        sig = request.headers.get("apca-api-signature", "")
        expected = hmac.new(
            ALPACA_SIGNING_SECRET.encode(), raw, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(status_code=401, detail="Invalid Alpaca signature")

    event = {
        "source": "alpaca",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": json.loads(raw),
    }
    background_tasks.add_task(_forward, event)
    return {"status": "queued"}


# ── background processing ─────────────────────────────────────────────────────

async def _process_tradingview(event: dict):
    """Enrich the TV alert with live chart context from the TV MCP, then forward."""
    payload = event.get("payload", {})
    ticker = payload.get("ticker", "")

    if ticker:
        chart_ctx = await _enrich_from_mcp(ticker)
        event["chart_context"] = chart_ctx
        log.info("Enriched %s alert with MCP context: %s", ticker, list(chart_ctx.keys()))

    await _forward(event)


async def _enrich_from_mcp(ticker: str) -> dict:
    """
    Call the co-located TV MCP service using MCP-over-HTTP JSON-RPC.
    Returns a dict of chart context to attach to the event.
    Falls back to {} on any error so the alert is never lost.
    """
    context = {}
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        async with streamablehttp_client(TV_MCP_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Real-time quote
                quote_result = await session.call_tool("quote_get", {"symbol": ticker})
                if quote_result.content:
                    context["quote"] = _extract_text(quote_result.content)

                # Current indicator / study values (AVWAP etc.)
                studies_result = await session.call_tool(
                    "data_get_study_values", {"symbol": ticker}
                )
                if studies_result.content:
                    context["studies"] = _extract_text(studies_result.content)

    except Exception as exc:
        log.warning("TV MCP enrichment failed for %s: %s", ticker, exc)

    return context


def _extract_text(content) -> str:
    """Pull text out of MCP tool result content list."""
    parts = []
    for item in content:
        if hasattr(item, "text"):
            parts.append(item.text)
        else:
            parts.append(str(item))
    return "\n".join(parts)


async def _forward(event: dict):
    """POST the event to the local relay via the ngrok tunnel."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{LOCAL_RELAY_URL}/relay",
                json=event,
                headers={"Authorization": f"Bearer {RELAY_SECRET}"},
            )
            resp.raise_for_status()
            log.info("Forwarded %s event → HTTP %s", event["source"], resp.status_code)
    except Exception as exc:
        log.error("Forward failed for %s event: %s", event["source"], exc)
