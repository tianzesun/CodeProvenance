# Load Testing for IntegrityDesk

This directory contains load testing scripts for the plagiarism detection system.

## Prerequisites

Install load testing dependencies:

```bash
pip install -r requirements-load-test.txt
```

## Running Locust Tests

```bash
# Run with default settings (100 users, 10 spawn rate, 1 min run time)
locust -f src/backend/load_tests/locustfile.py

# Run with command line options
locust -f src/backend/load_tests/locustfile.py --host http://localhost:8000 --users 200 --spawn-rate 20 --run-time 5m

# Run headless mode
locust -f src/backend/load_tests/locustfile.py --headless --users 100 --spawn-rate 10 --run-time 1m --expect-workers 4
```

## Running k6 Tests

```bash
# Run k6 test
k6 run src/backend/load_tests/load_test.js

# Run with custom thresholds
k6 run --vus 100 --duration 2m src/backend/load_tests/load_test.js
```

## Test Scenarios

1. **Small File Similarity** (50% weight)
   - Small Python code snippets
   - High throughput scenario

2. **Medium File Similarity** (30% weight)
   - Medium-sized code files
   - Tests moderate load

3. **Results Fetch** (10% weight)
   - Fetch recent results
   - Tests read performance

4. **Health Check** (5% weight)
   - Health endpoint
   - Baseline performance check

## Thresholds

- p95 response time: < 500ms
- p99 response time: < 1000ms
- Error rate: < 1%
- Max requests per second: 50

## Monitoring

The tests include:
- Response time tracking
- Error counting
- Verdict validation