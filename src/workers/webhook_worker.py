"""
Webhook delivery worker for IntegrityDesk.
Runs as a background process to deliver webhook events.
"""
import asyncio
import logging
import os
from typing import Optional

from src.services.webhook_delivery import WebhookDeliveryService
from src.api.schemas.webhook import WebhookDeliveryConfig

logger = logging.getLogger(__name__)


class WebhookWorker:
    """
    Background worker for processing webhook delivery queue.
    """
    
    def __init__(self, check_interval: int = 10):
        self.check_interval = check_interval  # seconds
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
        # Load configuration from environment
        self.config = WebhookDeliveryConfig(
            secret_key=os.getenv('WEBHOOK_SECRET_KEY', 'your-webhook-secret-key-change-in-production'),
            max_retries=int(os.getenv('WEBHOOK_MAX_RETRIES', '3')),
            retry_delay_base=int(os.getenv('WEBHOOK_RETRY_DELAY_BASE', '60')),
            timeout=int(os.getenv('WEBHOOK_TIMEOUT', '30'))
        )
    
    async def start(self):
        """Start the webhook worker."""
        if self.running:
            logger.warning("Webhook worker is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._run())
        logger.info("Webhook worker started")
    
    async def stop(self):
        """Stop the webhook worker."""
        if not self.running:
            logger.warning("Webhook worker is not running")
            return
        
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Webhook worker stopped")
    
    async def _run(self):
        """Main worker loop."""
        logger.info("Webhook worker loop started")
        
        while self.running:
            try:
                # Process pending webhooks
                async with WebhookDeliveryService(self.config) as service:
                    processed_count = await service.process_pending_webhooks()
                    
                    if processed_count > 0:
                        logger.info(f"Processed {processed_count} webhook events")
                
                # Wait before next check
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Webhook worker loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in webhook worker loop: {e}")
                # Wait a bit before retrying to avoid tight error loop
                await asyncio.sleep(min(self.check_interval, 30))


# For running as a standalone script
if __name__ == "__main__":
    import logging.config
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run worker
    worker = WebhookWorker()
    
    async def main():
        await worker.start()
        try:
            # Keep running until interrupted
            while worker.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await worker.stop()
    
    asyncio.run(main())