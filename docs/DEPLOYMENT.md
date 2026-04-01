# IntegrityDesk Deployment Guide

## Staging Deployment Instructions

### Prerequisites
- Docker and Docker Compose installed
- Access to PostgreSQL database (Neon or local)
- Redis instance available
- Environment variables configured

### Environment Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   ```env
   DATABASE_URL=postgresql://user:password@host:port/dbname
   REDIS_URL=redis://localhost:6379
   WEBHOOK_SECRET_KEY=your-secret-key-here
   ```

### Local Development Deployment

For local testing and development:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment Considerations

For production deployment, consider:

1. **Scaling**
   - Increase API replicas based on traffic
   - Scale workers based on queue depth
   - Use managed PostgreSQL and Redis services

2. **Security**
   - Use strong secrets for webhook signatures
   - Enable HTTPS/TLS termination at load balancer
   - Regularly rotate API keys and secrets
   - Implement proper CORS policies

3. **Monitoring**
   - Set up health checks for all services
   - Monitor API response times and error rates
   - Track webhook delivery success/failure rates
   - Monitor database connection pool usage

4. **Backup Strategy**
   - Regular PostgreSQL backups
   - Redis persistence configuration
   - Test restore procedures periodically

### Kubernetes Deployment (Optional)

For Kubernetes deployment, you would:
1. Create Deployment manifests for API and workers
2. Create Services for internal communication
3. Configure Ingress for external access
4. Set up ConfigMaps and Secrets for configuration
5. Use HorizontalPodAutoscaler for scaling

### Testing the Deployment

After deployment, verify:

1. Health check endpoint:
   ```bash
   curl http://localhost:8000/health
   # Should return {"status": "healthy"}
   ```

2. API documentation:
   ```bash
   curl http://localhost:8000/docs
   # Should return Swagger UI HTML
   ```

3. Authentication:
   ```bash
   curl -H "Authorization: Bearer YOUR_API_KEY" http://localhost:8000/api/v1/
   # Should return API information
   ```

### Troubleshooting

Common issues and solutions:

1. **Database connection failures**
   - Verify DATABASE_URL is correct
   - Check network connectivity to database
   - Ensure database accepts connections from your IP

2. **Redis connection failures**
   - Verify REDIS_URL is correct
   - Check Redis is running and accessible
   - Ensure proper password/authentication if required

3. **Webhook delivery failures**
   - Check webhook URL is accessible
   - Verify HMAC secret key matches between sender and receiver
   - Check firewall rules allow outbound HTTP requests

4. **Performance issues**
   - Monitor CPU/memory usage of containers
   - Check database query performance
   - Consider adding database indexes for frequent queries
   - Review rate limiting configurations

## Next Steps

After successful staging deployment:
1. Run comprehensive test suite against staging environment
2. Monitor performance and error rates
3. Gather feedback from pilot users
4. Plan production rollout with blue/green or canary deployment