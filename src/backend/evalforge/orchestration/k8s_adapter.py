"""
Kubernetes Adapter - 100-node cluster execution backend.

Generates Kubernetes Job manifests for large-scale distributed execution.
Supports parallelism up to 100 workers for full benchmark runs.
"""

from typing import List, Dict, Any
import json
import uuid


class KubernetesAdapter:
    """
    Kubernetes backend adapter for large-scale benchmark execution.
    
    Generates Job manifests with configurable parallelism.
    """

    @staticmethod
    def generate_job_manifest(
        jobs: List[Dict[str, Any]],
        parallelism: int = 100,
        image: str = "evalforge/worker:latest"
    ) -> Dict[str, Any]:
        """
        Generate Kubernetes Job manifest for distributed execution.

        Args:
            jobs: List of micro-jobs to execute
            parallelism: Number of parallel workers
            image: Worker container image

        Returns:
            Kubernetes Job manifest
        """
        job_id = str(uuid.uuid4())[:8]

        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": f"evalforge-{job_id}",
                "labels": {
                    "app": "evalforge",
                    "job-type": "benchmark"
                }
            },
            "spec": {
                "parallelism": parallelism,
                "completions": len(jobs),
                "completionMode": "Indexed",
                "backoffLimit": 2,
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "worker",
                                "image": image,
                                "command": ["python", "-m", "evalforge.worker"],
                                "env": [
                                    {
                                        "name": "JOB_INDEX",
                                        "valueFrom": {
                                            "fieldRef": {
                                                "fieldPath": "metadata.annotations['batch.kubernetes.io/job-completion-index']"
                                            }
                                        }
                                    }
                                ],
                                "resources": {
                                    "limits": {
                                        "cpu": "1",
                                        "memory": "4Gi"
                                    },
                                    "requests": {
                                        "cpu": "500m",
                                        "memory": "2Gi"
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }

    @staticmethod
    def generate_configmap(jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate ConfigMap with job payloads."""
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": f"evalforge-jobs"
            },
            "data": {
                "jobs.json": json.dumps(jobs, indent=2)
            }
        }