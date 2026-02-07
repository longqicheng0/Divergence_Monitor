"""Discord webhook alerting."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import aiohttp

logger = logging.getLogger(__name__)


def build_discord_payload(
    symbol: str,
    timeframe: str,
    signal_type: str,
    strength: str,
    confirmations: list[str],
    reason: str,
    pivot_ts: str,
) -> Dict[str, Any]:
    """Build a Discord webhook payload."""

    title = f"{signal_type.title()} divergence ({strength})"
    confirmations_value = ", ".join(confirmations) if confirmations else "None"
    embed = {
        "title": title,
        "fields": [
            {"name": "Symbol", "value": symbol, "inline": True},
            {"name": "Timeframe", "value": timeframe, "inline": True},
            {"name": "Pivot", "value": pivot_ts, "inline": False},
            {"name": "Confirmations", "value": confirmations_value, "inline": False},
            {"name": "Reason", "value": reason, "inline": False},
        ],
        "color": 3066993 if signal_type == "bullish" else 15158332,
    }
    return {"embeds": [embed]}


async def send_discord_alert(
    webhook_url: Optional[str],
    payload: Dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Send an alert to a Discord webhook or print payload if dry_run."""

    if dry_run:
        logger.info("DRY_RUN enabled. Payload: %s", json.dumps(payload))
        return

    if not webhook_url:
        raise ValueError("Discord webhook URL is not configured")

    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload, timeout=15) as resp:
            if resp.status >= 300:
                text = await resp.text()
                raise RuntimeError(
                    f"Discord webhook failed ({resp.status}): {text}"
                )
