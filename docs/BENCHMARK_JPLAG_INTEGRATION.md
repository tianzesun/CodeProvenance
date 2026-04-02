# JPlag Benchmark Integration Requirements

## Current Status
JPlag benchmarking is **pending** due to build environment requirements.

## JPlag Source
Location: `tools/JPlag/`
Repository: https://github.com/jplag/jplag

## Build Requirements
- **Java version**: JDK 25+ (current server has JDK 21)
- **Build tool**: Apache Maven (installed)
- **Build command**: `mvn package -DskipTests`

## What's Needed to Integrate JPlag

### 1. Server with Java 25+
The current JPlag codebase targets Java 25. You need:
- A server with JDK 25 installed, OR
- Wait for JPlag to downgrade their requirements

### 2. After Building
Once JPlag CLI JAR is built, create a benchmark adapter:
```python
# benchmark/adapters/jplag_runner.py
class JPlagBenchmarkEngine(BaseSimilarityEngine):
    """Runs actual JPlag CLI for comparison."""
    
    def compare(self, code_a, code_b):
        # Write temp files, run JPlag CLI, parse output
        ...
```

### 3. Alternative Approach
A Python re-implementation of JPlag's Greedy String Tiling algorithm
exists at `benchmark/adapters/jplag_engine.py`. This can be used as a
proxy for benchmark testing but is NOT identical to JPlag.

## Steps to Enable
1. Provision server with Java 25+
2. Build JPlag: `cd tools/JPlag && mvn package -DskipTests`
3. Create adapter in `benchmark/adapters/jplag_runner.py`
4. Register engine in `benchmark/__init__.py`:
   ```python
   registry.register("jplag", JPlagBenchmarkEngine)
   ```
5. Run benchmark: `python -m benchmark run --config config/benchmark_jplag.yaml`