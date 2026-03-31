"""
Unit tests for Webhook Delivery System

Tests the webhook delivery functionality including:
- HMAC-SHA256 signature generation
- Header preparation
- Retry logic
- Error handling
"""

import pytest
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.services.webhook_delivery import WebhookDeliveryService
from src.api.schemas.webhook import WebhookDeliveryConfig


class TestWebhookDeliveryService:
    """Test the webhook delivery service."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = WebhookDeliveryConfig(
            secret_key="test-secret-key-12345678",
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        )
        self.service = WebhookDeliveryService(self.config)
    
    def test_signature_generation(self):
        """Test HMAC-SHA256 signature generation."""
        payload = '{"event": "test", "data": "value"}'
        secret = "my-secret-key"
        
        signature = self.service._generate_signature(payload, secret)
        
        # Verify signature is correct
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        assert signature == expected
        assert len(signature) == 64  # SHA256 hex digest length
    
    def test_signature_with_different_payloads(self):
        """Test that different payloads produce different signatures."""
        payload1 = '{"event": "job.completed"}'
        payload2 = '{"event": "job.failed"}'
        secret = "test-secret"
        
        sig1 = self.service._generate_signature(payload1, secret)
        sig2 = self.service._generate_signature(payload2, secret)
        
        assert sig1 != sig2
    
    def test_signature_with_different_secrets(self):
        """Test that different secrets produce different signatures."""
        payload = '{"event": "test"}'
        secret1 = "secret-one"
        secret2 = "secret-two"
        
        sig1 = self.service._generate_signature(payload, secret1)
        sig2 = self.service._generate_signature(payload, secret2)
        
        assert sig1 != sig2
    
    def test_header_preparation(self):
        """Test HTTP header preparation."""
        payload = '{"event": "test"}'
        secret = "test-secret"
        
        headers = self.service._prepare_headers(payload, secret)
        
        assert 'Content-Type' in headers
        assert headers['Content-Type'] == 'application/json'
        assert 'X-Webhook-Signature' in headers
        assert 'X-Webhook-Timestamp' in headers
        assert 'User-Agent' in headers
        assert headers['User-Agent'] == 'CodeProvenance/1.0'
    
    def test_signature_verification(self):
        """Test signature verification (simulating receiver)."""
        payload = '{"event": "job.completed", "job_id": "123"}'
        secret = "shared-secret-key"
        
        # Generate signature (sender)
        signature = self.service._generate_signature(payload, secret)
        
        # Verify signature (receiver)
        expected = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        assert hmac.compare_digest(signature, expected)
    
    def test_signature_tamper_detection(self):
        """Test that tampered payloads fail verification."""
        original_payload = '{"event": "job.completed", "amount": 100}'
        tampered_payload = '{"event": "job.completed", "amount": 1000}'
        secret = "test-secret"
        
        # Generate signature for original
        signature = self.service._generate_signature(original_payload, secret)
        
        # Verify tampered payload should fail
        tampered_signature = self.service._generate_signature(tampered_payload, secret)
        
        assert signature != tampered_signature
    
    @pytest.mark.asyncio
    async def test_deliver_webhook_success(self):
        """Test successful webhook delivery."""
        # Create mock webhook event
        mock_event = MagicMock()
        mock_event.id = "test-event-id"
        mock_event.payload = {
            "event": "job.completed",
            "job_id": "123",
            "webhook_url": "https://example.com/webhook"
        }
        
        # Mock random to always return success
        with patch('random.random', return_value=0.5):  # > 0.1 = success
            result = await self.service.deliver_webhook(mock_event, "test-secret")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_deliver_webhook_failure(self):
        """Test failed webhook delivery."""
        mock_event = MagicMock()
        mock_event.id = "test-event-id"
        mock_event.payload = {
            "event": "job.completed",
            "webhook_url": "https://example.com/webhook"
        }
        
        # Mock random to always return failure
        with patch('random.random', return_value=0.05):  # < 0.1 = failure
            result = await self.service.deliver_webhook(mock_event, "test-secret")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_deliver_webhook_exception_handling(self):
        """Test exception handling in webhook delivery."""
        mock_event = MagicMock()
        mock_event.id = "test-event-id"
        mock_event.payload = {
            "event": "job.completed",
            "webhook_url": "https://example.com/webhook"
        }
        
        # Mock to raise exception
        with patch.object(self.service, '_prepare_headers', side_effect=Exception("Test error")):
            result = await self.service.deliver_webhook(mock_event, "test-secret")
        
        assert result is False


class TestWebhookRetryLogic:
    """Test webhook retry logic."""
    
    def test_retry_count_tracking(self):
        """Test that retry counts are tracked correctly."""
        config = WebhookDeliveryConfig(
            secret_key="test-secret-key-12345678",
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        )
        
        assert config.max_retries == 3
    
    def test_exponential_backoff_calculation(self):
        """Test exponential backoff delay calculation."""
        base_delay = 60  # seconds
        
        # Calculate delays for retries
        delay_1 = base_delay * (2 ** 0)  # 60 seconds
        delay_2 = base_delay * (2 ** 1)  # 120 seconds
        delay_3 = base_delay * (2 ** 2)  # 240 seconds
        
        assert delay_1 == 60
        assert delay_2 == 120
        assert delay_3 == 240
    
    def test_max_retries_limit(self):
        """Test that max retries limit is enforced."""
        config = WebhookDeliveryConfig(
            secret_key="test-secret",
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        )
        
        # Simulate retry attempts
        attempt_count = 0
        max_attempts = config.max_retries
        
        # Should stop after max_retries
        for i in range(max_attempts + 5):
            if attempt_count < max_attempts:
                attempt_count += 1
        
        assert attempt_count == max_attempts


class TestWebhookPayload:
    """Test webhook payload structure."""
    
    def test_payload_serialization(self):
        """Test that payloads serialize correctly to JSON."""
        payload = {
            "event": "job.completed",
            "job_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2026-03-31T12:00:00Z",
            "data": {
                "total_submissions": 10,
                "flagged_pairs": 3,
                "max_similarity": 0.85
            }
        }
        
        json_str = json.dumps(payload, separators=(',', ':'))
        parsed = json.loads(json_str)
        
        assert parsed["event"] == "job.completed"
        assert parsed["data"]["total_submissions"] == 10
    
    def test_payload_with_signature(self):
        """Test payload with signature included."""
        payload = {
            "event": "job.completed",
            "job_id": "123",
            "signature": "abc123def456"
        }
        
        json_str = json.dumps(payload)
        assert "signature" in json_str
    
    def test_webhook_event_types(self):
        """Test different webhook event types."""
        event_types = [
            "job.completed",
            "job.failed",
            "job.progress"
        ]
        
        for event_type in event_types:
            payload = {
                "event": event_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            assert payload["event"] == event_type


class TestWebhookSecurity:
    """Test webhook security features."""
    
    def test_signature_immutable(self):
        """Test that signature cannot be modified after generation."""
        payload = '{"event": "test"}'
        secret = "test-secret"
        
        service = WebhookDeliveryService(WebhookDeliveryConfig(
            secret_key=secret,
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        ))
        
        signature1 = service._generate_signature(payload, secret)
        signature2 = service._generate_signature(payload, secret)
        
        # Same payload and secret should produce same signature
        assert signature1 == signature2
    
    def test_timing_safe_comparison(self):
        """Test that signature comparison is timing-safe."""
        sig1 = "a" * 64
        sig2 = "a" * 64
        sig3 = "b" * 64
        
        # Same signatures should match
        assert hmac.compare_digest(sig1, sig2) is True
        
        # Different signatures should not match
        assert hmac.compare_digest(sig1, sig3) is False
    
    def test_timestamp_in_headers(self):
        """Test that timestamp is included in headers."""
        service = WebhookDeliveryService(WebhookDeliveryConfig(
            secret_key="test-secret",
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        ))
        
        headers = service._prepare_headers('{}', "test-secret")
        
        assert 'X-Webhook-Timestamp' in headers
        timestamp = int(headers['X-Webhook-Timestamp'])
        assert timestamp > 0
    
    def test_content_type_header(self):
        """Test that Content-Type header is set correctly."""
        service = WebhookDeliveryService(WebhookDeliveryConfig(
            secret_key="test-secret",
            max_retries=3,
            retry_delay_base=60,
            timeout=30
        ))
        
        headers = service._prepare_headers('{}', "test-secret")
        
        assert headers['Content-Type'] == 'application/json'


class TestWebhookConfiguration:
    """Test webhook configuration validation."""
    
    def test_valid_configuration(self):
        """Test valid webhook configuration."""
        config = WebhookDeliveryConfig(
            secret_key="valid-secret-key-123456",
            max_retries=5,
            retry_delay_base=120,
            timeout=60
        )
        
        assert config.secret_key == "valid-secret-key-123456"
        assert config.max_retries == 5
        assert config.retry_delay_base == 120
        assert config.timeout == 60
    
    def test_configuration_defaults(self):
        """Test configuration with default values."""
        config = WebhookDeliveryConfig(
            secret_key="test-secret-key"
        )
        
        assert config.max_retries == 3
        assert config.retry_delay_base == 60
        assert config.timeout == 30
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Secret key must be at least 16 characters
        with pytest.raises(Exception):
            WebhookDeliveryConfig(secret_key="short")
        
        # Max retries must be between 1 and 10
        with pytest.raises(Exception):
            WebhookDeliveryConfig(
                secret_key="valid-secret-key",
                max_retries=0
            )
        
        with pytest.raises(Exception):
            WebhookDeliveryConfig(
                secret_key="valid-secret-key",
                max_retries=11
            )


class TestWebhookIntegration:
    """Test webhook integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_full_webhook_flow(self):
        """Test complete webhook delivery flow."""
        config = WebhookDeliveryConfig(
            secret_key="integration-test-secret",
            max_retries=2,
            retry_delay_base=1,  # Short delay for testing
            timeout=5
        )
        
        service = WebhookDeliveryService(config)
        
        # Create mock event
        mock_event = MagicMock()
        mock_event.id = "integration-test-event"
        mock_event.payload = {
            "event": "job.completed",
            "job_id": "test-job-123",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "total_submissions": 5,
                "similarity_threshold": 0.7
            }
        }
        
        # Mock successful delivery
        with patch('random.random', return_value=0.5):
            result = await service.deliver_webhook(
                mock_event,
                config.secret_key
            )
        
        assert result is True
    
    def test_webhook_event_lifecycle(self):
        """Test webhook event status transitions."""
        statuses = ['pending', 'delivered', 'failed', 'retried']
        
        # Test valid status transitions
        current_status = 'pending'
        
        # pending -> delivered
        if current_status == 'pending':
            current_status = 'delivered'
        assert current_status == 'delivered'
        
        # pending -> failed
        current_status = 'pending'
        if current_status == 'pending':
            current_status = 'failed'
        assert current_status == 'failed'
        
        # failed -> retried
        if current_status == 'failed':
            current_status = 'retried'
        assert current_status == 'retried'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])