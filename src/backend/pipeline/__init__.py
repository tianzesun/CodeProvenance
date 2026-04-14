"""
Pipeline Module - Orchestration Only (No Logic)

This module orchestrates processing steps only.
It does NOT contain business logic, metrics computation, or execution engines.

Responsibility: DAG orchestration, workflow management, batch processing
"""

from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


class StepStatus(Enum):
    """Pipeline step status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a pipeline step."""
    step_name: str
    status: StepStatus
    data: Any
    metadata: Dict[str, Any]
    error: Optional[str] = None


class PipelineStep(ABC):
    """Base class for pipeline steps."""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
    
    @abstractmethod
    def execute(self, input_data: Any) -> StepResult:
        """Execute the step."""
        pass
    
    def validate_input(self, input_data: Any) -> List[str]:
        """Validate input data."""
        return []
    
    def validate_output(self, output_data: Any) -> List[str]:
        """Validate output data."""
        return []


class Pipeline:
    """Orchestrates pipeline steps."""
    
    def __init__(self, name: str, steps: List[PipelineStep]):
        self.name = name
        self.steps = steps
        self._results: Dict[str, StepResult] = {}
    
    def execute(self, input_data: Any) -> Dict[str, StepResult]:
        """Execute all steps in order."""
        current_data = input_data
        
        for step in self.steps:
            # Validate input
            errors = step.validate_input(current_data)
            if errors:
                result = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    data=None,
                    metadata={"errors": errors},
                    error=f"Input validation failed: {errors}"
                )
                self._results[step.name] = result
                return self._results
            
            # Execute step
            try:
                result = step.execute(current_data)
                self._results[step.name] = result
                
                if result.status == StepStatus.FAILED:
                    return self._results
                
                # Validate output
                errors = step.validate_output(result.data)
                if errors:
                    result.status = StepStatus.FAILED
                    result.error = f"Output validation failed: {errors}"
                    return self._results
                
                current_data = result.data
                
            except Exception as e:
                result = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    data=None,
                    metadata={"exception": str(e)},
                    error=f"Step execution failed: {str(e)}"
                )
                self._results[step.name] = result
                return self._results
        
        return self._results
    
    def get_result(self, step_name: str) -> Optional[StepResult]:
        """Get result of a specific step."""
        return self._results.get(step_name)
    
    def get_all_results(self) -> Dict[str, StepResult]:
        """Get all step results."""
        return self._results.copy()


class AsyncPipeline:
    """Asynchronous pipeline orchestrator."""
    
    def __init__(self, name: str, steps: List[PipelineStep], max_workers: int = 4):
        self.name = name
        self.steps = steps
        self.max_workers = max_workers
        self._results: Dict[str, StepResult] = {}
    
    async def execute(self, input_data: Any) -> Dict[str, StepResult]:
        """Execute steps asynchronously."""
        current_data = input_data
        
        for step in self.steps:
            # Validate input
            errors = step.validate_input(current_data)
            if errors:
                result = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    data=None,
                    metadata={"errors": errors},
                    error=f"Input validation failed: {errors}"
                )
                self._results[step.name] = result
                return self._results
            
            # Execute step asynchronously
            try:
                result = await asyncio.to_thread(step.execute, current_data)
                self._results[step.name] = result
                
                if result.status == StepStatus.FAILED:
                    return self._results
                
                # Validate output
                errors = step.validate_output(result.data)
                if errors:
                    result.status = StepStatus.FAILED
                    result.error = f"Output validation failed: {errors}"
                    return self._results
                
                current_data = result.data
                
            except Exception as e:
                result = StepResult(
                    step_name=step.name,
                    status=StepStatus.FAILED,
                    data=None,
                    metadata={"exception": str(e)},
                    error=f"Step execution failed: {str(e)}"
                )
                self._results[step.name] = result
                return self._results
        
        return self._results


class BatchPipeline:
    """Batch processing pipeline."""
    
    def __init__(self, name: str, steps: List[PipelineStep], batch_size: int = 100):
        self.name = name
        self.steps = steps
        self.batch_size = batch_size
        self._results: Dict[str, StepResult] = {}
    
    def execute_batch(self, input_items: List[Any]) -> List[Dict[str, StepResult]]:
        """Execute pipeline on batch of items."""
        all_results = []
        
        for i in range(0, len(input_items), self.batch_size):
            batch = input_items[i:i + self.batch_size]
            batch_results = []
            
            for item in batch:
                pipeline = Pipeline(f"{self.name}_batch_{i}", self.steps)
                results = pipeline.execute(item)
                batch_results.append(results)
            
            all_results.extend(batch_results)
        
        return all_results


class PipelineRegistry:
    """Registry for pipelines."""
    
    def __init__(self):
        self._pipelines: Dict[str, Pipeline] = {}
    
    def register(self, name: str, pipeline: Pipeline) -> None:
        """Register a pipeline."""
        self._pipelines[name] = pipeline
    
    def get(self, name: str) -> Optional[Pipeline]:
        """Get a pipeline by name."""
        return self._pipelines.get(name)
    
    def list_pipelines(self) -> List[str]:
        """List all registered pipelines."""
        return list(self._pipelines.keys())


# Global pipeline registry
registry = PipelineRegistry()


def get_pipeline(name: str) -> Optional[Pipeline]:
    """Get a pipeline by name."""
    return registry.get(name)


def register_pipeline(name: str):
    """Decorator to register a pipeline."""
    def decorator(pipeline_class):
        registry.register(name, pipeline_class)
        return pipeline_class
    return decorator