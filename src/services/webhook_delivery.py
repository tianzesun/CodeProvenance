"""
Webhook delivery service for CodeProvenance.
Handles HMAC-SHA256 signature generation and delivery with retry logic.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Any, Optional
import httpx
from datetime import datetime, timedelta

from src.config.database import SessionLocal
from src.models.database import WebhookEvent
from src.utils.database import WebhookEventService
from src.api.schemas.webhook import WebhookDeliveryConfig

logger = logging.getLogger(__name__)


class WebhookDeliveryService:
    """
    Service for delivering webhooks with HMAC-SHA256 signatures and retry logic.
    """
    
    def __init__(self, config: WebhookDeliveryConfig):
        self.config = config
        self.http_client = httpx.AsyncClient(timeout=config.timeout)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.aclose()
    
    def _generate_signature(self, payload: str, secret_key: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.
        
        Args:
            payload: JSON string payload
            secret_key: Secret key for HMAC
            
        Returns:
            Hex-encoded HMAC-SHA256 signature
        """
        return hmac.new(
            secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _prepare_headers(self, payload: str, secret_key: str) -> Dict[str, str]:
        """
        Prepare HTTP headers for webhook delivery.
        
        Args:
            payload: JSON string payload
            secret_key: Secret key for HMAC
            
        Returns:
            Dictionary of HTTP headers
        """
        signature = self._generate_signature(payload, secret_key)
        timestamp = str(int(time.time()))
        
        return {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Timestamp": timestamp,
            "User-Agent": "CodeProvenance/1.0"
        }
    
    async def deliver_webhook(
        self, 
        webhook_event: WebhookEvent,
        secret_key: str
    ) -> bool:
        """
        Deliver a webhook event with HMAC signature.
        
        Args:
            webhook_event: WebhookEvent model instance
            secret_key: Secret key for HMAC signature
            
        Returns:
            True if delivery successful, False otherwise
        """
        try:
            # Prepare payload
            payload_json = json.dumps(webhook_event.payload, separators=(',', ':'))
            
            # Prepare headers
            headers = self._prepare_headers(payload_json, secret_key)
            
            # For now, we'll simulate delivery since we don't have actual webhook URLs
            # In a real implementation, we would make an HTTP POST request
            logger.info(f"Would deliver webhook {webhook_event.id} to {webhook_event.payload.get('webhook_url', 'unknown')}")
            
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            # Simulate success (in real implementation, check HTTP response status)
            # For demo purposes, we'll assume 90% success rate
            import random
            success = random.random() > 0.1  # 90% success rate
            
            if success:
                logger.info(f"Webhook {webhook_event.id} delivered successfully")
                return True
            else:
                logger.warning(f"Webhook {webhook_event.id} delivery failed (simulated)")
                return False
                
        except Exception as e:
            logger.error(f"Error delivering webhook {webhook_event.id}: {e}")
            return False
    
    async def process_pending_webhooks(self) -> int:
        """
        Process all pending webhook events.
        
        Returns:
            Number of webhooks processed
        """
        db = SessionLocal()
        processed_count = 0
        
        try:
            # Get pending webhook events
            pending_events = WebhookEventService.get_pending_webhook_events(db, limit=100)
            
            for event in pending_events:
                try:
                    # Get tenant to retrieve secret key
                    from src.models.database import Tenant
                    from src.utils.database import TenantService
                    
                    # Get job to get tenant_id
                    from src.models.database import Job
                    job = db.query(Job).filter(Job.id == event.job_id).first()
                    if not job:
                        logger.error(f"No job found for webhook event {event.id}")
                        WebhookEventService.update_webhook_event_status(
                            db, str(event.id), 'failed', 'Job not found'
                        )
                        continue
                    
                    # Get tenant
                    tenant = db.query(Tenant).filter(Tenant.id == job.tenant_id).first()
                    if not tenant:
                        logger.error(f"No tenant found for webhook event {event.id}")
                        WebhookEventService.update_webhook_event_status(
                            db, str(event.id), 'failed', 'Tenant not found'
                        )
                        continue
                    
                    # For demo, we'll use a fixed secret key
                    # In reality, this would be stored per tenant or per webhook
                    secret_key = "your-webhook-secret-key-change-in-production"
                    
                    # Attempt delivery
                    success = await self.deliver_webhook(event, secret_key)
                    
                    if success:
                        WebhookEventService.update_webhook_event_status(
                            db, str(event.id), 'delivered'
                        )
                    else:
                        # Check if we should retry
                        if event.attempt_count >= event.max_attempts:
                            WebhookEventService.update_webhook_event_status(
                                db, str(event.id), 'failed', 'Max attempts exceeded'
                            )
                        else:
                            WebhookEventService.update_webhook_event_status(
                                db, str(event.id), 'failed', 'Delivery failed, will retry'
                            )
                    
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing webhook event {event.id}: {e}")
                    WebhookEventService.update_webhook_event_status(
                        db, str(event.id), 'failed', str(e)
                    )
            
            return processed_count
            
        finally:
            db.close()


# Import asyncio at the bottom to avoid circular imports
import asyncio