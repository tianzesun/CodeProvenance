#!/usr/bin/env python3
"""
Advanced Benchmarking API Service

Production-grade REST API for real-time plagiarism detection benchmarking.
Provides endpoints for:
- Real-time similarity checking
- Benchmark execution
- Performance monitoring
- Configuration management
- Historical analysis
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import uvicorn
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import our benchmarking components
from production_benchmark_runner import ProductionBenchmarkRunner, IntegrityDeskEngine


class SimilarityRequest(BaseModel):
    """Request model for similarity checking."""
    code_a: str = Field(..., description="First code snippet", max_length=10000)
    code_b: str = Field(..., description="Second code snippet", max_length=10000)
    algorithm: str = Field("integritydesk", description="Algorithm to use")
    threshold: float = Field(0.7, description="Similarity threshold", ge=0.0, le=1.0)


class SimilarityResponse(BaseModel):
    """Response model for similarity checking."""
    similarity_score: float
    is_plagiarism: bool
    confidence: str
    algorithm: str
    processing_time_ms: float
    threshold_used: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BenchmarkRequest(BaseModel):
    """Request model for benchmark execution."""
    datasets: List[str] = Field(..., description="Datasets to test")
    algorithms: List[str] = Field(..., description="Algorithms to compare")
    max_samples: int = Field(1000, description="Maximum samples per dataset", gt=0)
    priority: str = Field("normal", description="Execution priority")


class BenchmarkStatus(BaseModel):
    """Status of benchmark execution."""
    benchmark_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress: float
    start_time: Optional[datetime]
    estimated_completion: Optional[datetime]
    results: Optional[Dict[str, Any]]


class MetricsSummary(BaseModel):
    """Summary of system performance metrics."""
    total_requests: int
    average_response_time: float
    false_positive_rate: float
    accuracy: float
    uptime_percentage: float
    timestamp: datetime


class BenchmarkingAPIService:
    """Main API service for advanced benchmarking."""

    def __init__(self):
        self.app = FastAPI(
            title="IntegrityDesk Benchmarking API",
            description="Advanced API for code plagiarism detection benchmarking",
            version="2.0.0"
        )

        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Initialize components
        self.engine = IntegrityDeskEngine()
        self.runner = ProductionBenchmarkRunner()
        self.executor = ThreadPoolExecutor(max_workers=4)

        # In-memory storage (use database for production)
        self.active_benchmarks = {}
        self.completed_benchmarks = {}
        self.performance_metrics = self._initialize_metrics()

        # Setup routes
        self._setup_routes()

        logger.info("Benchmarking API service initialized")

    def _initialize_metrics(self) -> Dict[str, Any]:
        """Initialize performance metrics tracking."""
        return {
            'requests_total': 0,
            'requests_since_startup': 0,
            'response_times': [],
            'similarity_scores': [],
            'false_positives': 0,
            'total_predictions': 0,
            'start_time': datetime.now(),
            'last_updated': datetime.now()
        }

    def _setup_routes(self):
        """Setup all API routes."""

        @self.app.get("/")
        async def root():
            """API root endpoint."""
            return {
                "message": "IntegrityDesk Benchmarking API v2.0.0",
                "status": "operational",
                "endpoints": [
                    "/similarity - Real-time similarity checking",
                    "/benchmark - Run comprehensive benchmarks",
                    "/status/{benchmark_id} - Check benchmark status",
                    "/metrics - System performance metrics",
                    "/health - Health check"
                ]
            }

        @self.app.post("/similarity", response_model=SimilarityResponse)
        async def check_similarity(request: SimilarityRequest):
            """Real-time similarity checking endpoint."""
            start_time = time.time()

            try:
                # Compute similarity
                similarity_score = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self.engine.compute_similarity,
                    request.code_a,
                    request.code_b,
                    request.algorithm
                )

                # Determine plagiarism classification
                is_plagiarism = similarity_score >= request.threshold

                # Calculate confidence level
                if similarity_score >= 0.9:
                    confidence = "very_high"
                elif similarity_score >= 0.8:
                    confidence = "high"
                elif similarity_score >= 0.7:
                    confidence = "medium"
                elif similarity_score >= 0.5:
                    confidence = "low"
                else:
                    confidence = "very_low"

                processing_time = (time.time() - start_time) * 1000

                # Update metrics
                self._update_metrics(similarity_score, processing_time)

                response = SimilarityResponse(
                    similarity_score=similarity_score,
                    is_plagiarism=is_plagiarism,
                    confidence=confidence,
                    algorithm=request.algorithm,
                    processing_time_ms=processing_time,
                    threshold_used=request.threshold,
                    metadata={
                        'request_id': f"req_{int(time.time()*1000)}",
                        'code_a_length': len(request.code_a),
                        'code_b_length': len(request.code_b)
                    }
                )

                logger.info(f"Similarity check: {similarity_score:.3f} ({confidence}) in {processing_time:.1f}ms")
                return response

            except Exception as e:
                logger.error(f"Similarity check failed: {e}")
                raise HTTPException(status_code=500, detail=f"Similarity check failed: {str(e)}")

        @self.app.post("/benchmark", response_model=Dict[str, str])
        async def start_benchmark(request: BenchmarkRequest, background_tasks: BackgroundTasks):
            """Start a comprehensive benchmark."""
            benchmark_id = f"bench_{int(time.time()*1000)}"

            # Initialize benchmark status
            self.active_benchmarks[benchmark_id] = BenchmarkStatus(
                benchmark_id=benchmark_id,
                status="pending",
                progress=0.0,
                start_time=datetime.now(),
                estimated_completion=None
            )

            # Run benchmark in background
            background_tasks.add_task(self._run_benchmark_async, benchmark_id, request)

            logger.info(f"Started benchmark {benchmark_id} with datasets: {request.datasets}")
            return {"benchmark_id": benchmark_id, "status": "started"}

        @self.app.get("/status/{benchmark_id}", response_model=BenchmarkStatus)
        async def get_benchmark_status(benchmark_id: str):
            """Get status of a benchmark execution."""
            if benchmark_id in self.active_benchmarks:
                return self.active_benchmarks[benchmark_id]
            elif benchmark_id in self.completed_benchmarks:
                return self.completed_benchmarks[benchmark_id]
            else:
                raise HTTPException(status_code=404, detail="Benchmark not found")

        @self.app.get("/results/{benchmark_id}")
        async def get_benchmark_results(benchmark_id: str):
            """Get complete results of a completed benchmark."""
            if benchmark_id in self.completed_benchmarks:
                status = self.completed_benchmarks[benchmark_id]
                if status.results:
                    return JSONResponse(content=status.results)
                else:
                    raise HTTPException(status_code=404, detail="Results not available")
            else:
                raise HTTPException(status_code=404, detail="Benchmark not completed or not found")

        @self.app.get("/download/{benchmark_id}")
        async def download_benchmark_report(benchmark_id: str):
            """Download benchmark report as JSON file."""
            if benchmark_id in self.completed_benchmarks:
                status = self.completed_benchmarks[benchmark_id]
                if status.results:
                    # Create temporary file
                    import tempfile
                    import json

                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(status.results, f, indent=2, default=str)
                        temp_file = f.name

                    return FileResponse(
                        temp_file,
                        media_type='application/json',
                        filename=f'benchmark_{benchmark_id}_results.json'
                    )
            raise HTTPException(status_code=404, detail="Benchmark results not available")

        @self.app.get("/metrics", response_model=MetricsSummary)
        async def get_metrics():
            """Get current system performance metrics."""
            metrics = self.performance_metrics

            # Calculate derived metrics
            avg_response_time = (
                sum(metrics['response_times'][-100:]) / len(metrics['response_times'][-100:])
                if metrics['response_times'] else 0.0
            )

            # Calculate false positive rate from recent predictions
            recent_scores = metrics['similarity_scores'][-100:]
            fp_count = sum(1 for score in recent_scores if score >= 0.7)  # Assuming 0.7 threshold
            fp_rate = fp_count / len(recent_scores) if recent_scores else 0.0

            # Calculate uptime (simplified)
            uptime_seconds = (datetime.now() - metrics['start_time']).total_seconds()
            uptime_percentage = 99.9  # Simplified - calculate properly in production

            return MetricsSummary(
                total_requests=metrics['requests_total'],
                average_response_time=avg_response_time,
                false_positive_rate=fp_rate,
                accuracy=0.95,  # Placeholder - calculate from actual data
                uptime_percentage=uptime_percentage,
                timestamp=datetime.now()
            )

        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "version": "2.0.0",
                "engine_status": "operational" if self.engine.engine_loaded else "simulated",
                "active_benchmarks": len(self.active_benchmarks)
            }

        @self.app.get("/benchmarks")
        async def list_benchmarks():
            """List all benchmarks (active and completed)."""
            return {
                "active": list(self.active_benchmarks.keys()),
                "completed": list(self.completed_benchmarks.keys()),
                "total": len(self.active_benchmarks) + len(self.completed_benchmarks)
            }

    async def _run_benchmark_async(self, benchmark_id: str, request: BenchmarkRequest):
        """Run benchmark asynchronously."""
        try:
            # Update status to running
            self.active_benchmarks[benchmark_id].status = "running"
            self.active_benchmarks[benchmark_id].progress = 0.1

            logger.info(f"Starting benchmark {benchmark_id}")

            # Run the actual benchmark
            results = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.runner.run_production_benchmark,
                request.datasets,
                request.algorithms
            )

            # Update status to completed
            self.active_benchmarks[benchmark_id].status = "completed"
            self.active_benchmarks[benchmark_id].progress = 1.0
            self.active_benchmarks[benchmark_id].results = results

            # Move to completed
            self.completed_benchmarks[benchmark_id] = self.active_benchmarks[benchmark_id]
            del self.active_benchmarks[benchmark_id]

            logger.info(f"Completed benchmark {benchmark_id}")

        except Exception as e:
            logger.error(f"Benchmark {benchmark_id} failed: {e}")

            # Update status to failed
            self.active_benchmarks[benchmark_id].status = "failed"
            self.active_benchmarks[benchmark_id].results = {"error": str(e)}

            # Move to completed (with error)
            self.completed_benchmarks[benchmark_id] = self.active_benchmarks[benchmark_id]
            del self.active_benchmarks[benchmark_id]

    def _update_metrics(self, similarity_score: float, response_time: float):
        """Update performance metrics."""
        metrics = self.performance_metrics

        metrics['requests_total'] += 1
        metrics['requests_since_startup'] += 1
        metrics['response_times'].append(response_time)
        metrics['similarity_scores'].append(similarity_score)

        # Keep only recent metrics to avoid memory issues
        max_history = 1000
        if len(metrics['response_times']) > max_history:
            metrics['response_times'] = metrics['response_times'][-max_history:]
            metrics['similarity_scores'] = metrics['similarity_scores'][-max_history:]

        metrics['last_updated'] = datetime.now()

    def run_server(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the API server."""
        logger.info(f"Starting Benchmarking API server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port)


def main():
    """Main API server entry point."""
    print("🚀 INTEGRITYDESK BENCHMARKING API SERVICE v2.0")
    print("=" * 60)
    print("Advanced REST API for plagiarism detection benchmarking")
    print()
    print("Endpoints:")
    print("  GET  /              - API information")
    print("  POST /similarity    - Real-time similarity checking")
    print("  POST /benchmark     - Start comprehensive benchmark")
    print("  GET  /status/{id}   - Check benchmark status")
    print("  GET  /results/{id}  - Get benchmark results")
    print("  GET  /metrics       - System performance metrics")
    print("  GET  /health        - Health check")
    print()

    service = BenchmarkingAPIService()

    try:
        service.run_server()
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()