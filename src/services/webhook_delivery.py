"""Simplified webhook delivery service used by the test suite."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import random
import time
from typing import Any, Dict

from src.api.schemas.webhook import WebhookDeliveryConfig


class WebhookDeliveryService:
    """Prepare and simulate webhook deliveries."""

    def __init__(self, config: WebhookDeliveryConfig) -> None:
        self.config = config

    def _generate_signature(self, payload: str, secret: str) -> str:
        return hmac.new(
            secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _prepare_headers(self, payload: str, secret: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Webhook-Signature": self._generate_signature(payload, secret),
            "X-Webhook-Timestamp": str(int(time.time())),
            "User-Agent": "IntegrityDesk/1.0",
        }

    async def deliver_webhook(self, event: Any, secret: str) -> bool:
        """Simulate a webhook delivery outcome."""
        try:
            payload = json.dumps(event.payload, separators=(",", ":"), default=str)
            self._prepare_headers(payload, secret)
            await asyncio.sleep(0)
            return random.random() >= 0.1
        except Exception:
            return False
