# Technology Choices Justification

## Why Celery + Redis (Not MongoDB)

### Celery Broker Options Comparison

| Feature | Redis | MongoDB | RabbitMQ |
|---------|-------|---------|----------|
| **Performance** | Excellent (in-memory) | Good (disk-based) | Excellent |
| **Persistence** | Optional (RDB/AOF) | Built-in | Optional |
| **Setup Complexity** | Low | Medium | Medium |
| **Monitoring** | Good (Redis CLI) | Good (MongoDB tools) | Excellent |
| **Cloud Support** | Excellent (ElastiCache, Azure Redis) | Excellent (Atlas, mLab) | Good (AWS MQ, CloudAMQP) |
| **Use Case Fit** | Ideal for task queues | Better for document storage | Ideal for complex routing |

### Why We Chose Redis for Celery

1. **Speed**: In-memory operations for queue operations are faster than disk-based MongoDB
2. **Simplicity**: Redis has simpler setup and maintenance for queue workloads
3. **Features**: Supports pub/sub, blocking operations, and atomic operations needed for task queues
4. **Cost**: Generally lower cost for equivalent performance
5. **Ecosystem**: Celery has excellent first-class support for Redis as a broker

### Why We Chose PostgreSQL (Not MongoDB) for Primary Data

| Requirement | PostgreSQL | MongoDB |
|-------------|------------|---------|
| **ACID Transactions** | ✅ Full support | ❌ Limited (multi-document transactions added later) |
| **Relational Data** | ✅ Natural fit for tenants/jobs/submissions | ❌ Requires embedding or referencing |
| **JSON Support** | ✅ JSONB with indexing | ✅ Native BSON |
| **Aggregation Queries** | ✅ SQL + JSONB functions | ✅ Aggregation pipeline |
| **Schema Evolution** | ✅ ALTER TABLE, nullable columns | ✅ Flexible schema |
| **Maturity** | ✅ Decades of battle-testing | ✅ Growing but younger |

### Our Hybrid Approach

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA STORAGE LAYER                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ PostgreSQL      │  │ Redis           │  │ S3/Local    │ │
│  │ (Primary DB)    │  │ (Broker/Cache)  │  │ (File Store)│ │
│  │ - Tenants       │  │ - Celery Broker │  │ - Uploads   │ │
│  │ - Jobs          │  │ - Rate Limits   │  │ - Results   │ │
│  │ - Results       │  │ - Idempotency   │  │             │ │
│  │ - Usage Metrics │  │ - Webhook Queue │  │             │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Conclusion

- **Celery Broker**: Redis (not MongoDB) - optimized for queue performance
- **Primary Database**: PostgreSQL (not MongoDB) - ACID compliance and relational integrity
- **File Storage**: S3/Local - for large binary objects (submission files)
- **Cache**: Redis - for fast access to rate limits, idempotency keys

This combination gives us:
- High performance queue processing
- Strong data consistency for billing and tenant isolation
- Cost-effective storage for large files
- Flexibility to scale each component independently
