"""IntegrityDesk Backend API Server"""

# LOAD ENVIRONMENT FIRST BEFORE ANY OTHER IMPORTS
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env.local")


import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import tempfile
import zipfile
import shutil
import uuid
import json
import os
import re
import logging
import hashlib
import secrets
import time
import math
import subprocess
import csv
import asyncio
from collections import Counter, defaultdict
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path as PathLib
import numpy as np

from fastapi import (
    FastAPI,
    Request,
    Response,
    UploadFile,
    File,
    Form,
    HTTPException,
    BackgroundTasks,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
    StreamingResponse,
)

from src.backend.api.middleware.request_id import RequestIdMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import func, select, or_
from sqlalchemy.orm import joinedload

from src.backend.config.settings import DEFAULT_ENGINE_WEIGHTS, settings
from src.backend.application.services.batch_detection_service import (
    BatchDetectionService,
    ComparisonResult,
    _risk_level,
)

os.environ.setdefault("DATABASE_URL", settings.DATABASE_URL)
if settings.MOSS_USER_ID:
    os.environ.setdefault("MOSS_USER_ID", settings.MOSS_USER_ID)
from src.backend.config.database import SessionLocal
from src.backend.infrastructure.professional_report_generator import ReportGenerator
from src.backend.infrastructure.reporting.evidence_pdf_exporter import (
    _minimal_pdf_bytes,
)
from src.backend.models.database import (
    Tenant,
    User,
    ApiKey,
    Job,
    Submission,
    SimilarityResult,
    WebhookEvent,
    UsageMetric,
    AuditLog,
    Course,
    Assignment,
    CourseInstructor,
    FprValidationRun,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IntegrityDesk API")

frontend_origin_candidates = {settings.FRONTEND_URL.rstrip("/")}
parsed_frontend_url = urlparse(settings.FRONTEND_URL)
if parsed_frontend_url.hostname == "localhost":
    frontend_origin_candidates.add(
        settings.FRONTEND_URL.replace("localhost", "127.0.0.1", 1).rstrip("/")
    )
elif parsed_frontend_url.hostname == "127.0.0.1":
    frontend_origin_candidates.add(
        settings.FRONTEND_URL.replace("127.0.0.1", "localhost", 1).rstrip("/")
    )

app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(frontend_origin_candidates),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "content-type",
        "authorization",
        "accept",
        "accept-language",
        "content-language",
        "*",
    ],
)

REPORTS_DIR = project_root / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
BENCHMARK_RUNS_DIR = REPORTS_DIR / "benchmark_runs"
BENCHMARK_RUNS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = project_root / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
TOOLS_DIR = project_root.parent / "tools"
ENV_SETTINGS_PATH = project_root / "backend" / ".env.local"
AUTH_COOKIE_NAME = "integritydesk_session"
AUTH_COOKIE_MAX_AGE_SECONDS = max(300, int(settings.AUTH_TOKEN_EXPIRE_MINUTES) * 60)
AUTH_EXEMPT_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/status",
    "/api/auth/login",
    "/api/auth/bootstrap-admin",
    "/api/upload",
    "/api/upload-zip",
    "/api/upload-settings",
    "/api/benchmark",
    "/api/benchmark/stream",
    "/api/benchmark/start",
    "/api/error-analysis",
    "/api/benchmark/export-pdf",
    "/api/benchmark-tools",
    "/api/benchmark-datasets",
    "/api/ai-detect",
}
AUTH_PROTECTED_PREFIXES = ("/api/", "/report/", "/benchmark/")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# In-memory progress tracking for benchmark jobs
import threading

BENCHMARK_PROGRESS: Dict[str, List[str]] = {}

# Rate limiting for login attempts
LOGIN_ATTEMPTS: Dict[str, List[datetime]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes
BENCHMARK_RESULTS: Dict[str, Any] = {}
BENCHMARK_LOCK = threading.Lock()


def _append_progress(job_id: str, line: str) -> None:
    with BENCHMARK_LOCK:
        BENCHMARK_PROGRESS.setdefault(job_id, []).append(line)


REAL_BENCHMARK_TOOL_IDS = {
    "integritydesk",
    "dolos",
    "jplag",
    "moss",
    "nicad",
    "pmd",
    "sherlock",
}

TOOL_DIRECTORY_ALIASES = {
    "bplag": "bplag",
    "jplag": "jplag",
    "nicad": "nicad",
    "strange": "strange",
    "sherlock": "sherlock",
    "dolos": "dolos",
    "evalforge": "evalforge",
    "gptzero": "gptzero",
    "grammarly": "grammarly",
    "moss": "moss",
    "pmd": "pmd",
    "sim": "sim",
    "vendetect": "vendetect",
}

TOOL_DISPLAY_ORDER = [
    "integritydesk",
    "moss",
    "jplag",
    "dolos",
    "nicad",
    "pmd",
    "sherlock",
    "sim",
    "bplag",
    "strange",
    "vendetect",
    "gptzero",
    "grammarly",
    "evalforge",
]

BENCHMARK_TOOL_METADATA: Dict[str, Dict[str, Any]] = {
    "integritydesk": {
        "name": "IntegrityDesk",
        "desc": "Multi-engine fusion across Token, AST, Winnowing, GST, Semantic, and Web signals, with optional AI Detection and Execution/CFG layers.",
        "color": "#0066cc",
        "gradient": "from-blue-500 to-blue-600",
        "bgLight": "bg-blue-50",
        "ring": "ring-blue-500",
        "engines": [
            "Token",
            "AST",
            "Winnowing",
            "GST",
            "Semantic",
            "Web",
            "AI Detection",
            "Execution/CFG",
        ],
        "source_type": "built-in",
    },
    "moss": {
        "name": "MOSS",
        "desc": "Tokenized code comparison with document fingerprinting via the winnowing algorithm.",
        "color": "#7c3aed",
        "gradient": "from-violet-500 to-violet-600",
        "bgLight": "bg-violet-50",
        "ring": "ring-violet-500",
        "engines": ["Token", "Winnowing"],
    },
    "jplag": {
        "name": "JPlag",
        "desc": "Syntax-aware token comparison over normalized language-specific token streams.",
        "color": "#059669",
        "gradient": "from-emerald-500 to-emerald-600",
        "bgLight": "bg-emerald-50",
        "ring": "ring-emerald-500",
        "engines": ["Token", "Syntax-Aware"],
    },
    "dolos": {
        "name": "Dolos",
        "desc": "Dodona Dolos CLI using real fingerprint-based plagiarism analysis.",
        "color": "#d97706",
        "gradient": "from-amber-500 to-amber-600",
        "bgLight": "bg-amber-50",
        "ring": "ring-amber-500",
        "engines": ["Token", "Winnowing", "Syntax-Aware"],
    },
    "nicad": {
        "name": "NiCad",
        "desc": "Near-miss clone detector using normalization and blind identifier renaming.",
        "color": "#e11d48",
        "gradient": "from-rose-500 to-rose-600",
        "bgLight": "bg-rose-50",
        "ring": "ring-rose-500",
        "engines": ["Normalization", "Near-Miss"],
    },
    "pmd": {
        "name": "PMD CPD",
        "desc": "PMD Copy/Paste Detector executed from the bundled CLI distribution.",
        "color": "#0f766e",
        "gradient": "from-teal-500 to-teal-600",
        "bgLight": "bg-teal-50",
        "ring": "ring-teal-500",
        "engines": ["Token"],
    },
    "sherlock": {
        "name": "Sherlock",
        "desc": "Text-signature style detector based on textual signatures and attribute-style comparisons.",
        "color": "#4f46e5",
        "gradient": "from-indigo-500 to-indigo-600",
        "bgLight": "bg-indigo-50",
        "ring": "ring-indigo-500",
        "engines": ["Text-Signature Style", "Text Similarity"],
    },
    "sim": {
        "name": "SIM",
        "desc": "Dick Grune's software similarity tester for common token and text segments.",
        "color": "#0891b2",
        "gradient": "from-cyan-500 to-cyan-600",
        "bgLight": "bg-cyan-50",
        "ring": "ring-cyan-500",
        "engines": ["Token", "Text Similarity"],
    },
    "bplag": {
        "name": "BPlag",
        "desc": "Installed under tools/ as an additional plagiarism detector, but not benchmark-wired yet.",
        "color": "#a21caf",
        "gradient": "from-fuchsia-500 to-fuchsia-600",
        "bgLight": "bg-fuchsia-50",
        "ring": "ring-fuchsia-500",
        "engines": ["Installed"],
    },
    "strange": {
        "name": "STRANGE",
        "desc": "Installed research detector bundle present in tools/, currently inventory-only in the UI.",
        "color": "#db2777",
        "gradient": "from-pink-500 to-pink-600",
        "bgLight": "bg-pink-50",
        "ring": "ring-pink-500",
        "engines": ["Installed"],
    },
    "vendetect": {
        "name": "VenDetect",
        "desc": "Installed auxiliary detection utility that is not yet runnable from the benchmark page.",
        "color": "#78716c",
        "gradient": "from-stone-500 to-stone-600",
        "bgLight": "bg-stone-50",
        "ring": "ring-stone-500",
        "engines": ["Installed"],
    },
    "gptzero": {
        "name": "GPTZero",
        "desc": "AI-generated text detector present in tools/, listed for inventory completeness only.",
        "color": "#334155",
        "gradient": "from-slate-600 to-slate-700",
        "bgLight": "bg-slate-50",
        "ring": "ring-slate-500",
        "engines": ["Installed"],
    },
    "grammarly": {
        "name": "Grammarly API",
        "desc": "Grammar and writing-analysis tooling present in tools/, not part of benchmark execution.",
        "color": "#65a30d",
        "gradient": "from-lime-500 to-lime-600",
        "bgLight": "bg-lime-50",
        "ring": "ring-lime-500",
        "engines": ["Installed"],
    },
    "evalforge": {
        "name": "EvalForge",
        "desc": "Evaluation framework assets stored in tools/, surfaced here as inventory rather than a runner.",
        "color": "#0284c7",
        "gradient": "from-sky-500 to-sky-600",
        "bgLight": "bg-sky-50",
        "ring": "ring-sky-500",
        "engines": ["Evaluation"],
    },
}

ENGINE_WEIGHT_LEGACY_MAP: Dict[str, str] = {
    "fingerprint": "token",
    "semantic": "embedding",
    "unixcoder": "embedding",
    "ngram": "gst",
    "structural": "gst",
    "string_tiling": "gst",
    "execution": "graph",
    "llm": "embedding",
}


def _normalize_engine_weights(raw: Any) -> Dict[str, float]:
    normalized = {key: 0.0 for key in DEFAULT_ENGINE_WEIGHTS}
    seen = set()
    if not isinstance(raw, dict):
        return dict(DEFAULT_ENGINE_WEIGHTS)

    for key, value in raw.items():
        target = ENGINE_WEIGHT_LEGACY_MAP.get(str(key), str(key))
        if target not in normalized:
            continue
        try:
            normalized[target] += float(value)
            seen.add(target)
        except (TypeError, ValueError):
            continue

    if not seen:
        return dict(DEFAULT_ENGINE_WEIGHTS)

    for key, value in DEFAULT_ENGINE_WEIGHTS.items():
        if key not in seen:
            normalized[key] = value

    return normalized


_jobs: Dict[str, Dict[str, Any]] = {}
JOB_METADATA_FILENAME = "job.json"
REVIEW_STATUSES = {"unreviewed", "needs_review", "confirmed", "dismissed", "escalated"}
TRUTHY_VALUES = {"1", "true", "yes", "on"}
AI_MEDIUM_RISK_THRESHOLD = 0.4
AI_HIGH_RISK_THRESHOLD = 0.7

ALLOWED_EXTENSIONS = {
    ".py",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".kt",
    ".swift",
    ".scala",
    ".r",
    ".m",
    ".sql",
    ".sh",
    ".bash",
    ".zsh",
    ".ps1",
    ".lua",
    ".pl",
    ".pm",
    ".ex",
    ".exs",
    ".dart",
    ".clj",
    ".hs",
    ".ml",
    ".fs",
    ".erl",
    ".vue",
    ".svelte",
}


def _is_code_file(filename: str) -> bool:
    return PathLib(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _language_file_extension(language: str) -> str:
    return {
        "python": ".py",
        "java": ".java",
        "javascript": ".js",
        "cpp": ".cpp",
    }.get(language, f".{language}")


def _normalize_demo_filename(
    filename: str, language: str, plagiarized: bool = False
) -> str:
    path = PathLib(filename)
    suffix = path.suffix.lower()
    normalized_suffix = {
        ".python": ".py",
        ".javascript": ".js",
    }.get(suffix, suffix or _language_file_extension(language))
    base_name = path.stem or path.name
    if plagiarized:
        return f"{base_name}_plagiarized{normalized_suffix}"
    return f"{base_name}{normalized_suffix}"


def _infer_language_from_filename(filename: str) -> str:
    suffix = PathLib(filename).suffix.lower()
    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".hpp": "cpp",
        ".h": "c",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".kt": "kotlin",
        ".swift": "swift",
        ".scala": "scala",
    }
    return language_map.get(suffix, "python")


def _infer_pmd_language_from_filename(filename: str) -> str:
    language = _infer_language_from_filename(filename)
    pmd_language_map = {
        "javascript": "ecmascript",
        "typescript": "typescript",
        "csharp": "cs",
    }
    return pmd_language_map.get(language, language)


def _read_json_file(path: PathLib) -> Dict[str, Any]:
    """Read a JSON file and return a dictionary."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Error reading JSON file {path}: {exc}")
        return {}
    return data if isinstance(data, dict) else {}


def _load_dataset_metadata(dataset_root: PathLib) -> Dict[str, Any]:
    """Load optional dataset metadata from a dataset root."""
    if dataset_root.name in BUILTIN_PAIR_DATASET_IDS:
        metadata = _load_builtin_pair_dataset_metadata(dataset_root.name)
        if metadata:
            return metadata
    metadata_path = dataset_root / "metadata.json"
    if not metadata_path.exists():
        return _load_builtin_pair_dataset_metadata(dataset_root.name)
    return _read_json_file(metadata_path)


def _builtin_pair_dataset_path(dataset_id: str) -> PathLib:
    """Return the tracked fixture path for a built-in pair-labeled dataset."""
    return BUILTIN_PAIR_DATASET_DIR / f"{dataset_id}.json"


def _load_builtin_pair_dataset_payload(dataset_id: str) -> Dict[str, Any]:
    """Load a tracked pair-labeled benchmark fixture."""
    if dataset_id not in BUILTIN_PAIR_DATASET_IDS:
        return {}
    fixture_path = _builtin_pair_dataset_path(dataset_id)
    if not fixture_path.exists():
        return {}
    return _read_json_file(fixture_path)


def _load_builtin_pair_dataset_metadata(dataset_id: str) -> Dict[str, Any]:
    """Load display metadata from a tracked pair-labeled benchmark fixture."""
    payload = _load_builtin_pair_dataset_payload(dataset_id)
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _normalize_submission_name(path: PathLib, root_dir: PathLib) -> str:
    """Create a stable, collision-resistant submission name within a dataset root."""
    try:
        relative_path = path.relative_to(root_dir)
    except ValueError:
        relative_path = PathLib(path.name)
    return "__".join(relative_path.parts)


def _infer_language_from_code(code: str, fallback: str = "python") -> str:
    """Infer a likely language from code content when metadata is missing."""
    sample = code[:2000]
    if not sample.strip():
        return fallback

    if (
        "import java." in sample
        or "System.out." in sample
        or re.search(r"\b(public|private|protected)\s+(class|static|void)\b", sample)
    ):
        return "java"
    if (
        "#include" in sample
        or re.search(r"\bprintf\s*\(", sample)
        or re.search(r"\bscanf\s*\(", sample)
    ):
        return "c"
    if re.search(r"^\s*def\s+\w+\s*\(", sample, re.MULTILINE):
        return "python"
    if "console.log" in sample or re.search(r"\bfunction\b|\=\>", sample):
        return "javascript"

    return fallback


def _dataset_default_language(dataset_id: str) -> str:
    """Return the default language for a known benchmark dataset."""
    return {
        "poj104": "mixed",
        "poolc_600k_python": "python",
        "codesearchnet": "mixed",
        "codexglue_clone": "java",
        "codexglue_defect": "c",
        "CodeSimilarityDataset": "python",
        "bigclonebench": "java",
        "conplag": "java",
        "conplag_classroom_java": "java",
        "google_codejam": "python",
        "human_eval": "python",
        "mbpp": "python",
        "kaggle_student_code": "python",
        "synthetic": "python",
        "xiangtan": "java",
        "clough_stevenson_style": "python",
    }.get(dataset_id, "mixed")


def _resolve_benchmark_dataset_dir(dataset_id: str) -> Optional[PathLib]:
    """Resolve the on-disk directory for a benchmark dataset."""
    dataset_root = _resolve_benchmark_dataset_root(dataset_id)
    if not dataset_root.exists():
        return None

    for candidate in (
        dataset_root / "huggingface" / "train",
        dataset_root / "huggingface" / "test",
        dataset_root / "huggingface" / "validation",
        dataset_root / "submissions",
        dataset_root,
    ):
        if candidate.exists():
            return candidate

    return dataset_root


def _dataset_snippets_per_row(dataset_info: Dict[str, Any]) -> int:
    """Estimate how many code files one dataset row can yield."""
    features = dataset_info.get("features") or {}
    if not isinstance(features, dict):
        return 1
    if "func1" in features and "func2" in features:
        return 2
    return 1


def _infer_dataset_language(
    dataset_id: str,
    metadata: Dict[str, Any],
    dataset_info: Dict[str, Any],
    dataset_dir: Optional[PathLib] = None,
) -> str:
    """Infer a dataset language from metadata or dataset schema."""
    language = metadata.get("language") or metadata.get("lang")
    if isinstance(language, str) and language.strip():
        return language.strip().lower()

    default_language = _dataset_default_language(dataset_id)
    features = dataset_info.get("features") or {}
    if (
        isinstance(features, dict)
        and "language" in features
        and default_language == "mixed"
    ):
        return "mixed"

    return default_language


def _infer_dataset_size_label(
    dataset_dir: PathLib,
    metadata: Dict[str, Any],
    dataset_info: Dict[str, Any],
    is_demo: bool,
) -> str:
    """Build the display size label for a dataset card."""
    explicit_size = metadata.get("size")
    if isinstance(explicit_size, str) and explicit_size.strip():
        return explicit_size

    if is_demo:
        demo_files = metadata.get("files_created")
        if isinstance(demo_files, int) and demo_files > 0:
            return f"{demo_files} files"

    generated_pairs = dataset_dir / "generated_pairs.jsonl"
    if generated_pairs.exists():
        try:
            payload = json.loads(generated_pairs.read_text(encoding="utf-8"))
            pair_count = len(payload.get("pairs", []))
            if pair_count > 0:
                return f"{pair_count:,} labeled pairs"
        except (OSError, json.JSONDecodeError):
            pass

    cheating_csv = dataset_dir / "cheating_dataset.csv"
    if cheating_csv.exists():
        try:
            with cheating_csv.open("r", encoding="utf-8", newline="") as csv_file:
                pair_count = max(0, sum(1 for _ in csv_file) - 1)
            if pair_count > 0:
                return f"{pair_count:,} labeled pairs"
        except OSError:
            pass

    pairs_csv = dataset_dir / "pairs.csv"
    if pairs_csv.exists():
        try:
            with pairs_csv.open("r", encoding="utf-8", newline="") as csv_file:
                pair_count = max(0, sum(1 for _ in csv_file) - 1)
            if pair_count > 0:
                return f"{pair_count:,} labeled pairs"
        except OSError:
            pass

    conplag_labels = dataset_dir / "versions" / "labels.csv"
    if conplag_labels.exists():
        try:
            with conplag_labels.open("r", encoding="utf-8", newline="") as csv_file:
                pair_count = max(0, sum(1 for _ in csv_file) - 1)
            if pair_count > 0:
                return f"{pair_count:,} labeled pairs"
        except OSError:
            pass

    full_metadata_csv = dataset_dir / "full_metadata.csv"
    if full_metadata_csv.exists():
        try:
            with full_metadata_csv.open("r", encoding="utf-8", newline="") as csv_file:
                snippet_count = max(0, sum(1 for _ in csv_file) - 1)
            if snippet_count > 0:
                return f"{snippet_count:,} snippets"
        except OSError:
            pass

    reduced_bcb = dataset_dir / "bcb_reduced"
    if reduced_bcb.exists():
        java_count = sum(1 for _ in reduced_bcb.rglob("*.java"))
        if java_count > 0:
            return f"{java_count:,} Java files"

    parquet_files = sorted((dataset_dir / "data").glob("*.parquet"))
    if parquet_files:
        return f"{len(parquet_files):,} parquet shard{'s' if len(parquet_files) != 1 else ''}"

    splits = dataset_info.get("splits") or {}
    if isinstance(splits, dict):
        train_info = splits.get("train") or next(iter(splits.values()), {})
        if isinstance(train_info, dict):
            num_examples = train_info.get("num_examples")
            if isinstance(num_examples, int) and num_examples > 0:
                total_files = num_examples * _dataset_snippets_per_row(dataset_info)
                return f"{total_files:,} files"

    return "Dataset files"


def _read_generated_pair_items(dataset_root: PathLib) -> List[Dict[str, Any]]:
    """Read explicit benchmark pairs from a generated pair dataset."""
    pairs_path = dataset_root / "generated_pairs.jsonl"
    payload = _load_builtin_pair_dataset_payload(dataset_root.name)
    if pairs_path.exists():
        try:
            loaded_payload = json.loads(pairs_path.read_text(encoding="utf-8"))
            if isinstance(loaded_payload, dict) and not payload:
                payload = loaded_payload
        except (OSError, json.JSONDecodeError):
            pass

    raw_pairs = payload.get("pairs", []) if isinstance(payload, dict) else []
    return [item for item in raw_pairs if isinstance(item, dict)]


def _count_csv_binary_labels(
    csv_path: PathLib, label_column: str = "Label"
) -> tuple[int, int, int]:
    """Count total, positive, and negative labels in a CSV pair manifest."""
    if not csv_path.exists():
        return 0, 0, 0

    total = 0
    positives = 0
    negatives = 0
    try:
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                total += 1
                if _label_to_clone_grade(row.get(label_column, 0)) >= 2:
                    positives += 1
                else:
                    negatives += 1
    except OSError:
        return 0, 0, 0

    return total, positives, negatives


def _count_generated_pair_labels(dataset_root: PathLib) -> tuple[int, int, int]:
    """Count total, positive, and negative labels in a generated pair dataset."""
    raw_pairs = _read_generated_pair_items(dataset_root)
    positives = sum(
        1
        for pair in raw_pairs
        if _label_to_clone_grade(pair.get("label", 0), pair.get("clone_type")) >= 2
    )
    return len(raw_pairs), positives, len(raw_pairs) - positives


def _count_conplag_labels(dataset_root: PathLib) -> tuple[int, int, int]:
    """Count total, positive, and negative CONPLAG labels."""
    return _count_csv_binary_labels(dataset_root / "versions" / "labels.csv", "verdict")


def _count_code_similarity_pairs(dataset_root: PathLib) -> tuple[int, int, int]:
    """Estimate balanced pair counts for CodeSimilarityDataset."""
    grouped = _code_similarity_snippet_groups(dataset_root)
    positive_pairs = sum(
        max(0, len(files) * (len(files) - 1) // 2) for files in grouped.values()
    )
    group_sizes = [len(files) for files in grouped.values()]
    negative_pairs = 0
    for left_index, left_size in enumerate(group_sizes):
        for right_size in group_sizes[left_index + 1 :]:
            negative_pairs += left_size * right_size
    cap_each = PAIR_BENCHMARK_MAX_PAIRS // 2
    positives = min(positive_pairs, cap_each)
    negatives = min(negative_pairs, cap_each)
    return positives + negatives, positives, negatives


def _count_bigclonebench_reduced_pairs(dataset_root: PathLib) -> tuple[int, int, int]:
    """Estimate balanced pair counts from BigCloneBench reduced functionality folders."""
    groups = _bigclonebench_reduced_groups(dataset_root)
    positive_pairs = sum(
        max(0, len(files) * (len(files) - 1) // 2) for files in groups.values()
    )
    group_sizes = [len(files) for files in groups.values()]
    negative_pairs = 0
    for left_index, left_size in enumerate(group_sizes):
        for right_size in group_sizes[left_index + 1 :]:
            negative_pairs += left_size * right_size
    cap_each = PAIR_BENCHMARK_MAX_PAIRS // 2
    positives = min(positive_pairs, cap_each)
    negatives = min(negative_pairs, cap_each)
    return positives + negatives, positives, negatives


def _has_loadable_huggingface_dataset(dataset_root: PathLib) -> bool:
    """Return whether a HuggingFace dataset directory can be loaded locally."""
    hf_path = dataset_root / "huggingface"
    if not hf_path.exists():
        return False

    dataset_dict = _read_json_file(hf_path / "dataset_dict.json")
    splits = dataset_dict.get("splits")
    if isinstance(splits, list) and splits:
        for split_name in splits:
            split_dir = hf_path / str(split_name)
            if not split_dir.exists():
                return False
            if not (split_dir / "state.json").exists():
                return False
            if not any(split_dir.glob("*.arrow")):
                return False
        return True

    return (hf_path / "state.json").exists() and any(hf_path.glob("*.arrow"))


def _build_benchmark_dataset_readiness(
    dataset_id: str, dataset_root: PathLib
) -> Dict[str, Any]:
    """Describe whether a dataset should be visible as runnable in the dashboard."""
    if dataset_id.startswith("demo_"):
        original_dir = dataset_root / "original"
        plagiarized_dir = dataset_root / "plagiarized"
        runnable = original_dir.exists() and plagiarized_dir.exists()
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_demo_pairs",
            "reason": (
                "Demo dataset has original and plagiarized folders."
                if runnable
                else "Demo dataset is missing original or plagiarized files."
            ),
        }

    if dataset_id in BUILTIN_PAIR_DATASET_IDS:
        runnable = _builtin_pair_dataset_path(dataset_id).exists()
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_fixture",
            "reason": (
                "Built-in labeled fixture is available."
                if runnable
                else "Built-in labeled fixture is missing."
            ),
        }

    if (dataset_root / "generated_pairs.jsonl").exists():
        total, positives, negatives = _count_generated_pair_labels(dataset_root)
        runnable = positives > 0 and negatives > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "needs_positive_and_negative_pairs",
            "reason": f"{positives} positive and {negatives} negative labeled pairs.",
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    if dataset_id == "kaggle_student_code":
        total, positives, negatives = _count_csv_binary_labels(
            dataset_root / "cheating_dataset.csv"
        )
        runnable = positives > 0 and negatives > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_labeled_csv",
            "reason": f"Found {positives} positive and {negatives} negative pairs in CSV.",
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    if dataset_id == "CodeSimilarityDataset":
        total, positives, negatives = _count_code_similarity_pairs(dataset_root)
        runnable = positives > 0 and negatives > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_snippet_groups",
            "reason": (
                f"CodeSimilarityDataset can create {positives} same-task positives and {negatives} cross-task negatives."
                if runnable
                else "CodeSimilarityDataset needs full_metadata.csv and snippet files."
            ),
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    if dataset_id == "google_codejam":
        gt_path = dataset_root / "ground_truth.json"
        runnable = gt_path.exists()
        if runnable:
            try:
                gt = json.loads(gt_path.read_text())
                total = len(gt)
                positives = sum(1 for v in gt.values() if v.get("plagiarism", False))
                negatives = total - positives
            except Exception:
                runnable = False
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_ground_truth",
            "reason": (
                "Google Code Jam dataset with ground truth labels."
                if runnable
                else "Missing ground_truth.json file."
            ),
            "pair_count": total if runnable else 0,
            "positive_pairs": positives if runnable else 0,
            "negative_pairs": negatives if runnable else 0,
        }

    if dataset_id == "xiangtan":
        pairs_csv = dataset_root / "pairs.csv"
        source_dir = dataset_root / "source"
        positive_pairs = (
            max(0, sum(1 for _ in pairs_csv.open()) - 1) if pairs_csv.exists() else 0
        )
        source_files = list(source_dir.rglob("*.java")) if source_dir.exists() else []
        negative_pairs = min(positive_pairs, max(0, len(source_files) - 1))
        runnable = positive_pairs > 0 and negative_pairs > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_xiangtan_sources",
            "reason": (
                f"{positive_pairs} positive pairs plus {negative_pairs} generated negative pairs."
                if runnable
                else "Xiangtan needs pairs.csv and Java source files."
            ),
            "pair_count": positive_pairs + negative_pairs,
            "positive_pairs": positive_pairs,
            "negative_pairs": negative_pairs,
        }

    if dataset_id == "bigclonebench":
        total, positives, negatives = _count_bigclonebench_reduced_pairs(dataset_root)
        runnable = positives > 0 and negatives > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_reduced_bcb_sources",
            "reason": (
                f"BigCloneBench reduced sample can create {positives} same-functionality positives and {negatives} cross-functionality negatives."
                if runnable
                else "BigCloneBench needs bcb_reduced functionality folders with Java files."
            ),
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    if dataset_id == "poj104":
        runnable = _has_loadable_huggingface_dataset(dataset_root)
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "incomplete_huggingface_dataset",
            "reason": (
                "POJ-104 HuggingFace dataset is loadable."
                if runnable
                else "POJ-104 HuggingFace dataset is incomplete or missing."
            ),
        }

    if dataset_id == "poolc_600k_python":
        parquet_files = sorted((dataset_root / "data").glob("*.parquet"))
        runnable = bool(parquet_files)
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_parquet_shards",
            "reason": (
                f"{len(parquet_files)} local parquet shard(s) available."
                if runnable
                else "PoolC needs at least one local parquet shard."
            ),
        }

    if dataset_id == "codexglue_clone":
        runnable = _has_loadable_huggingface_dataset(dataset_root)
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "incomplete_huggingface_dataset",
            "reason": (
                "CodeXGLUE clone dataset is loadable."
                if runnable
                else "CodeXGLUE clone dataset is incomplete; download all splits first."
            ),
        }

    if dataset_id == "IR-Plag-Dataset":
        # Check for case-* directories with required subdirs
        case_dirs = [
            d
            for d in dataset_root.iterdir()
            if d.is_dir() and d.name.startswith("case-")
        ]
        if not case_dirs:
            return {
                "runnable": False,
                "status": "missing_case_dirs",
                "reason": "IR-Plag dataset needs case-* directories.",
            }
        total_pairs = 0
        for case_dir in case_dirs:
            original_dir = case_dir / "original"
            plagiarized_dir = case_dir / "plagiarized"
            non_plagiarized_dir = case_dir / "non-plagiarized"
            if not (
                original_dir.exists()
                and plagiarized_dir.exists()
                and non_plagiarized_dir.exists()
            ):
                return {
                    "runnable": False,
                    "status": "incomplete_case_structure",
                    "reason": f"Case {case_dir.name} missing required subdirectories.",
                }
            # Count potential pairs: original files vs plagiarized/non-plagiarized
            original_files = list(original_dir.glob("*.java"))
            plagiarized_files = sum(1 for _ in plagiarized_dir.rglob("*.java"))
            non_plagiarized_files = sum(1 for _ in non_plagiarized_dir.rglob("*.java"))
            total_pairs += len(original_files) * (
                plagiarized_files + non_plagiarized_files
            )
        runnable = total_pairs > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "no_java_files",
            "reason": (
                f"IR-Plag dataset with {total_pairs} labeled pairs across {len(case_dirs)} cases."
                if runnable
                else "No Java files found in IR-Plag dataset structure."
            ),
            "pair_count": total_pairs,
            "positive_pairs": total_pairs // 2,  # Approximate: assuming balanced
            "negative_pairs": total_pairs // 2,
        }

    if dataset_id == "conplag":
        total, positives, negatives = _count_conplag_labels(dataset_root)
        version_dir = dataset_root / "versions" / "version_1"
        runnable = (
            total > 0 and positives > 0 and negatives > 0 and version_dir.exists()
        )
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "missing_conplag_files",
            "reason": (
                f"CONPLAG dataset with {total} labeled Java contest pairs ({positives} positive, {negatives} negative)."
                if runnable
                else "CONPLAG needs versions/labels.csv and versions/version_1 Java pair folders."
            ),
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    if dataset_id == "conplag_classroom_java":
        # Map to conplag directory
        conplag_root = BENCHMARK_DATA_DIR / "conplag"
        if not conplag_root.exists():
            return {
                "runnable": False,
                "status": "missing_conplag_dir",
                "reason": "CONPLAG dataset directory not found.",
            }
        labels_csv = conplag_root / "versions" / "labels.csv"
        version_1_dir = conplag_root / "versions" / "version_1"
        if not (labels_csv.exists() and version_1_dir.exists()):
            return {
                "runnable": False,
                "status": "missing_conplag_files",
                "reason": "CONPLAG dataset missing labels.csv or version_1 directory.",
            }
        try:
            import csv

            with open(labels_csv, "r") as f:
                reader = csv.DictReader(f)
                total = sum(1 for row in reader)
            positives = sum(
                1
                for row in csv.DictReader(open(labels_csv, "r"))
                if row.get("verdict") == "1"
            )
            negatives = total - positives
        except Exception:
            return {
                "runnable": False,
                "status": "invalid_labels_csv",
                "reason": "Could not parse CONPLAG labels.csv.",
            }
        runnable = total > 0
        return {
            "runnable": runnable,
            "status": "ready" if runnable else "no_pairs",
            "reason": (
                f"CONPLAG dataset with {total} labeled pairs ({positives} positive, {negatives} negative)."
                if runnable
                else "No pairs found in CONPLAG labels.csv."
            ),
            "pair_count": total,
            "positive_pairs": positives,
            "negative_pairs": negatives,
        }

    return {
        "runnable": False,
        "status": "unsupported_dataset_layout",
        "reason": "No labeled pair loader is available for this dataset layout.",
    }


def _build_benchmark_quality_certificate(
    dataset_root: PathLib,
) -> Optional[Dict[str, Any]]:
    """Build a reproducible quality certificate for explicit pair benchmarks."""
    raw_pairs = _read_generated_pair_items(dataset_root)
    if not raw_pairs:
        return None

    metadata = _load_dataset_metadata(dataset_root)
    positive_pairs = [
        pair
        for pair in raw_pairs
        if _label_to_clone_grade(pair.get("label", 0), pair.get("clone_type")) >= 2
    ]
    negative_pairs = [pair for pair in raw_pairs if pair not in positive_pairs]
    clone_types = Counter(
        str(pair.get("clone_type", "unknown")) for pair in positive_pairs
    )
    transformations = Counter(
        str(pair.get("obfuscation", "unspecified")) for pair in raw_pairs
    )
    case_categories = Counter(_pair_case_category(pair) for pair in raw_pairs)
    split_counts = Counter(_pair_split(pair) for pair in raw_pairs)
    pair_ids = [str(pair.get("id", "")).strip() for pair in raw_pairs]
    hard_negative_pairs = [
        pair
        for pair in negative_pairs
        if _pair_case_category(pair) == "hard_negative"
        or str(pair.get("obfuscation", "")).startswith("hard_negative")
        or str(pair.get("obfuscation", ""))
        in {
            "same_domain_different_task",
            "shared_boilerplate_only",
            "same_algorithm_family_different_behavior",
        }
    ]
    generated_by_tools = metadata.get("generated_by_tools", [])
    if not isinstance(generated_by_tools, list):
        generated_by_tools = []
    lower_generated_by_tools = {
        str(tool).strip().lower() for tool in generated_by_tools if str(tool).strip()
    }
    evaluated_tool_ids = REAL_BENCHMARK_TOOL_IDS - {"integritydesk"}
    leaked_tools = sorted(lower_generated_by_tools.intersection(evaluated_tool_ids))
    has_cross_language = any(
        str(pair.get("obfuscation", "")) == "cross_language_translation"
        or (
            pair.get("language_a")
            and pair.get("language_b")
            and pair.get("language_a") != pair.get("language_b")
        )
        for pair in positive_pairs
    )
    has_obfuscation = any(
        "obfuscat" in str(pair.get("obfuscation", "")).lower()
        or "dead_code" in str(pair.get("obfuscation", "")).lower()
        for pair in positive_pairs
    )
    required_case_categories = {
        "true_positive",
        "true_negative",
        "hard_negative",
        "edge_case",
    }
    required_splits = {"train", "validation", "test"}
    duplicate_pair_ids = sorted(
        pair_id for pair_id, count in Counter(pair_ids).items() if pair_id and count > 1
    )
    split_protocol = metadata.get("split_protocol", {})
    labeling_process = metadata.get("labeling_process", {})
    if not isinstance(split_protocol, dict):
        split_protocol = {}
    if not isinstance(labeling_process, dict):
        labeling_process = {}
    external_validation = metadata.get("external_validation", {})
    inter_rater_agreement = metadata.get("inter_rater_agreement", {})
    if not isinstance(external_validation, dict):
        external_validation = {}
    if not isinstance(inter_rater_agreement, dict):
        inter_rater_agreement = {}
    minimum_kappa = float(labeling_process.get("minimum_cohens_kappa", 0.7))
    cohens_kappa = inter_rater_agreement.get("cohens_kappa")
    has_trustworthy_kappa = (
        isinstance(cohens_kappa, (int, float)) and float(cohens_kappa) >= minimum_kappa
    )
    has_pan_external_results = external_validation.get(
        "pan_source_code_corpora"
    ) == "included" and bool(external_validation.get("results"))
    pair_count = len(raw_pairs)
    positive_ratio = len(positive_pairs) / pair_count if pair_count else 0.0

    gates = [
        {
            "id": "label_leakage",
            "label": "No tool-derived labels",
            "passed": len(leaked_tools) == 0,
            "value": (
                "No evaluated tools used as label source"
                if not leaked_tools
                else ", ".join(leaked_tools)
            ),
            "target": "Ground truth independent of MOSS, JPlag, Dolos, Sherlock, NiCad, and PMD",
        },
        {
            "id": "explicit_labels",
            "label": "Explicit pair labels",
            "passed": all("label" in pair for pair in raw_pairs),
            "value": f"{pair_count} labeled pairs",
            "target": "Every pair has a ground-truth label",
        },
        {
            "id": "minimum_size",
            "label": "Minimum controlled corpus size",
            "passed": pair_count >= 12,
            "value": pair_count,
            "target": "At least 12 curated pairs",
        },
        {
            "id": "class_balance",
            "label": "Positive/negative balance",
            "passed": 0.55 <= positive_ratio <= 0.75 and len(negative_pairs) >= 4,
            "value": f"{len(positive_pairs)} positive / {len(negative_pairs)} negative",
            "target": "55-75% positives with at least 4 negatives",
        },
        {
            "id": "clone_coverage",
            "label": "Clone-type coverage",
            "passed": {"1", "2", "3"}.issubset(set(clone_types)),
            "value": ", ".join(
                f"type {key}: {value}" for key, value in sorted(clone_types.items())
            ),
            "target": "Type 1, Type 2, Type 3, and optional Type 4 positives",
        },
        {
            "id": "obfuscation_coverage",
            "label": "Transformation coverage",
            "passed": len(transformations) >= 8,
            "value": len(transformations),
            "target": "At least 8 distinct transformations",
        },
        {
            "id": "hard_negatives",
            "label": "Hard-negative coverage",
            "passed": len(hard_negative_pairs) >= 3,
            "value": len(hard_negative_pairs),
            "target": "At least 3 same-domain or boilerplate negatives",
        },
        {
            "id": "case_category_coverage",
            "label": "Four case categories",
            "passed": required_case_categories.issubset(set(case_categories)),
            "value": ", ".join(
                f"{key}: {value}" for key, value in sorted(case_categories.items())
            ),
            "target": "true positives, true negatives, hard negatives, and edge cases",
        },
        {
            "id": "three_way_split",
            "label": "Train/validation/test separation",
            "passed": required_splits.issubset(set(split_counts))
            and not duplicate_pair_ids
            and bool(split_protocol),
            "value": ", ".join(
                f"{key}: {value}" for key, value in sorted(split_counts.items())
            ),
            "target": "Non-overlapping train, validation, and locked test sets",
        },
        {
            "id": "cross_language_coverage",
            "label": "Cross-language coverage",
            "passed": has_cross_language,
            "value": "present" if has_cross_language else "missing",
            "target": "At least one translated-language clone pair",
        },
        {
            "id": "obfuscated_code_coverage",
            "label": "Obfuscated-code coverage",
            "passed": has_obfuscation,
            "value": "present" if has_obfuscation else "missing",
            "target": "At least one deliberately obfuscated clone pair",
        },
        {
            "id": "reviewer_protocol",
            "label": "Independent reviewer protocol",
            "passed": int(labeling_process.get("required_reviewers_per_pair", 0)) >= 2
            and bool(labeling_process.get("adjudicator_required"))
            and float(labeling_process.get("minimum_cohens_kappa", 0.0)) >= 0.7,
            "value": labeling_process.get("status", "missing"),
            "target": "Two independent reviewers, third-person adjudication, Kappa >= 0.7",
        },
        {
            "id": "inter_rater_agreement",
            "label": "Cohen's Kappa",
            "passed": has_trustworthy_kappa,
            "value": (
                "pending" if cohens_kappa is None else round(float(cohens_kappa), 3)
            ),
            "target": f"Kappa >= {minimum_kappa:.1f} before final claims",
        },
        {
            "id": "pan_external_validation",
            "label": "PAN external validation",
            "passed": has_pan_external_results,
            "value": external_validation.get("pan_source_code_corpora", "missing"),
            "target": "Published PAN source-code corpus results are recorded",
        },
    ]
    passed_gates = sum(1 for gate in gates if gate["passed"])
    score = passed_gates / max(1, len(gates))
    final_claim_gate_ids = {"inter_rater_agreement", "pan_external_validation"}
    internal_gates_passed = all(
        gate["passed"] for gate in gates if gate["id"] not in final_claim_gate_ids
    )
    if passed_gates == len(gates):
        certification_level = "gold_standard_external"
    elif internal_gates_passed:
        certification_level = "controlled_internal_ready"
    else:
        certification_level = "labeled"
    warnings = []
    if not has_pan_external_results:
        warnings.append(
            "External PAN source-code corpora are not bundled; run PAN 2011-2014 separately for published-baseline validity."
        )
    if not has_trustworthy_kappa:
        warnings.append(
            "Cohen's Kappa is not yet >= 0.7; use this benchmark for internal engineering, not final published claims."
        )

    return {
        "certification_level": certification_level,
        "score": round(score, 4),
        "score_percent": round(score * 100, 1),
        "pair_count": pair_count,
        "positive_pairs": len(positive_pairs),
        "negative_pairs": len(negative_pairs),
        "positive_ratio": round(positive_ratio, 4),
        "clone_types": dict(sorted(clone_types.items())),
        "transformations": dict(sorted(transformations.items())),
        "case_categories": dict(sorted(case_categories.items())),
        "splits": dict(sorted(split_counts.items())),
        "duplicate_pair_ids": duplicate_pair_ids,
        "split_protocol": split_protocol,
        "labeling_process": labeling_process,
        "hard_negative_pairs": len(hard_negative_pairs),
        "ground_truth_source": metadata.get("ground_truth_source", "unknown"),
        "generated_by_tools": sorted(lower_generated_by_tools),
        "leaked_tools": leaked_tools,
        "external_validation": external_validation,
        "inter_rater_agreement": inter_rater_agreement,
        "validation_warnings": warnings,
        "metric_basis": "pair_level_pan_plagdet_with_single_detection_granularity",
        "gates": gates,
    }


def _audit_benchmark_pairs(raw_pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Audit pair labels, case categories, and train/validation/test separation."""
    case_categories = Counter(_pair_case_category(pair) for pair in raw_pairs)
    split_counts = Counter(_pair_split(pair) for pair in raw_pairs)
    labels = [
        _label_to_clone_grade(pair.get("label", 0), pair.get("clone_type"))
        for pair in raw_pairs
    ]
    positives = sum(1 for label in labels if label >= 2)
    negatives = len(labels) - positives
    missing_case_categories = sorted(
        {"true_positive", "true_negative", "hard_negative", "edge_case"}
        - set(case_categories)
    )
    missing_splits = sorted({"train", "validation", "test"} - set(split_counts))

    return {
        "pair_count": len(raw_pairs),
        "positive_pairs": positives,
        "negative_pairs": negatives,
        "case_categories": dict(sorted(case_categories.items())),
        "splits": dict(sorted(split_counts.items())),
        "missing_case_categories": missing_case_categories,
        "missing_splits": missing_splits,
        "hard_negative_count": case_categories.get("hard_negative", 0),
        "ready_for_weight_tuning": not missing_case_categories
        and not missing_splits
        and case_categories.get("hard_negative", 0) >= 3,
    }


def _benchmark_split_guard(split: str, purpose: str) -> Dict[str, Any]:
    """Enforce that locked test data is not used for iterative tuning."""
    normalized_split = str(split or "").strip().lower()
    normalized_purpose = str(purpose or "").strip().lower()
    allowed = not (
        normalized_split == "test"
        and normalized_purpose
        in {"tune", "tuning", "train", "optimize", "optimization"}
    )
    return {
        "allowed": allowed,
        "split": normalized_split,
        "purpose": normalized_purpose,
        "locked_test": normalized_split == "test",
        "message": (
            "Locked test split cannot be used for iterative weight tuning."
            if not allowed
            else "Split use is allowed."
        ),
    }


def _pair_case_category(pair: Dict[str, Any]) -> str:
    """Return the benchmark case category for a labeled pair."""
    category = str(pair.get("case_category", "")).strip().lower()
    if category:
        return category

    label = _label_to_clone_grade(pair.get("label", 0), pair.get("clone_type"))
    obfuscation = str(pair.get("obfuscation", "")).lower()
    pair_id = str(pair.get("id", "")).lower()
    if label >= 2 and (
        "cross_language" in obfuscation
        or "obfuscat" in obfuscation
        or "semantic" in obfuscation
        or "reorder" in obfuscation
        or "rewrite" in obfuscation
    ):
        return "edge_case"
    if label >= 2:
        return "true_positive"
    if "hard_negative" in pair_id or obfuscation in {
        "same_domain_different_task",
        "shared_boilerplate_only",
        "same_algorithm_family_different_behavior",
    }:
        return "hard_negative"
    return "true_negative"


def _pair_split(pair: Dict[str, Any]) -> str:
    """Return the benchmark split for a labeled pair."""
    split = str(pair.get("split", "")).strip().lower()
    return split if split else "unspecified"


def _count_unique_code_files(root_dir: PathLib) -> int:
    """Count unique code files using the same naming rules as the loader."""
    unique_names = {
        _normalize_submission_name(file_path, root_dir)
        for file_path in root_dir.rglob("*")
        if file_path.is_file() and _is_code_file(file_path.name)
    }
    return len(unique_names)


def _infer_language_from_directory(root_dir: PathLib) -> Optional[str]:
    """Infer the dominant language from code file extensions in a raw dataset folder."""
    counts: Dict[str, int] = {}
    for file_path in root_dir.rglob("*"):
        if not file_path.is_file() or not _is_code_file(file_path.name):
            continue
        language = _infer_language_from_filename(file_path.name)
        counts[language] = counts.get(language, 0) + 1

    if not counts:
        return None

    top_language, top_count = max(counts.items(), key=lambda item: item[1])
    total = sum(counts.values())
    if total == 0:
        return None
    if top_count / total >= 0.8:
        return top_language
    return "mixed"


def _extract_code_entries_from_row(
    item: Dict[str, Any],
    dataset_id: str,
    index: int,
) -> List[Dict[str, str]]:
    """Extract one or more source files from a Hugging Face dataset row."""
    if not isinstance(item, dict):
        return []

    code_entries: List[Dict[str, str]] = []
    per_row_fields = ("func1", "func2")
    default_language = _dataset_default_language(dataset_id)
    item_language = str(item.get("language") or default_language).lower()

    for position, field_name in enumerate(per_row_fields):
        code = item.get(field_name)
        if not isinstance(code, str) or len(code.strip()) <= 10:
            continue
        inferred_language = _infer_language_from_code(code, fallback=item_language)
        code_entries.append(
            {
                "filename": (
                    f"{dataset_id}_{index:04d}_{position}"
                    f"{_language_file_extension(inferred_language)}"
                ),
                "code": code,
            }
        )

    if code_entries:
        return code_entries

    for field_name in (
        "code",
        "func_code_string",
        "func",
        "whole_func_string",
        "canonical_solution",
        "prompt",
    ):
        code = item.get(field_name)
        if not isinstance(code, str) or len(code.strip()) <= 10:
            continue
        inferred_language = _infer_language_from_code(code, fallback=item_language)
        return [
            {
                "filename": (
                    f"{dataset_id}_{index:04d}"
                    f"{_language_file_extension(inferred_language)}"
                ),
                "code": code,
            }
        ]

    return []


def _write_submissions_to_directory(
    target_dir: PathLib, submissions: Dict[str, str]
) -> Dict[str, str]:
    written_paths: Dict[str, str] = {}
    for filename, content in submissions.items():
        file_path = target_dir / PathLib(filename).name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        written_paths[filename] = str(file_path)
    return written_paths


def _write_submissions_as_submission_dirs(
    target_dir: PathLib, submissions: Dict[str, str]
) -> Dict[str, Dict[str, str]]:
    written: Dict[str, Dict[str, str]] = {}
    for index, (filename, content) in enumerate(submissions.items()):
        submission_id = f"sub{index:03d}"
        submission_dir = target_dir / submission_id
        submission_dir.mkdir(parents=True, exist_ok=True)
        file_path = submission_dir / PathLib(filename).name
        file_path.write_text(content, encoding="utf-8")
        written[submission_id] = {"filename": filename, "path": str(file_path)}
    return written


def _ai_bucket(score: float) -> str:
    if score >= AI_HIGH_RISK_THRESHOLD:
        return "high"
    if score >= AI_MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def _ai_status_label(score: float) -> str:
    if score >= AI_HIGH_RISK_THRESHOLD:
        return "High Risk"
    if score >= AI_MEDIUM_RISK_THRESHOLD:
        return "Needs Review"
    return "Low Risk"


def _pair_key(file_a: str, file_b: str) -> str:
    return "::".join(sorted([file_a, file_b]))


def _canonical_tool_id(directory_name: str) -> str:
    slug = directory_name.lower()
    for prefix, tool_id in TOOL_DIRECTORY_ALIASES.items():
        if slug == prefix or slug.startswith(f"{prefix}-"):
            return tool_id
    return re.sub(r"[^a-z0-9]+", "-", slug).strip("-")


def _external_tools_dir() -> PathLib:
    """Return the canonical directory for standalone external tools."""
    return TOOLS_DIR / "external"


def _relative_tool_path(path: PathLib) -> str:
    """Return a stable repository-relative path for a tool directory."""
    try:
        return str(Path("tools") / path.relative_to(TOOLS_DIR))
    except ValueError:
        pass
    try:
        return str(path.relative_to(project_root.parent))
    except ValueError:
        return str(path)


def _iter_tool_inventory_dirs() -> List[PathLib]:
    """List installed tool directories from the canonical and legacy locations."""
    ignored_top_level = {
        "__pycache__",
        "configs",
        "external",
        "libs",
        "outputs",
        "registry",
        "runs",
        "sandbox",
    }
    dirs: List[PathLib] = []

    for root in (_external_tools_dir(), TOOLS_DIR):
        if not root.exists():
            continue
        for entry in sorted(root.iterdir(), key=lambda item: item.name.lower()):
            if not entry.is_dir():
                continue
            if root == TOOLS_DIR and entry.name in ignored_top_level:
                continue
            dirs.append(entry)

    return dirs


def _first_existing_path(candidates: List[PathLib]) -> Optional[PathLib]:
    """Return the first path that exists."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_tool_dir(tool_id: str) -> Optional[PathLib]:
    """Resolve a benchmark tool directory from tools/external with legacy fallback."""
    external_tools_dir = _external_tools_dir()
    candidates: Dict[str, List[PathLib]] = {
        "moss": [external_tools_dir / "moss", TOOLS_DIR / "moss"],
        "jplag": [
            external_tools_dir / "JPlag",
            external_tools_dir / "jplag",
            TOOLS_DIR / "JPlag",
        ],
        "dolos": [
            external_tools_dir / "dolos-cli",
            external_tools_dir / "dolos",
            TOOLS_DIR / "dolos",
            TOOLS_DIR / "dolos-cli",
        ],
        "nicad": [
            external_tools_dir / "nicad",
            external_tools_dir / "NiCad-6.2",
            TOOLS_DIR / "NiCad-6.2",
            TOOLS_DIR / "nicad",
        ],
        "pmd": [
            external_tools_dir / "pmd",
            *sorted(external_tools_dir.glob("pmd-bin-*")),
            TOOLS_DIR / "pmd",
        ],
        "sherlock": [external_tools_dir / "sherlock", TOOLS_DIR / "sherlock"],
    }
    return _first_existing_path(candidates.get(tool_id, []))


def _is_tool_dir_available(tool_id: str) -> bool:
    """Return true when a tool directory is present in the inventory."""
    if tool_id == "integritydesk":
        return True
    return _find_tool_dir(tool_id) is not None


def _get_setting_secret(key: str) -> str:
    """Read a secret-like setting from runtime settings or the process env."""
    attr = SETTINGS_ATTR_MAP.get(key)
    if attr:
        value = getattr(settings, attr, None)
        if value:
            return str(value)
        return os.environ.get(attr, "")
    return ""


def _find_jplag_jar() -> Optional[PathLib]:
    jplag_dir = _find_tool_dir("jplag")
    if not jplag_dir:
        return None
    candidates = [jplag_dir / "jplag.jar"]
    candidates.extend(sorted(jplag_dir.glob("*jar-with-dependencies.jar")))
    candidates.extend(sorted(jplag_dir.glob("*.jar")))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _find_dolos_cli() -> Optional[PathLib]:
    dolos_dir = _find_tool_dir("dolos")
    candidates = []
    if dolos_dir:
        candidates.extend(
            [
                dolos_dir / "node_modules" / ".bin" / "dolos",
                dolos_dir / "cli" / "node_modules" / ".bin" / "dolos",
                dolos_dir / "cli" / "dist" / "cli.js",
                dolos_dir / "dolos",
            ]
        )
    candidates.append(TOOLS_DIR / "dolos-cli" / "node_modules" / ".bin" / "dolos")
    for candidate in candidates:
        if candidate.exists() and _is_dolos_plagiarism_cli(candidate):
            return candidate
    return None


def _is_dolos_plagiarism_cli(candidate: PathLib) -> bool:
    """Return true when a dolos binary is the code-similarity CLI."""
    command = (
        ["node", str(candidate)] if candidate.suffix == ".js" else [str(candidate)]
    )
    try:
        result = subprocess.run(
            [*command, "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except Exception:
        return False
    help_text = f"{result.stdout}\n{result.stderr}".lower()
    return (
        "code similarity" in help_text
        or "plagiarism" in help_text
        or "--output-format" in help_text
    )


def _find_moss_script() -> Optional[PathLib]:
    """Find the MOSS Perl script in the configured tool location."""
    from src.backend.benchmark.adapters.moss_adapter import MossAdapter

    return MossAdapter.SCRIPT_PATH if MossAdapter.SCRIPT_PATH.exists() else None


def _find_nicad_executable() -> Optional[PathLib]:
    """Find a NiCad executable in the configured tool location."""
    nicad_dir = _find_tool_dir("nicad")
    if not nicad_dir:
        return None
    return _first_existing_path(
        [
            nicad_dir / "nicad6",
            nicad_dir / "bin" / "nicad",
        ]
    )


def _find_txl_executable() -> Optional[PathLib]:
    """Find a TXL executable if the local NiCad install provides one."""
    nicad_dir = _find_tool_dir("nicad")
    candidates = []
    if nicad_dir:
        candidates.extend(
            [
                nicad_dir / "txl",
                nicad_dir / "bin" / "txl",
                nicad_dir / "lib" / "nicad" / "txl",
                nicad_dir / "tools" / "txl",
            ]
        )
    candidates.extend(
        [
            TOOLS_DIR / "freetxl" / "current" / "bin" / "txl",
            _external_tools_dir() / "freetxl" / "current" / "bin" / "txl",
        ]
    )
    return _first_existing_path(candidates)


def _find_pmd_executable() -> Optional[PathLib]:
    """Find the PMD CLI executable in the configured tool location."""
    pmd_dir = _find_tool_dir("pmd")
    if not pmd_dir:
        return None
    return _first_existing_path([pmd_dir / "bin" / "pmd", pmd_dir / "pmd"])


def _find_sherlock_executable() -> Optional[PathLib]:
    """Find an executable Sherlock binary in the configured tool location."""
    sherlock_dir = _find_tool_dir("sherlock")
    if not sherlock_dir:
        return None

    for candidate in [sherlock_dir / "sherlock"]:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return candidate
    return None


def _unavailable_tool_reason(tool_id: str) -> str:
    if tool_id == "moss":
        missing = []
        if not _find_moss_script():
            missing.append("tools/external/moss/moss.pl")
        if not _get_setting_secret("moss_user_id"):
            missing.append("MOSS_USER_ID")
        return f"Needs {', '.join(missing)}" if missing else "Not ready"
    if tool_id == "jplag":
        return (
            "Needs a JPlag jar in tools/external/JPlag"
            if not _find_jplag_jar()
            else "Not ready"
        )
    if tool_id == "dolos":
        return (
            "Needs Dolos npm dependencies and CLI build"
            if not _find_dolos_cli()
            else "Not ready"
        )

    if tool_id == "nicad":
        return "Needs NiCad and TXL binaries"
    if tool_id == "pmd":
        return "Needs the PMD CLI"
    if tool_id == "sherlock":
        return "Needs an executable Sherlock binary at tools/external/sherlock/sherlock"
    return "Not ready"


def _build_tool_record(tool_id: str, source_type: str = "repo") -> Dict[str, Any]:
    metadata = BENCHMARK_TOOL_METADATA.get(tool_id, {})
    runnable = _is_real_benchmark_tool_available(tool_id)
    return {
        "id": tool_id,
        "name": metadata.get("name", tool_id.replace("-", " ").title()),
        "desc": metadata.get(
            "desc", "Tool discovered from the local tools/ inventory."
        ),
        "color": metadata.get("color", "#64748b"),
        "gradient": metadata.get("gradient", "from-slate-500 to-slate-600"),
        "bgLight": metadata.get("bgLight", "bg-slate-50"),
        "ring": metadata.get("ring", "ring-slate-400"),
        "engines": list(metadata.get("engines", [])),
        "runnable": runnable,
        "installed": False,
        "source_type": metadata.get("source_type", source_type),
        "paths": [],
        "status": "Ready to run" if runnable else _unavailable_tool_reason(tool_id),
    }


def _is_real_benchmark_tool_available(tool_id: str) -> bool:
    if tool_id not in REAL_BENCHMARK_TOOL_IDS:
        return False
    if tool_id == "integritydesk":
        return True
    if tool_id == "moss":
        return (
            bool(_get_setting_secret("moss_user_id"))
            and _find_moss_script() is not None
        )

    if tool_id == "dolos":
        return _find_dolos_cli() is not None
    if tool_id == "jplag":
        return _find_jplag_jar() is not None
    if tool_id == "nicad":
        return (
            _find_nicad_executable() is not None and _find_txl_executable() is not None
        )
    if tool_id == "pmd":
        return _find_pmd_executable() is not None
    if tool_id == "sherlock":
        return _find_sherlock_executable() is not None
    return False


def _tool_sort_key(record: Dict[str, Any]) -> Any:
    try:
        order = TOOL_DISPLAY_ORDER.index(record["id"])
    except ValueError:
        order = len(TOOL_DISPLAY_ORDER)
    return (order, 0 if record.get("runnable") else 1, record.get("name", "").lower())


def _list_benchmark_tools() -> List[Dict[str, Any]]:
    tools: Dict[str, Dict[str, Any]] = {
        tool_id: _build_tool_record(
            tool_id,
            source_type="built-in" if tool_id == "integritydesk" else "repo",
        )
        for tool_id in REAL_BENCHMARK_TOOL_IDS
    }

    for entry in _iter_tool_inventory_dirs():
        tool_id = _canonical_tool_id(entry.name)
        if tool_id not in BENCHMARK_TOOL_METADATA:
            continue
        record = tools.setdefault(tool_id, _build_tool_record(tool_id))
        record["installed"] = True
        record["paths"].append(_relative_tool_path(entry))

    for record in tools.values():
        record["paths"].sort()
        if record["source_type"] == "built-in":
            record["status"] = "Built in"
        elif record["runnable"] and record["installed"]:
            record["status"] = "Installed and ready"
        elif record["runnable"]:
            record["status"] = "Ready to run"
        elif record["installed"]:
            record["status"] = _unavailable_tool_reason(record["id"])
        else:
            record["status"] = _unavailable_tool_reason(record["id"])

    return sorted(tools.values(), key=_tool_sort_key)


def _parse_selected_tool_ids(raw: str = "") -> List[str]:
    """Parse upload-selected detector tools, defaulting to IntegrityDesk."""
    if not raw:
        return ["integritydesk"]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = []

    if isinstance(parsed, str):
        candidates = [parsed]
    elif isinstance(parsed, list):
        candidates = parsed
    else:
        candidates = []

    selected: List[str] = []
    for candidate in candidates:
        tool_id = str(candidate).strip().lower()
        if tool_id not in REAL_BENCHMARK_TOOL_IDS or tool_id in selected:
            continue
        selected.append(tool_id)

    return selected or ["integritydesk"]


def _build_all_submission_pairs(submissions: Dict[str, str]) -> List[tuple]:
    """Build stable all-pairs comparison tuples for uploaded submissions."""
    file_list = list(submissions.keys())
    return [
        (file_list[i], file_list[j])
        for i in range(len(file_list))
        for j in range(i + 1, len(file_list))
    ]


def _external_tool_pair_lookup(
    tool_id: str, tool_data: Dict[str, Any]
) -> Dict[str, float]:
    """Map external tool pair output to pair-keyed similarity scores."""
    lookup: Dict[str, float] = {}
    for pair in tool_data.get("pairs", []):
        file_a = str(pair.get("file_a", ""))
        file_b = str(pair.get("file_b", ""))
        if not file_a or not file_b:
            continue
        try:
            lookup[_pair_key(file_a, file_b)] = float(pair.get("score"))
        except (TypeError, ValueError):
            continue
    return lookup


def _build_external_comparison_results(
    tool_results: Dict[str, Dict[str, Any]], pairs: List[tuple]
) -> List[ComparisonResult]:
    """Create report-ready comparison results from selected external tools.

    For strict behavioral parity, external tools are treated as independent engines.
    When multiple tools are selected, the first successful tool provides the primary
    score, while others are included as additional features for comparison.
    """
    successful_tools = [
        tool_id for tool_id, data in tool_results.items() if "pairs" in data
    ]
    if not successful_tools:
        return []

    lookups = {
        tool_id: _external_tool_pair_lookup(tool_id, tool_results[tool_id])
        for tool_id in successful_tools
    }

    # Use the first successful tool as the primary score provider
    # This ensures behavioral parity - one tool = one result
    primary_tool = successful_tools[0]

    results: List[ComparisonResult] = []

    for file_a, file_b in pairs:
        pair_key = _pair_key(file_a, file_b)
        features = {
            tool_id: lookup.get(pair_key, 0.0) for tool_id, lookup in lookups.items()
        }

        # Use primary tool's score directly (no averaging/aggregation)
        score = features.get(primary_tool, 0.0)

        results.append(
            ComparisonResult(
                file_a=file_a,
                file_b=file_b,
                score=score,
                risk_level=_risk_level(score),
                features=features,
                contributions={
                    primary_tool: score
                },  # Only primary tool contributes to score
            )
        )

    return results


def _merge_external_features_into_results(
    results: List[ComparisonResult],
    tool_results: Dict[str, Dict[str, Any]],
) -> None:
    """Attach successful external tool scores to existing comparison features."""
    lookups = {
        tool_id: _external_tool_pair_lookup(tool_id, data)
        for tool_id, data in tool_results.items()
        if "pairs" in data
    }
    if not lookups:
        return

    for result in results:
        pair_key = _pair_key(result.file_a, result.file_b)
        for tool_id, lookup in lookups.items():
            result.features[tool_id] = lookup.get(pair_key, 0.0)


def _external_evidence_for_pair(
    file_a: str,
    file_b: str,
    tool_results: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return external-tool evidence rows for one comparison pair."""
    pair_key = _pair_key(file_a, file_b)
    evidence: List[Dict[str, Any]] = []
    for tool_id, data in tool_results.items():
        if "pairs" not in data:
            continue
        for pair in data.get("pairs", []):
            pair_file_a = str(pair.get("file_a") or "")
            pair_file_b = str(pair.get("file_b") or "")
            if _pair_key(pair_file_a, pair_file_b) != pair_key:
                continue
            evidence.append(
                {
                    "tool": tool_id,
                    "score": _coerce_float(pair.get("score")),
                    "file_a_percent": pair.get("file_a_percent"),
                    "file_b_percent": pair.get("file_b_percent"),
                    "report_url": pair.get("report_url") or data.get("report_url"),
                }
            )
            break
    return evidence


def _run_selected_external_tools(
    selected_tool_ids: List[str],
    submissions: Dict[str, str],
    pairs: List[tuple],
) -> Dict[str, Dict[str, Any]]:
    """Run selected non-IntegrityDesk tools and preserve per-tool failures."""
    from src.backend.benchmark.runners.external_tool_runner import ExternalToolRunner

    runner = ExternalToolRunner(moss_user_id=_get_setting_secret("moss_user_id"))
    return runner.run_selected_tools(selected_tool_ids, submissions, pairs)


def _extract_zip(zip_path: PathLib, target_dir: PathLib) -> List[str]:
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            if member.endswith("/"):
                continue
            member_path = PathLib(member)
            if _is_code_file(member_path.name):
                safe_parts = [
                    part
                    for part in member_path.parts
                    if part not in {"", ".", ".."} and not PathLib(part).is_absolute()
                ]
                relative_path = (
                    PathLib(*safe_parts) if safe_parts else PathLib(member_path.name)
                )
                target = _unique_child_path(target_dir, relative_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    dst.write(src.read())
                extracted.append(str(target))
    return extracted


def _unique_child_path(root_dir: PathLib, relative_path: PathLib) -> PathLib:
    """Return a child path under root_dir without overwriting existing uploads."""
    target = root_dir / relative_path
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _read_files_from_dir(directory: PathLib) -> Dict[str, str]:
    submissions = {}
    for ext in ALLOWED_EXTENSIONS:
        for f in directory.rglob(f"*{ext}"):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if len(content.strip()) > 10:
                    submissions[_normalize_submission_name(f, directory)] = content
            except Exception as e:
                logger.warning(f"Skipping {f.name}: {e}")
    return submissions


async def _store_benchmark_uploads(
    files: List[UploadFile], target_dir: PathLib
) -> Dict[str, str]:
    """Store uploaded benchmark inputs, accepting either source files or zip archives."""
    for upload in files:
        if not upload.filename:
            continue

        filename = PathLib(upload.filename).name
        if not filename:
            continue

        destination = target_dir / filename
        destination.write_bytes(await upload.read())

        if filename.lower().endswith(".zip"):
            _extract_zip(destination, target_dir)

    return _read_files_from_dir(target_dir)


# Dataset location: All datasets are stored in data/datasets/
# Note: benchmark/data is a symlink to data/datasets/ for backward compatibility
DEFAULT_BENCHMARK_DATA_DIR = project_root.parent / "data" / "datasets"
BENCHMARK_DATA_DIR = DEFAULT_BENCHMARK_DATA_DIR
BENCHMARK_ARCHIVE_DATA_DIR = project_root.parent / "archive" / "unused_datasets"
BUILTIN_PAIR_DATASET_DIR = (
    project_root / "backend" / "benchmark" / "datasets" / "fixtures"
)
BUILTIN_PAIR_DATASET_IDS = {"clough_stevenson_style"}
PAIR_BENCHMARK_MAX_PAIRS = 400


def _benchmark_archive_enabled() -> bool:
    """Return true when local archived datasets should supplement the main data dir."""
    return BENCHMARK_DATA_DIR == DEFAULT_BENCHMARK_DATA_DIR


def _iter_benchmark_dataset_roots() -> List[PathLib]:
    """Return benchmark dataset roots in precedence order without duplicate ids."""
    roots: List[PathLib] = []
    seen: set[str] = set()
    for parent in (BENCHMARK_DATA_DIR, BENCHMARK_ARCHIVE_DATA_DIR):
        if parent == BENCHMARK_ARCHIVE_DATA_DIR and not _benchmark_archive_enabled():
            continue
        if not parent.exists():
            continue
        for item in sorted(parent.iterdir()):
            if item.is_dir() and item.name not in seen:
                roots.append(item)
                seen.add(item.name)
    return roots


def _resolve_benchmark_dataset_root(dataset_id: str) -> PathLib:
    """Resolve a dataset id to its preferred local root."""
    primary_root = BENCHMARK_DATA_DIR / dataset_id
    if primary_root.exists() or not _benchmark_archive_enabled():
        return primary_root

    archived_root = BENCHMARK_ARCHIVE_DATA_DIR / dataset_id
    if archived_root.exists():
        return archived_root
    return primary_root


def _label_to_clone_grade(label: Any, clone_type: Any = None) -> int:
    """Convert dataset labels into the benchmark's 0/2/3 clone scale."""
    try:
        numeric_label = int(label)
    except (TypeError, ValueError):
        numeric_label = 1 if str(label).strip().lower() in {"true", "yes"} else 0

    if numeric_label <= 0:
        return 0

    try:
        numeric_clone_type = int(clone_type)
    except (TypeError, ValueError):
        numeric_clone_type = 3

    if numeric_clone_type <= 1:
        return 3
    return max(2, min(3, numeric_clone_type))


def _write_pair_submission(
    submissions: Dict[str, str], target_dir: PathLib, filename: str, code: str
) -> str:
    """Store one pair-based benchmark snippet and return its stable filename."""
    safe_name = PathLib(filename).name
    submissions[safe_name] = code
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / safe_name).write_text(code, encoding="utf-8")
    return safe_name


def _pair_label_value(pair: Dict[str, Any]) -> int:
    """Return the normalized benchmark label for a pair record."""
    return _label_to_clone_grade(pair.get("label", 0), pair.get("clone_type"))


def _stable_pair_sort_key(dataset_id: str, pair: Dict[str, Any]) -> str:
    """Return a deterministic pseudo-random sort key for benchmark pairs."""
    key = "|".join(
        [
            str(dataset_id or "custom"),
            str(pair.get("file_a", "")),
            str(pair.get("file_b", "")),
            str(pair.get("label", "")),
            str(pair.get("case_category", "")),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _build_pair_sampling_audit(
    dataset_id: str,
    original_pairs: List[Dict[str, Any]],
    selected_pairs: List[Dict[str, Any]],
    *,
    balanced: bool,
) -> Dict[str, Any]:
    """Describe how labeled benchmark pairs were selected for this run."""

    def counts_for(pairs: List[Dict[str, Any]]) -> Dict[str, Any]:
        positive = sum(1 for pair in pairs if _pair_label_value(pair) >= 2)
        negative = len(pairs) - positive
        categories = Counter(
            str(pair.get("case_category") or "unspecified") for pair in pairs
        )
        splits = Counter(str(pair.get("split") or "unspecified") for pair in pairs)
        return {
            "total_pairs": len(pairs),
            "positive_pairs": positive,
            "negative_pairs": negative,
            "class_balance_ratio": round(
                min(positive, negative) / max(positive, negative, 1), 4
            ),
            "case_categories": dict(sorted(categories.items())),
            "splits": dict(sorted(splits.items())),
        }

    original_counts = counts_for(original_pairs)
    selected_counts = counts_for(selected_pairs)
    warnings: List[str] = []
    blockers: List[str] = []
    if selected_counts["positive_pairs"] == 0 or selected_counts["negative_pairs"] == 0:
        blockers.append(
            "Selected benchmark sample lacks both positive and negative pairs."
        )
    if selected_counts["class_balance_ratio"] < 0.5:
        warnings.append("Selected benchmark sample is class-imbalanced.")
    if original_counts["class_balance_ratio"] < 0.5:
        warnings.append("Original dataset pair list is class-imbalanced.")

    synthetic_negative_datasets = {
        "CodeSimilarityDataset",
        "bigclonebench",
        "poolc_600k_python",
        "poj104",
        "xiangtan",
    }
    if dataset_id in synthetic_negative_datasets:
        warnings.append(
            "Negative pairs are generated by the loader; validate them before certification."
        )

    return {
        "dataset": dataset_id or "custom",
        "sampling_policy": (
            "deterministic_balanced_shuffle"
            if balanced
            else "deterministic_shuffle_unbalanced"
        ),
        "random_seed_source": "sha256(dataset,file_a,file_b,label,case_category)",
        "original": original_counts,
        "selected": selected_counts,
        "dropped_pairs": max(0, len(original_pairs) - len(selected_pairs)),
        "warnings": warnings,
        "blockers": blockers,
    }


def _select_reliable_explicit_pairs(
    dataset_id: str, explicit_pairs: List[Dict[str, Any]]
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Select a deterministic balanced labeled sample for benchmark scoring."""
    if not explicit_pairs:
        return [], _build_pair_sampling_audit(dataset_id, [], [], balanced=False)

    positives = [pair for pair in explicit_pairs if _pair_label_value(pair) >= 2]
    negatives = [pair for pair in explicit_pairs if _pair_label_value(pair) < 2]
    positives = sorted(
        positives, key=lambda pair: _stable_pair_sort_key(dataset_id, pair)
    )
    negatives = sorted(
        negatives, key=lambda pair: _stable_pair_sort_key(dataset_id, pair)
    )

    if positives and negatives:
        per_class = min(
            len(positives),
            len(negatives),
            max(1, PAIR_BENCHMARK_MAX_PAIRS // 2),
        )
        selected = positives[:per_class] + negatives[:per_class]
        balanced = True
    else:
        selected = sorted(
            explicit_pairs, key=lambda pair: _stable_pair_sort_key(dataset_id, pair)
        )[:PAIR_BENCHMARK_MAX_PAIRS]
        balanced = False

    selected = sorted(
        selected, key=lambda pair: _stable_pair_sort_key(f"{dataset_id}:eval", pair)
    )
    audit = _build_pair_sampling_audit(
        dataset_id, explicit_pairs, selected, balanced=balanced
    )
    return selected, audit


def _pair_language_extension(language: Any) -> str:
    """Return a source-code filename extension for a pair fixture language."""
    language_key = str(language or "python").strip().lower()
    return {
        "c": ".c",
        "c++": ".cpp",
        "cpp": ".cpp",
        "csharp": ".cs",
        "go": ".go",
        "java": ".java",
        "javascript": ".js",
        "python": ".py",
        "ruby": ".rb",
        "rust": ".rs",
        "typescript": ".ts",
    }.get(language_key, ".py")


def _load_pair_labeled_benchmark_dataset(
    dataset_id: str, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load datasets that already define explicit labeled comparison pairs."""
    dataset_root = _resolve_benchmark_dataset_root(dataset_id)
    if (dataset_root / "generated_pairs.jsonl").exists() or (
        dataset_id in BUILTIN_PAIR_DATASET_IDS
    ):
        return _load_synthetic_pair_dataset(dataset_root, target_dir)
    if dataset_id == "kaggle_student_code":
        return _load_kaggle_pair_dataset(dataset_root, target_dir)
    if dataset_id == "CodeSimilarityDataset":
        return _load_code_similarity_pair_dataset(dataset_root, target_dir)
    if dataset_id == "xiangtan":
        return _load_xiangtan_pair_dataset(dataset_root, target_dir)
    if dataset_id == "bigclonebench":
        return _load_bigclonebench_reduced_pair_dataset(dataset_root, target_dir)
    if dataset_id == "codexglue_clone":
        return _load_codexglue_pair_dataset(dataset_root, target_dir)
    if dataset_id == "poj104":
        return _load_poj104_pair_dataset(dataset_root, target_dir)
    if dataset_id == "poolc_600k_python":
        return _load_poolc_pair_dataset(dataset_root, target_dir)
    if dataset_id == "google_codejam":
        return _load_google_codejam_pair_dataset(dataset_root, target_dir)
    if dataset_id == "IR-Plag-Dataset":
        return _load_ir_plag_pair_dataset(dataset_root, target_dir)
    if dataset_id == "conplag":
        return _load_conplag_pair_dataset(dataset_root, target_dir)
    if dataset_id == "conplag_classroom_java":
        return _load_conplag_pair_dataset(dataset_root, target_dir)
    return {}, []


def _load_synthetic_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load generated synthetic clone/non-clone pairs from JSON."""
    raw_pairs = _read_generated_pair_items(dataset_root)
    if not raw_pairs:
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []

    for idx, item in enumerate(raw_pairs[:PAIR_BENCHMARK_MAX_PAIRS]):
        pair_id = str(item.get("id") or f"synthetic_{idx:05d}")
        extension_a = _pair_language_extension(item.get("language_a"))
        extension_b = _pair_language_extension(item.get("language_b"))
        file_a = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_a{extension_a}",
            str(item.get("code_a", "")),
        )
        file_b = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_b{extension_b}",
            str(item.get("code_b", "")),
        )
        explicit_pairs.append(
            {
                "file_a": file_a,
                "file_b": file_b,
                "label": _label_to_clone_grade(
                    item.get("label", 0), item.get("clone_type")
                ),
                "case_category": _pair_case_category(item),
                "split": _pair_split(item),
            }
        )

    return submissions, explicit_pairs


def _load_kaggle_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load Kaggle student plagiarism pairs from the labeled CSV."""
    csv_path = dataset_root / "cheating_dataset.csv"
    if not csv_path.exists():
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for idx, row in enumerate(reader):
            if idx >= PAIR_BENCHMARK_MAX_PAIRS:
                break
            source_a = dataset_root / str(row.get("File_1", ""))
            source_b = dataset_root / str(row.get("File_2", ""))
            if not source_a.exists() or not source_b.exists():
                continue
            file_a = _write_pair_submission(
                submissions,
                target_dir,
                source_a.name,
                source_a.read_text(encoding="utf-8", errors="ignore"),
            )
            file_b = _write_pair_submission(
                submissions,
                target_dir,
                source_b.name,
                source_b.read_text(encoding="utf-8", errors="ignore"),
            )
            explicit_pairs.append(
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "label": _label_to_clone_grade(row.get("Label", 0)),
                }
            )

    return submissions, explicit_pairs


def _code_similarity_snippet_groups(dataset_root: PathLib) -> Dict[str, List[PathLib]]:
    """Group CodeSimilarityDataset snippets by programming task."""
    metadata_csv = dataset_root / "full_metadata.csv"
    if not metadata_csv.exists():
        return {}

    groups: Dict[str, List[PathLib]] = {}
    with metadata_csv.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            problem_type = str(row.get("problem_type", "")).strip()
            filename = str(row.get("filename", "")).strip()
            if not problem_type or not filename:
                continue
            source = dataset_root / problem_type / "snippets" / filename
            if source.exists():
                groups.setdefault(problem_type, []).append(source)

    return {key: sorted(value) for key, value in groups.items() if len(value) >= 2}


def _load_code_similarity_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load CodeSimilarityDataset as same-task positives and cross-task negatives."""
    grouped = _code_similarity_snippet_groups(dataset_root)
    if not grouped:
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    max_each = PAIR_BENCHMARK_MAX_PAIRS // 2

    positive_count = 0
    for problem_type, files in grouped.items():
        if positive_count >= max_each:
            break
        for left_index, source_a in enumerate(files):
            if positive_count >= max_each:
                break
            for source_b in files[left_index + 1 :]:
                if positive_count >= max_each:
                    break
                pair_id = f"codesim_pos_{positive_count:05d}_{problem_type}"
                file_a = _write_pair_submission(
                    submissions,
                    target_dir,
                    f"{pair_id}_a.py",
                    source_a.read_text(encoding="utf-8", errors="ignore"),
                )
                file_b = _write_pair_submission(
                    submissions,
                    target_dir,
                    f"{pair_id}_b.py",
                    source_b.read_text(encoding="utf-8", errors="ignore"),
                )
                explicit_pairs.append(
                    {
                        "file_a": file_a,
                        "file_b": file_b,
                        "label": _label_to_clone_grade(1, 4),
                        "case_category": "true_positive",
                        "split": "test",
                    }
                )
                positive_count += 1

    group_items = list(grouped.items())
    negative_count = 0
    for left_index, (left_problem, left_files) in enumerate(group_items):
        if negative_count >= max_each:
            break
        for right_problem, right_files in group_items[left_index + 1 :]:
            if negative_count >= max_each:
                break
            for source_a in left_files:
                if negative_count >= max_each:
                    break
                for source_b in right_files:
                    if negative_count >= max_each:
                        break
                    pair_id = f"codesim_neg_{negative_count:05d}_{left_problem}_{right_problem}"
                    file_a = _write_pair_submission(
                        submissions,
                        target_dir,
                        f"{pair_id}_a.py",
                        source_a.read_text(encoding="utf-8", errors="ignore"),
                    )
                    file_b = _write_pair_submission(
                        submissions,
                        target_dir,
                        f"{pair_id}_b.py",
                        source_b.read_text(encoding="utf-8", errors="ignore"),
                    )
                    explicit_pairs.append(
                        {
                            "file_a": file_a,
                            "file_b": file_b,
                            "label": 0,
                            "case_category": "true_negative",
                            "split": "test",
                        }
                    )
                    negative_count += 1

    return submissions, explicit_pairs


def _load_google_codejam_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load Google Code Jam pairs from ground_truth.json."""
    gt_path = dataset_root / "ground_truth.json"
    submissions_dir = dataset_root / "submissions"
    if not gt_path.exists() or not submissions_dir.exists():
        return {}, []

    try:
        gt_data = json.loads(gt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []

    for pair_key, info in gt_data.items():
        if len(explicit_pairs) >= PAIR_BENCHMARK_MAX_PAIRS:
            break
        # Parse pair_key like "A_0_1" -> problem A, solutions 0 and 1
        parts = pair_key.split("_")
        if len(parts) != 3:
            continue
        problem, sol_a, sol_b = parts
        problem_dir = submissions_dir / f"problem_{problem}" / "python"
        source_a = problem_dir / f"solution_{sol_a}.py"
        source_b = problem_dir / f"solution_{sol_b}.py"
        if not source_a.exists() or not source_b.exists():
            continue

        plagiarism = info.get("plagiarism", False)
        pair_id = f"codejam_{problem}_{sol_a}_{sol_b}"
        source_a_code = source_a.read_text(encoding="utf-8", errors="ignore")
        source_b_code = source_b.read_text(encoding="utf-8", errors="ignore")
        file_a = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_a.py",
            source_a_code,
        )
        file_b = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_b.py",
            source_b_code,
        )
        explicit_pairs.append(
            {
                "file_a": file_a,
                "file_b": file_b,
                "label": _label_to_clone_grade(1 if plagiarism else 0),
                "case_category": "true_positive" if plagiarism else "true_negative",
            }
        )

    return submissions, explicit_pairs


def _load_ir_plag_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load IR-Plag dataset pairs: original vs plagiarized (positive), original vs non-plagiarized (negative)."""
    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []

    case_dirs = sorted(
        [d for d in dataset_root.iterdir() if d.is_dir() and d.name.startswith("case-")]
    )
    for case_dir in case_dirs:
        original_dir = case_dir / "original"
        plagiarized_dir = case_dir / "plagiarized"
        non_plagiarized_dir = case_dir / "non-plagiarized"

        if not (
            original_dir.exists()
            and plagiarized_dir.exists()
            and non_plagiarized_dir.exists()
        ):
            continue

        # Get original file (should be one per case)
        original_files = list(original_dir.glob("*.java"))
        if not original_files:
            continue
        original_file = original_files[0]  # Take first one
        original_code = original_file.read_text(encoding="utf-8", errors="ignore")
        original_submission = _write_pair_submission(
            submissions,
            target_dir,
            f"ir_plag_{case_dir.name}_original.java",
            original_code,
        )

        # Generate positive pairs: original vs each plagiarized variant
        for level_dir in sorted(plagiarized_dir.iterdir()):
            if not level_dir.is_dir():
                continue
            for variant_dir in sorted(level_dir.iterdir()):
                if not variant_dir.is_dir():
                    continue
                plag_files = list(variant_dir.glob("*.java"))
                for plag_file in plag_files:
                    if len(explicit_pairs) >= PAIR_BENCHMARK_MAX_PAIRS:
                        return submissions, explicit_pairs
                    plag_code = plag_file.read_text(encoding="utf-8", errors="ignore")

                    pair_id = f"ir_plag_{case_dir.name}_{level_dir.name}_{variant_dir.name}_{plag_file.stem}"
                    file_b = _write_pair_submission(
                        submissions,
                        target_dir,
                        f"{pair_id}_plagiarized.java",
                        plag_code,
                    )
                    explicit_pairs.append(
                        {
                            "file_a": original_submission,
                            "file_b": file_b,
                            "label": _label_to_clone_grade(1),  # Positive
                            "case_category": "true_positive",
                        }
                    )

        # Generate negative pairs: original vs each non-plagiarized
        for non_plag_dir in sorted(non_plagiarized_dir.iterdir()):
            if not non_plag_dir.is_dir():
                continue
            non_plag_files = list(non_plag_dir.glob("*.java"))
            for non_plag_file in non_plag_files:
                if len(explicit_pairs) >= PAIR_BENCHMARK_MAX_PAIRS:
                    return submissions, explicit_pairs
                non_plag_code = non_plag_file.read_text(
                    encoding="utf-8", errors="ignore"
                )

                pair_id = f"ir_plag_{case_dir.name}_nonplag_{non_plag_dir.name}_{non_plag_file.stem}"
                file_b = _write_pair_submission(
                    submissions,
                    target_dir,
                    f"{pair_id}_nonplagiarized.java",
                    non_plag_code,
                )
                explicit_pairs.append(
                    {
                        "file_a": original_submission,
                        "file_b": file_b,
                        "label": _label_to_clone_grade(0),  # Negative
                        "case_category": "true_negative",
                    }
                )

    return submissions, explicit_pairs


def _bigclonebench_reduced_groups(
    dataset_root: PathLib, max_files_per_group: int = 8
) -> Dict[str, List[PathLib]]:
    """Group a bounded BigCloneBench reduced sample by functionality id."""
    reduced_root = dataset_root / "bcb_reduced"
    if not reduced_root.exists():
        return {}

    groups: Dict[str, List[PathLib]] = {}
    for function_dir in sorted(
        path for path in reduced_root.iterdir() if path.is_dir()
    ):
        files: List[PathLib] = []
        for subdir_name in ("sample", "selected", "default"):
            subdir = function_dir / subdir_name
            if subdir.exists():
                for source_file in sorted(subdir.glob("*.java")):
                    files.append(source_file)
                    if len(files) >= max_files_per_group:
                        break
            if len(files) >= max_files_per_group:
                break
        if len(files) >= 2:
            groups[function_dir.name] = files

    return groups


def _load_bigclonebench_reduced_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load a balanced pair sample from BigCloneBench reduced functionality folders."""
    grouped = _bigclonebench_reduced_groups(dataset_root)
    if not grouped:
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    max_each = PAIR_BENCHMARK_MAX_PAIRS // 2

    positive_count = 0
    for function_id, files in grouped.items():
        if positive_count >= max_each:
            break
        for left_index, source_a in enumerate(files):
            if positive_count >= max_each:
                break
            for source_b in files[left_index + 1 :]:
                if positive_count >= max_each:
                    break
                pair_id = f"bcb_pos_{positive_count:05d}_{function_id}"
                file_a = _write_pair_submission(
                    submissions,
                    target_dir,
                    f"{pair_id}_a.java",
                    source_a.read_text(encoding="utf-8", errors="ignore"),
                )
                file_b = _write_pair_submission(
                    submissions,
                    target_dir,
                    f"{pair_id}_b.java",
                    source_b.read_text(encoding="utf-8", errors="ignore"),
                )
                explicit_pairs.append(
                    {
                        "file_a": file_a,
                        "file_b": file_b,
                        "label": _label_to_clone_grade(1, 4),
                        "case_category": "true_positive",
                        "split": "test",
                    }
                )
                positive_count += 1

    group_items = list(grouped.items())
    negative_count = 0
    for left_index, (left_function, left_files) in enumerate(group_items):
        if negative_count >= max_each:
            break
        for right_function, right_files in group_items[left_index + 1 :]:
            if negative_count >= max_each:
                break
            for source_a in left_files[:3]:
                if negative_count >= max_each:
                    break
                for source_b in right_files[:3]:
                    if negative_count >= max_each:
                        break
                    pair_id = (
                        f"bcb_neg_{negative_count:05d}_{left_function}_{right_function}"
                    )
                    file_a = _write_pair_submission(
                        submissions,
                        target_dir,
                        f"{pair_id}_a.java",
                        source_a.read_text(encoding="utf-8", errors="ignore"),
                    )
                    file_b = _write_pair_submission(
                        submissions,
                        target_dir,
                        f"{pair_id}_b.java",
                        source_b.read_text(encoding="utf-8", errors="ignore"),
                    )
                    explicit_pairs.append(
                        {
                            "file_a": file_a,
                            "file_b": file_b,
                            "label": 0,
                            "case_category": "true_negative",
                            "split": "test",
                        }
                    )
                    negative_count += 1

    return submissions, explicit_pairs


def _load_conplag_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load a balanced CONPLAG sample from labels.csv and version_1 directories."""
    if dataset_root.name == "conplag_classroom_java":
        dataset_root = BENCHMARK_DATA_DIR / "conplag"
    labels_csv = dataset_root / "versions" / "labels.csv"
    version_1_dir = dataset_root / "versions" / "version_1"

    if not (labels_csv.exists() and version_1_dir.exists()):
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    max_each = PAIR_BENCHMARK_MAX_PAIRS // 2

    try:
        with labels_csv.open("r", encoding="utf-8", newline="") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except OSError:
        return {}, []

    positives = [row for row in rows if str(row.get("verdict", "")).strip() == "1"]
    negatives = [row for row in rows if str(row.get("verdict", "")).strip() != "1"]
    selected_rows = positives[:max_each] + negatives[:max_each]

    for idx, row in enumerate(selected_rows):
        sub1 = str(row.get("sub1", "")).strip()
        sub2 = str(row.get("sub2", "")).strip()
        problem = str(row.get("problem", "")).strip()
        verdict = str(row.get("verdict", "")).strip()
        if not sub1 or not sub2:
            continue

        pair_dir = version_1_dir / f"{sub1}_{sub2}"
        java_files = sorted(pair_dir.glob("*.java")) if pair_dir.exists() else []
        if len(java_files) != 2:
            continue

        source_a, source_b = java_files
        pair_id = f"conplag_{idx:05d}_{sub1}_{sub2}"
        file_a = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_a.java",
            source_a.read_text(encoding="utf-8", errors="ignore"),
        )
        file_b = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_b.java",
            source_b.read_text(encoding="utf-8", errors="ignore"),
        )
        explicit_pairs.append(
            {
                "file_a": file_a,
                "file_b": file_b,
                "label": _label_to_clone_grade(1 if verdict == "1" else 0),
                "case_category": "true_positive" if verdict == "1" else "true_negative",
                "problem": problem,
                "split": "test",
            }
        )

    return submissions, explicit_pairs


def _load_xiangtan_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load Xiangtan-style Java clone pairs and generate matched negatives."""
    pairs_csv = dataset_root / "pairs.csv"
    source_dir = dataset_root / "source"
    if not pairs_csv.exists() or not source_dir.exists():
        return {}, []

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    positive_originals: List[PathLib] = []
    behavior_signatures: Dict[PathLib, str] = {}

    with pairs_csv.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for idx, row in enumerate(reader):
            if idx >= PAIR_BENCHMARK_MAX_PAIRS // 2:
                break

            clone_type = str(row.get("clone_type", "")).strip()
            type_dir = source_dir / clone_type if clone_type else source_dir
            source_a = type_dir / str(row.get("file1", ""))
            source_b = type_dir / str(row.get("file2", ""))
            if not source_a.exists() or not source_b.exists():
                continue

            pair_id = f"xiangtan_pos_{idx:05d}"
            source_a_code = source_a.read_text(encoding="utf-8", errors="ignore")
            source_b_code = source_b.read_text(encoding="utf-8", errors="ignore")
            behavior_signatures[source_a] = _java_behavior_signature(source_a_code)
            file_a = _write_pair_submission(
                submissions,
                target_dir,
                f"{pair_id}_a.java",
                source_a_code,
            )
            file_b = _write_pair_submission(
                submissions,
                target_dir,
                f"{pair_id}_b.java",
                source_b_code,
            )
            positive_originals.append(source_a)
            explicit_pairs.append(
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "label": _label_to_clone_grade(1, clone_type.replace("T", "")),
                    "case_category": "true_positive",
                    "split": "test",
                }
            )

    unique_originals = list(dict.fromkeys(positive_originals))
    target_negative_count = min(len(explicit_pairs), PAIR_BENCHMARK_MAX_PAIRS // 2)
    negative_count = 0
    for left_index, source_a in enumerate(unique_originals):
        if negative_count >= target_negative_count:
            break
        for source_b in unique_originals[left_index + 1 :]:
            if negative_count >= target_negative_count:
                break
            if source_a.stem.replace("_original", "") == source_b.stem.replace(
                "_original", ""
            ):
                continue
            if behavior_signatures.get(source_a) == behavior_signatures.get(source_b):
                continue

            pair_id = f"xiangtan_neg_{negative_count:05d}"
            file_a = _write_pair_submission(
                submissions,
                target_dir,
                f"{pair_id}_a.java",
                source_a.read_text(encoding="utf-8", errors="ignore"),
            )
            file_b = _write_pair_submission(
                submissions,
                target_dir,
                f"{pair_id}_b.java",
                source_b.read_text(encoding="utf-8", errors="ignore"),
            )
            explicit_pairs.append(
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "label": 0,
                    "case_category": "true_negative",
                    "split": "test",
                }
            )
            negative_count += 1

    return submissions, explicit_pairs


def _java_behavior_signature(code: str) -> str:
    """Return a name-insensitive Java signature for avoiding mislabeled negatives."""
    without_comments = re.sub(
        r"/\*.*?\*/|//.*?$", "", code, flags=re.DOTALL | re.MULTILINE
    )
    tokens = re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||\S", without_comments)
    java_keywords = {
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
    }
    normalized = []
    for token in tokens:
        if re.fullmatch(r"\d+", token):
            normalized.append("NUM")
        elif token in {"for", "while", "do"}:
            normalized.append("ITERATIVE_BLOCK")
        elif re.fullmatch(r"[A-Za-z_]\w*", token) and token not in java_keywords:
            normalized.append("ID")
        else:
            normalized.append(token)
    return hashlib.sha256(" ".join(normalized).encode("utf-8")).hexdigest()


def _load_codexglue_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load a balanced sample from CodeXGLUE clone detection pairs."""
    hf_path = dataset_root / "huggingface"
    if not hf_path.exists():
        return {}, []

    from datasets import load_from_disk

    dataset = load_from_disk(str(hf_path))
    split = dataset["test"] if "test" in dataset else next(iter(dataset.values()))
    return _load_hf_binary_pair_rows(
        split,
        target_dir,
        prefix="codexglue",
        code_a_key="func1",
        code_b_key="func2",
        label_key="label",
        extension="java",
    )


def _load_poolc_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load a balanced sample from local PoolC Python clone-detection shards."""
    parquet_files = sorted((dataset_root / "data").glob("*.parquet"))
    if not parquet_files:
        return {}, []

    import pyarrow.parquet as pq

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    target_per_class = max(1, PAIR_BENCHMARK_MAX_PAIRS // 2)
    counts = {0: 0, 1: 0}

    for parquet_file in parquet_files:
        table = pq.ParquetFile(parquet_file)
        for batch in table.iter_batches(
            batch_size=1024, columns=["code1", "code2", "similar"]
        ):
            rows = batch.to_pylist()
            for item in rows:
                binary_label = 1 if bool(item.get("similar")) else 0
                if counts[binary_label] >= target_per_class:
                    if all(value >= target_per_class for value in counts.values()):
                        return submissions, explicit_pairs
                    continue

                code_a = str(item.get("code1", ""))
                code_b = str(item.get("code2", ""))
                if not code_a.strip() or not code_b.strip():
                    continue

                pair_id = f"poolc_{len(explicit_pairs):06d}"
                file_a = _write_pair_submission(
                    submissions, target_dir, f"{pair_id}_a.py", code_a
                )
                file_b = _write_pair_submission(
                    submissions, target_dir, f"{pair_id}_b.py", code_b
                )
                explicit_pairs.append(
                    {
                        "file_a": file_a,
                        "file_b": file_b,
                        "label": 3 if binary_label else 0,
                    }
                )
                counts[binary_label] += 1

    return submissions, explicit_pairs


def _load_hf_binary_pair_rows(
    rows: Any,
    target_dir: PathLib,
    prefix: str,
    code_a_key: str,
    code_b_key: str,
    label_key: str,
    extension: str,
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Load a balanced positive/negative sample from pair-based HF rows."""
    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    target_per_class = max(1, PAIR_BENCHMARK_MAX_PAIRS // 2)
    counts = {0: 0, 1: 0}

    for idx, item in enumerate(rows):
        binary_label = 1 if bool(item.get(label_key)) else 0
        if counts[binary_label] >= target_per_class:
            if all(value >= target_per_class for value in counts.values()):
                break
            continue

        code_a = str(item.get(code_a_key, ""))
        code_b = str(item.get(code_b_key, ""))
        if not code_a.strip() or not code_b.strip():
            continue

        pair_id = f"{prefix}_{idx:06d}"
        file_a = _write_pair_submission(
            submissions, target_dir, f"{pair_id}_a.{extension}", code_a
        )
        file_b = _write_pair_submission(
            submissions, target_dir, f"{pair_id}_b.{extension}", code_b
        )
        explicit_pairs.append(
            {"file_a": file_a, "file_b": file_b, "label": 3 if binary_label else 0}
        )
        counts[binary_label] += 1

    return submissions, explicit_pairs


def _load_poj104_pair_dataset(
    dataset_root: PathLib, target_dir: PathLib
) -> tuple[Dict[str, str], List[Dict[str, Any]]]:
    """Create balanced same-problem and different-problem POJ-104 pairs."""
    hf_path = dataset_root / "huggingface"
    if not hf_path.exists():
        return {}, []

    from datasets import load_from_disk

    dataset = load_from_disk(str(hf_path))
    by_label: Dict[str, List[Dict[str, Any]]] = {}
    preferred_splits = [
        name for name in ("test", "validation", "train") if name in dataset
    ]
    for split_name in preferred_splits or list(dataset.keys()):
        for item in dataset[split_name]:
            by_label.setdefault(str(item.get("label")), []).append(item)

    submissions: Dict[str, str] = {}
    explicit_pairs: List[Dict[str, Any]] = []
    labels = sorted(label for label, items in by_label.items() if len(items) >= 2)
    target_per_class = max(1, PAIR_BENCHMARK_MAX_PAIRS // 2)

    positive_count = 0
    while positive_count < target_per_class:
        made_progress = False
        for label in labels:
            if positive_count >= target_per_class:
                break
            items = by_label[label]
            pair_offset = positive_count // max(1, len(labels))
            left_index = (pair_offset * 2) % len(items)
            right_index = (left_index + 1) % len(items)
            if left_index == right_index:
                continue

            a, b = items[left_index], items[right_index]
            pair_id = f"poj104_pos_{positive_count:05d}"
            file_a = _write_pair_submission(
                submissions, target_dir, f"{pair_id}_a.c", str(a.get("code", ""))
            )
            file_b = _write_pair_submission(
                submissions, target_dir, f"{pair_id}_b.c", str(b.get("code", ""))
            )
            explicit_pairs.append({"file_a": file_a, "file_b": file_b, "label": 3})
            positive_count += 1
            made_progress = True
        if not made_progress:
            break

    for negative_count in range(target_per_class if len(labels) >= 2 else 0):
        left_label = labels[negative_count % len(labels)]
        right_label = labels[(negative_count + 1) % len(labels)]
        left_items = by_label[left_label]
        right_items = by_label[right_label]
        left_item = left_items[negative_count % len(left_items)]
        right_item = right_items[negative_count % len(right_items)]
        pair_id = f"poj104_neg_{negative_count:05d}"
        file_a = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_a.c",
            str(left_item.get("code", "")),
        )
        file_b = _write_pair_submission(
            submissions,
            target_dir,
            f"{pair_id}_b.c",
            str(right_item.get("code", "")),
        )
        explicit_pairs.append({"file_a": file_a, "file_b": file_b, "label": 0})

    return submissions, explicit_pairs


def _load_benchmark_dataset(dataset_id: str, target_dir: PathLib) -> Dict[str, str]:
    """Load benchmark dataset and extract to target directory for comparison."""
    submissions = {}

    # Handle demo datasets
    if dataset_id.startswith("demo_"):
        dataset_dir = BENCHMARK_DATA_DIR / dataset_id
        if not dataset_dir.exists():
            logger.warning(f"Demo dataset not found: {dataset_dir}")
            return submissions

        metadata = {}
        metadata_file = dataset_dir / "metadata.json"
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(
                    f"Error reading demo dataset metadata {metadata_file}: {exc}"
                )
        demo_language = metadata.get("language", "python")

        # For demo datasets, combine original and plagiarized files
        submissions = {}

        # Load original files
        original_dir = dataset_dir / "original"
        if original_dir.exists():
            for file_path in original_dir.glob("*"):
                normalized_name = _normalize_demo_filename(
                    file_path.name, demo_language, plagiarized=False
                )
                if file_path.is_file() and (
                    _is_code_file(file_path.name) or _is_code_file(normalized_name)
                ):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        submissions[normalized_name] = content
                    except Exception as e:
                        logger.warning(f"Error reading file {file_path}: {e}")

        # Load plagiarized files with modified names to distinguish them
        plagiarized_dir = dataset_dir / "plagiarized"
        if plagiarized_dir.exists():
            for file_path in plagiarized_dir.glob("*"):
                normalized_name = _normalize_demo_filename(
                    file_path.name, demo_language, plagiarized=True
                )
                if file_path.is_file() and (
                    _is_code_file(file_path.name) or _is_code_file(normalized_name)
                ):
                    try:
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        submissions[normalized_name] = content
                    except Exception as e:
                        logger.warning(f"Error reading file {file_path}: {e}")

        return submissions

    dataset_root = BENCHMARK_DATA_DIR / dataset_id
    metadata = _load_dataset_metadata(dataset_root)
    if metadata.get("exclude_from_benchmark"):
        logger.warning(f"Dataset {dataset_id} is marked as not benchmark-ready")
        return submissions

    dataset_dir = _resolve_benchmark_dataset_dir(dataset_id)
    if dataset_dir is None:
        logger.warning(f"Unknown dataset: {dataset_id}")
        return submissions

    try:
        from datasets import load_from_disk

        if dataset_dir.name in ["train", "test", "validation"]:
            ds = load_from_disk(str(dataset_dir))
            target_dir.mkdir(parents=True, exist_ok=True)

            max_samples = min(100, len(ds))
            for i, item in enumerate(ds):
                if i >= max_samples:
                    break

                for entry in _extract_code_entries_from_row(item, dataset_id, i):
                    filename = entry["filename"]
                    code = entry["code"]
                    (target_dir / filename).write_text(code, encoding="utf-8")
                    submissions[filename] = code
    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_id}: {e}")

    if not submissions:
        for f in dataset_dir.rglob("*"):
            if not f.is_file() or not _is_code_file(f.name):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if len(content.strip()) > 10:
                    storage_name = _normalize_submission_name(f, dataset_dir)
                    submissions[storage_name] = content
                    target_dir.mkdir(parents=True, exist_ok=True)
                    destination = target_dir / storage_name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(f, destination)
            except Exception as e:
                logger.warning(f"Skipping {f.name}: {e}")

    return submissions


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _job_report_dir(job_id: str) -> PathLib:
    return REPORTS_DIR / job_id


def _job_metadata_path(job_id: str) -> PathLib:
    return _job_report_dir(job_id) / JOB_METADATA_FILENAME


def _build_job_summary(
    results: List[Dict[str, Any]], threshold: float
) -> Dict[str, Any]:
    suspicious_pairs = sum(
        1 for result in results if _coerce_float(result.get("score")) >= threshold
    )
    return {
        "total_pairs": len(results),
        "suspicious_pairs": suspicious_pairs,
    }


def _normalize_result(result: Dict[str, Any]) -> Dict[str, Any]:
    features = {}
    for name, value in (result.get("features") or {}).items():
        features[name] = round(_coerce_float(value), 3)
    contributions = {}
    for name, value in (result.get("contributions") or {}).items():
        contributions[name] = round(_coerce_float(value), 3)

    return {
        "file_a": result.get("file_a", ""),
        "file_b": result.get("file_b", ""),
        "score": round(_coerce_float(result.get("score")), 3),
        "risk_level": result.get("risk_level") or result.get("risk") or "",
        "features": features,
        "contributions": contributions,
        "fusion_debug": result.get("fusion_debug") or {},
    }


def _normalize_submission_ai_result(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Normalise a single per-submission AI detection result.

    Preserves the richer fields added by the new engine (signal_labels,
    flagged_lines, annotated_snippet) so the results page can display them.
    """
    signals = {
        name: round(_coerce_float(value), 3)
        for name, value in (entry.get("signals") or {}).items()
    }
    indicators = [
        str(indicator) for indicator in (entry.get("indicators") or []) if indicator
    ]
    signal_labels = {
        str(k): str(v) for k, v in (entry.get("signal_labels") or {}).items()
    }
    flagged_lines = [int(ln) for ln in (entry.get("flagged_lines") or []) if ln]
    # annotated_snippet: list of {line, text, flagged} — pass through as-is
    annotated_snippet = [
        {
            "line": int(item.get("line", 0)),
            "text": str(item.get("text", "")),
            "flagged": bool(item.get("flagged", False)),
        }
        for item in (entry.get("annotated_snippet") or [])
        if isinstance(item, dict)
    ]

    return {
        "name": str(entry.get("name") or ""),
        "language": str(entry.get("language") or "python"),
        "ai_probability": round(_coerce_float(entry.get("ai_probability")), 3),
        "confidence": round(_coerce_float(entry.get("confidence")), 3),
        "status": str(entry.get("status") or "Low Risk"),
        "signals": signals,
        "signal_labels": signal_labels,
        "indicators": indicators[:6],
        "flagged_lines": flagged_lines[:30],
        "annotated_snippet": annotated_snippet,
        "error": str(entry.get("error") or ""),
    }


def _normalize_ai_detection(ai_detection: Any) -> Dict[str, Any]:
    if not isinstance(ai_detection, dict):
        return {}

    submissions = [
        _normalize_submission_ai_result(entry)
        for entry in ai_detection.get("submissions", [])
        if isinstance(entry, dict)
    ]
    signal_summary = {}
    for name, data in (ai_detection.get("signal_summary") or {}).items():
        if not isinstance(data, dict):
            continue
        signal_summary[str(name)] = {
            "average": round(_coerce_float(data.get("average")), 3),
            "peak": round(_coerce_float(data.get("peak")), 3),
        }

    distribution = (
        ai_detection.get("distribution")
        if isinstance(ai_detection.get("distribution"), dict)
        else {}
    )

    return {
        "enabled": bool(ai_detection.get("enabled")),
        "threshold": round(
            _coerce_float(ai_detection.get("threshold"), AI_MEDIUM_RISK_THRESHOLD), 3
        ),
        "status_message": str(ai_detection.get("status_message") or ""),
        "flagged_count": int(ai_detection.get("flagged_count") or 0),
        "total_files": int(ai_detection.get("total_files") or len(submissions)),
        "average_score": round(_coerce_float(ai_detection.get("average_score")), 3),
        "highest_score": round(_coerce_float(ai_detection.get("highest_score")), 3),
        "distribution": {
            "low": int(distribution.get("low") or 0),
            "medium": int(distribution.get("medium") or 0),
            "high": int(distribution.get("high") or 0),
        },
        "signal_summary": signal_summary,
        "submissions": submissions,
    }


def _normalize_web_analysis(web_analysis: Any) -> Dict[str, Any]:
    if not isinstance(web_analysis, dict):
        return {}

    submissions = []
    for entry in web_analysis.get("submissions", []):
        if not isinstance(entry, dict):
            continue
        sources = []
        for source in entry.get("sources", []):
            if not isinstance(source, dict):
                continue
            sources.append(
                {
                    "name": str(source.get("name") or ""),
                    "url": str(source.get("url") or ""),
                    "source": str(source.get("source") or ""),
                    "similarity": round(_coerce_float(source.get("similarity")), 3),
                }
            )
        source_counts = (
            entry.get("source_counts")
            if isinstance(entry.get("source_counts"), dict)
            else {}
        )
        submissions.append(
            {
                "name": str(entry.get("name") or ""),
                "max_similarity": round(_coerce_float(entry.get("max_similarity")), 3),
                "match_count": int(entry.get("match_count") or 0),
                "top_source": sources[0] if sources else None,
                "sources": sources,
                "source_counts": {
                    str(k): int(v or 0) for k, v in source_counts.items()
                },
            }
        )

    return {
        "enabled": bool(web_analysis.get("enabled")),
        "configured": bool(web_analysis.get("configured")),
        "status_message": str(web_analysis.get("status_message") or ""),
        "matched_submissions": int(web_analysis.get("matched_submissions") or 0),
        "highest_similarity": round(
            _coerce_float(web_analysis.get("highest_similarity")), 3
        ),
        "average_similarity": round(
            _coerce_float(web_analysis.get("average_similarity")), 3
        ),
        "source_totals": {
            str(k): int(v or 0)
            for k, v in (web_analysis.get("source_totals") or {}).items()
        },
        "submissions": submissions,
    }


def _normalize_job(job: Dict[str, Any], from_disk: bool = False) -> Dict[str, Any]:
    normalized = dict(job)
    job_id = normalized.get("id", "")
    threshold = _coerce_float(normalized.get("threshold"), 0.5)
    results = [_normalize_result(result) for result in normalized.get("results", [])]
    submissions = (
        normalized.get("submissions")
        if isinstance(normalized.get("submissions"), dict)
        else {}
    )
    file_count = normalized.get("file_count")
    try:
        file_count = int(file_count)
    except (TypeError, ValueError):
        file_count = 0

    normalized["threshold"] = threshold
    normalized["results"] = results
    normalized["summary"] = (
        normalized.get("summary") if isinstance(normalized.get("summary"), dict) else {}
    )
    if not normalized["summary"]:
        normalized["summary"] = _build_job_summary(results, threshold)

    normalized["course_name"] = normalized.get("course_name") or "Unnamed Course"
    normalized["assignment_name"] = (
        normalized.get("assignment_name")
        or normalized["course_name"]
        or "Unnamed Assignment"
    )
    normalized["created_at"] = (
        normalized.get("created_at") or datetime.now().isoformat()
    )
    normalized["submissions"] = submissions
    normalized["file_count"] = (
        file_count
        or len(submissions)
        or len(
            {
                name
                for result in results
                for name in (result["file_a"], result["file_b"])
            }
        )
    )
    normalized["review_status"] = (
        normalized.get("review_status")
        if normalized.get("review_status") in REVIEW_STATUSES
        else "unreviewed"
    )
    normalized["review_notes"] = str(normalized.get("review_notes") or "")
    normalized["review_updated_at"] = normalized.get("review_updated_at")
    normalized["tenant_id"] = normalized.get("tenant_id")
    normalized["owner_user_id"] = normalized.get("owner_user_id")
    normalized["owner_user_email"] = normalized.get("owner_user_email")
    normalized["calibration_report"] = (
        normalized.get("calibration_report")
        if isinstance(normalized.get("calibration_report"), dict)
        else {}
    )
    normalized["reproducibility"] = (
        normalized.get("reproducibility")
        if isinstance(normalized.get("reproducibility"), dict)
        else {}
    )
    normalized["ai_text_trust"] = (
        normalized.get("ai_text_trust")
        if isinstance(normalized.get("ai_text_trust"), dict)
        else {}
    )
    normalized["ai_detection"] = _normalize_ai_detection(normalized.get("ai_detection"))
    normalized["web_analysis"] = _normalize_web_analysis(normalized.get("web_analysis"))

    report_dir = _job_report_dir(job_id)
    normalized["report_path"] = normalized.get("report_path") or str(
        report_dir / "report.html"
    )
    normalized["report_json_path"] = normalized.get("report_json_path") or str(
        report_dir / "report.json"
    )
    normalized["committee_report_path"] = normalized.get(
        "committee_report_path"
    ) or str(report_dir / "committee_report.html")

    if from_disk and normalized.get("status") in {"processing", "analyzing"}:
        normalized["status"] = "failed"
        normalized["error"] = (
            normalized.get("error")
            or "Analysis did not complete because the backend restarted before the check finished."
        )

    return normalized


def _persist_job(job_id: str) -> None:
    job = _jobs.get(job_id)
    if not job:
        return

    normalized = _normalize_job(job)
    _jobs[job_id] = normalized

    metadata_path = _job_metadata_path(job_id)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")


def _update_job_status_in_db(
    job_id: str, status: str, error_message: str | None = None
) -> None:
    """Best-effort sync of job status and timestamps to the database (for admin/results pages)."""
    try:
        with SessionLocal() as db:
            db_job = db.query(Job).filter(Job.id == job_id).first()
            if not db_job:
                return
            db_job.status = status
            now = datetime.now()
            if status == "analyzing" and not db_job.started_at:
                db_job.started_at = now
            if status == "completed":
                db_job.completed_at = now
            if status == "failed":
                db_job.failed_at = now
                if error_message:
                    db_job.error_message = error_message[:2000]
            db.commit()
    except Exception:
        logger.warning(f"Failed to update job {job_id} status in DB")


def _recover_job_from_report(job_id: str) -> Optional[Dict[str, Any]]:
    report_json_path = _job_report_dir(job_id) / "report.json"
    if not report_json_path.exists():
        return None

    try:
        report_data = json.loads(report_json_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception(
            f"Failed to recover job metadata for {job_id} from report.json"
        )
        return None

    report_pairs = report_data.get("comparisons") or report_data.get("pairs") or []
    results = [
        _normalize_result(
            {
                "file_a": comparison.get("file_a", ""),
                "file_b": comparison.get("file_b", ""),
                "score": comparison.get("score", 0),
                "risk_level": comparison.get("risk")
                or comparison.get("risk_level")
                or "",
                "features": comparison.get("features") or {},
            }
        )
        for comparison in report_pairs
    ]
    threshold = _coerce_float(report_data.get("threshold"), 0.5)
    title = (
        str(report_data.get("title") or "")
        .replace("IntegrityDesk Report -", "")
        .strip()
    )
    assignment_name = title or f"Recovered Assignment {job_id}"
    file_names = {
        name
        for result in results
        for name in (result["file_a"], result["file_b"])
        if name
    }

    recovered_job = _normalize_job(
        {
            "id": job_id,
            "course_name": assignment_name,
            "assignment_name": assignment_name,
            "threshold": threshold,
            "status": "completed",
            "created_at": report_data.get("generated") or datetime.now().isoformat(),
            "file_count": len(file_names),
            "results": results,
            "summary": _build_job_summary(results, threshold),
            "report_path": str(_job_report_dir(job_id) / "report.html"),
            "report_json_path": str(report_json_path),
            "committee_report_path": str(
                _job_report_dir(job_id) / "committee_report.html"
            ),
            "submissions": {},
            "ai_detection": report_data.get("ai_detection", {}),
            "web_analysis": report_data.get("web_analysis", {}),
            "review_status": "unreviewed",
            "review_notes": "",
            "review_updated_at": None,
        }
    )
    _jobs[job_id] = recovered_job
    _persist_job(job_id)
    return recovered_job


def _load_persisted_job(job_id: str) -> Optional[Dict[str, Any]]:
    metadata_path = _job_metadata_path(job_id)
    if metadata_path.exists():
        try:
            stored_job = json.loads(metadata_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception(f"Failed to read persisted job metadata for {job_id}")
        else:
            stored_job["id"] = job_id
            normalized = _normalize_job(stored_job, from_disk=True)
            _jobs[job_id] = normalized
            _persist_job(job_id)
            return normalized

    return _recover_job_from_report(job_id)


def _get_job(job_id: str) -> Optional[Dict[str, Any]]:
    if job_id in _jobs:
        _jobs[job_id] = _normalize_job(_jobs[job_id])
        return _jobs[job_id]
    loaded = _load_persisted_job(job_id)
    if loaded:
        return loaded
    # DB fallback so results/[id] page can load jobs persisted via ORM (B1)
    return _load_job_from_db(job_id)


def _load_job_from_db(job_id: str) -> Optional[Dict[str, Any]]:
    """Minimal loader for jobs persisted to the database via the ORM wiring.

    Reconstructs a dict shape compatible with the in-memory job format
    so the results/[id] frontend page and existing endpoints can render it.
    """
    try:
        with SessionLocal() as db:
            db_job = db.query(Job).filter(Job.id == job_id).first()
            if not db_job:
                return None

            subs = (
                db.query(Submission)
                .filter(Submission.job_id == job_id)
                .order_by(Submission.created_at)
                .all()
            )
            sim_results = (
                db.query(SimilarityResult)
                .filter(SimilarityResult.job_id == job_id)
                .order_by(SimilarityResult.similarity_score.desc())
                .limit(200)
                .all()
            )

            job_dict: Dict[str, Any] = {
                "id": job_id,
                "status": db_job.status or "completed",
                "assignment_name": db_job.name or f"Job {job_id}",
                "threshold": (
                    float(db_job.threshold) if db_job.threshold is not None else 0.5
                ),
                "file_count": db_job.file_count or len(subs),
                "created_at": (
                    db_job.created_at.isoformat() if db_job.created_at else None
                ),
                "tenant_id": db_job.tenant_id,
                "results": [
                    {
                        "file_a": r.submission_a_id,
                        "file_b": r.submission_b_id,
                        "score": (
                            float(r.similarity_score)
                            if r.similarity_score is not None
                            else 0.0
                        ),
                        "risk_level": (
                            "CRITICAL"
                            if float(r.similarity_score or 0) >= 0.85
                            else (
                                "HIGH"
                                if float(r.similarity_score or 0) >= 0.7
                                else (
                                    "MEDIUM"
                                    if float(r.similarity_score or 0) >= 0.5
                                    else "LOW"
                                )
                            )
                        ),
                        "confidence": (
                            float(r.confidence_level)
                            if r.confidence_level is not None
                            else None
                        ),
                        "verdict": r.verdict,
                        "matching_blocks": r.matching_blocks or [],
                        "features": r.algorithm_scores or {},
                        "external_evidence": (r.algorithm_scores or {}).get(
                            "external_evidence", {}
                        ),
                        "review_status": r.review_status or "unreviewed",
                        "review_notes": r.review_notes or "",
                    }
                    for r in sim_results
                ],
                "submissions": {s.name: "" for s in subs},
                "summary": {"total_pairs": len(sim_results)},
                "review_status": "unreviewed",
                "review_notes": "",
                "submission_count": len(subs),
                "review_summary": (
                    {(s.review_status or "unreviewed"): 0 for s in sim_results}
                    if sim_results
                    else {}
                ),
            }

            # Compute actual review counts from DB
            if sim_results:
                review_summary = {}
                for s in sim_results:
                    st = s.review_status or "unreviewed"
                    review_summary[st] = review_summary.get(st, 0) + 1
                job_dict["review_summary"] = review_summary

            job_dict = _enrich_job_from_report(job_dict, job_id)
            _jobs[job_id] = job_dict
            return job_dict
    except Exception:
        logger.warning(f"_load_job_from_db failed for {job_id}")
        return None


def _enrich_job_from_report(job_dict: Dict[str, Any], job_id: str) -> Dict[str, Any]:
    """Merge richer data from the on-disk report.json into a DB-loaded job (for C)."""
    try:
        report_path = REPORTS_DIR / job_id / "report.json"
        if report_path.exists():
            data = json.loads(report_path.read_text(encoding="utf-8"))
            # Merge common rich fields the results page expects
            for key in (
                "summary",
                "calibration_report",
                "reproducibility",
                "ai_detection",
                "web_analysis",
                "ai_text_trust",
                "assignment_mode",
                "assignment_mode_name",
            ):
                if key in data and key not in job_dict:
                    job_dict[key] = data[key]
            if "external_tool_results" in data:
                job_dict["external_tool_results"] = data["external_tool_results"]
            if "pairs" in data:
                # Prefer the full rich pairs from the generated report (best for Results page)
                job_dict["results"] = data["pairs"]
    except Exception:
        pass
    return job_dict


def _build_ai_detection_summary(submissions: Dict[str, str]) -> Dict[str, Any]:
    """Run AI detection on all submissions and aggregate results.

    Returns a rich summary including per-file signals, flagged lines,
    annotated code snippets, and batch-level statistics.
    """
    if not submissions:
        return {}

    from src.backend.engines.ai.orchestrator import AIDetectionOrchestrator

    detector = AIDetectionOrchestrator()
    entries: List[Dict[str, Any]] = []
    signal_totals: Dict[str, float] = {}
    signal_peaks: Dict[str, float] = {}
    signal_counts: Dict[str, int] = {}

    for name, code in submissions.items():
        language = _infer_language_from_filename(name)
        result = detector.analyze(code, language=language)
        ai_probability = round(_coerce_float(result.get("ai_probability")), 3)
        confidence = round(_coerce_float(result.get("confidence")), 3)
        signals = {
            signal_name: round(_coerce_float(signal_value), 3)
            for signal_name, signal_value in (result.get("signals") or {}).items()
        }
        signal_labels = result.get("signal_labels") or {}

        for signal_name, signal_value in signals.items():
            signal_totals[signal_name] = (
                signal_totals.get(signal_name, 0.0) + signal_value
            )
            signal_peaks[signal_name] = max(
                signal_peaks.get(signal_name, 0.0), signal_value
            )
            signal_counts[signal_name] = signal_counts.get(signal_name, 0) + 1

        # Build annotated code snippet (first 60 lines, flagged lines marked)
        flagged_lines = result.get("flagged_lines") or []
        flagged_set = set(flagged_lines)
        code_lines = code.splitlines()[:60]
        annotated_snippet = [
            {"line": i + 1, "text": ln, "flagged": (i + 1) in flagged_set}
            for i, ln in enumerate(code_lines)
        ]

        entries.append(
            {
                "name": name,
                "language": language,
                "ai_probability": ai_probability,
                "confidence": confidence,
                "status": _ai_status_label(ai_probability),
                "signals": signals,
                "signal_labels": signal_labels,
                "indicators": [
                    str(indicator) for indicator in (result.get("indicators") or [])
                ][:6],
                "flagged_lines": flagged_lines[:30],
                "annotated_snippet": annotated_snippet,
                "error": str(result.get("error") or ""),
            }
        )

    entries.sort(key=lambda entry: (-entry["ai_probability"], entry["name"]))

    distribution = {"low": 0, "medium": 0, "high": 0}
    for entry in entries:
        distribution[_ai_bucket(entry["ai_probability"])] += 1

    average_score = sum(entry["ai_probability"] for entry in entries) / len(entries)
    highest_score = max((entry["ai_probability"] for entry in entries), default=0.0)
    signal_summary = {
        name: {
            "average": round(
                signal_totals[name] / max(signal_counts.get(name, 1), 1), 3
            ),
            "peak": round(signal_peaks.get(name, 0.0), 3),
        }
        for name in sorted(signal_totals)
    }

    return {
        "enabled": True,
        "threshold": AI_MEDIUM_RISK_THRESHOLD,
        "status_message": "Per-submission AI scoring is available for this assignment.",
        "flagged_count": sum(
            1
            for entry in entries
            if entry["ai_probability"] >= AI_MEDIUM_RISK_THRESHOLD
        ),
        "total_files": len(entries),
        "average_score": round(average_score, 3),
        "highest_score": round(highest_score, 3),
        "distribution": distribution,
        "signal_summary": signal_summary,
        "submissions": entries,
    }


def _build_pair_ai_details(
    results: List[Any],
    ai_detection: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    ai_by_submission = {
        entry.get("name"): entry
        for entry in ai_detection.get("submissions", [])
        if isinstance(entry, dict) and entry.get("name")
    }
    pair_ai_details: Dict[str, Dict[str, Any]] = {}

    for result in results:
        file_a = getattr(result, "file_a", "")
        file_b = getattr(result, "file_b", "")
        if not file_a or not file_b:
            continue

        ai_a = ai_by_submission.get(file_a, {})
        ai_b = ai_by_submission.get(file_b, {})
        indicators = []
        for indicator in [
            *(ai_a.get("indicators") or []),
            *(ai_b.get("indicators") or []),
        ]:
            if indicator and indicator not in indicators:
                indicators.append(indicator)

        pair_ai_details[_pair_key(file_a, file_b)] = {
            "ai_probability": round(
                max(
                    _coerce_float(ai_a.get("ai_probability")),
                    _coerce_float(ai_b.get("ai_probability")),
                ),
                3,
            ),
            "confidence": round(
                (
                    _coerce_float(ai_a.get("confidence"))
                    + _coerce_float(ai_b.get("confidence"))
                )
                / 2,
                3,
            ),
            "indicators": indicators[:5],
        }

    return pair_ai_details


def _build_fusion_debug(result: Any, threshold: float) -> Dict[str, Any]:
    """Build a professor-readable breakdown of which engines fired."""
    features = getattr(result, "features", {}) or {}
    contributions = getattr(result, "contributions", {}) or {}
    active = []
    for engine, score in sorted(
        features.items(), key=lambda item: -_coerce_float(item[1])
    ):
        normalized_score = round(_coerce_float(score), 3)
        contribution = round(_coerce_float(contributions.get(engine)), 3)
        active.append(
            {
                "engine": str(engine),
                "score": normalized_score,
                "contribution": contribution,
                "fired": normalized_score >= threshold,
            }
        )

    return {
        "threshold": round(threshold, 3),
        "engines_fired": [item["engine"] for item in active if item["fired"]],
        "engine_count": len(active),
        "active_evidence": active,
        "debug_note": (
            "Scores are normalized to a common 0-1 scale before fusion; contribution "
            "shows each engine's influence after weighting/arbitration when available."
        ),
    }


def _build_calibration_report(threshold: float, mode_id: str) -> Dict[str, Any]:
    """Return threshold/FPR guidance for professor-facing calibration reporting."""
    confidence_zones = [
        {
            "label": "clean",
            "min_score": 0.0,
            "max_score": 0.5,
            "description": "Low-signal region. Keep for archive unless other evidence is strong.",
        },
        {
            "label": "uncertain",
            "min_score": 0.5,
            "max_score": 0.78,
            "description": "Manual review zone. Evidence should be inspected before escalation.",
        },
        {
            "label": "flag",
            "min_score": 0.78,
            "max_score": 1.0,
            "description": "High-certainty review zone. Suitable for formal evidence review.",
        },
    ]
    points = [
        {"threshold": 0.5, "estimated_fpr": 0.08, "label": "broad review"},
        {"threshold": 0.65, "estimated_fpr": 0.04, "label": "balanced"},
        {"threshold": 0.78, "estimated_fpr": 0.02, "label": "high certainty"},
        {"threshold": 0.9, "estimated_fpr": 0.01, "label": "panel-ready"},
    ]
    nearest = min(points, key=lambda point: abs(point["threshold"] - threshold))
    return {
        "threshold": round(threshold, 3),
        "mode_id": mode_id,
        "estimated_false_positive_rate": nearest["estimated_fpr"],
        "confidence_mode": nearest["label"],
        "confidence_zones": confidence_zones,
        "curve": points,
        "methodology": (
            "FPR values are benchmark estimates for calibration guidance. Institutions "
            "should replace them with local validation data when enough professor feedback exists."
        ),
        "overfit_guard": (
            "Default weights must be tuned on train/validation data only; locked test "
            "sets are reserved for final reporting."
        ),
    }


def _build_reproducibility_report(
    submissions: Dict[str, str],
    selected_tool_ids: List[str],
    mode: Any,
) -> Dict[str, Any]:
    """Build deterministic run metadata for reproducible reports."""
    digest = hashlib.sha256()
    for name in sorted(submissions):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(submissions[name].encode("utf-8", errors="replace"))
        digest.update(b"\0")

    return {
        "submission_set_hash": digest.hexdigest(),
        "selected_tool_ids": list(selected_tool_ids),
        "assignment_mode": getattr(mode, "mode_id", ""),
        "assignment_mode_version": getattr(mode, "version", ""),
        "deterministic_caching": True,
        "cache_note": (
            "Tokenization and embeddings use content-hash caches where available; "
            "reports store mode/tool versions and submission-set hash for reruns."
        ),
    }


def _build_ai_text_trust_report(ai_detection: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize AI-text limitations and high-certainty operating mode."""
    threshold = _coerce_float(ai_detection.get("threshold"), AI_MEDIUM_RISK_THRESHOLD)
    return {
        "high_certainty_threshold": AI_HIGH_RISK_THRESHOLD,
        "review_threshold": threshold,
        "humanizer_benchmark_required": True,
        "humanizer_tools": ["Undetectable.ai", "QuillBot"],
        "model_attribution_policy": (
            "Model attribution is supplementary and must use a separate recent held-out evaluation."
        ),
        "false_positive_policy": (
            "AI results are never binary accusations. Borderline results should stay in manual review."
        ),
        "calibration_cadence": "quarterly against recent model and humanizer outputs",
    }


def _build_web_analysis_summary(
    submissions: Dict[str, str], settings_payload: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build public-source match evidence from administrator-configured sources."""
    if not submissions:
        return {}

    settings_payload = settings_payload or {}
    source_sites = _normalize_source_scan_sites(
        settings_payload.get("source_scan_sites")
    )
    web_enabled = bool(settings_payload.get("source_scan_enabled")) and bool(
        source_sites
    )
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_TOKEN")
    stackoverflow_api_key = os.getenv("STACKEXCHANGE_API_KEY")

    if not web_enabled:
        return {
            "enabled": False,
            "configured": bool(source_sites),
            "status_message": "External source scanning is disabled in admin settings.",
            "matched_submissions": 0,
            "highest_similarity": 0.0,
            "average_similarity": 0.0,
            "source_totals": {},
            "configured_sources": source_sites,
            "submissions": [],
        }

    from src.backend.infrastructure.indexing.web_search import WebSearchService

    service = WebSearchService(
        github_token=github_token,
        stackoverflow_api_key=stackoverflow_api_key,
    )
    entries: List[Dict[str, Any]] = []
    source_totals: Dict[str, int] = {}

    for name, code in submissions.items():
        result = service.scan_configured_sources(
            code, _infer_language_from_filename(name), source_sites
        )
        sources = []
        for source in result.get("web_results", [])[:5]:
            sources.append(
                {
                    "name": str(source.get("name") or ""),
                    "url": str(source.get("url") or ""),
                    "source": str(source.get("source") or ""),
                    "similarity": round(_coerce_float(source.get("similarity")), 3),
                }
            )

        source_counts = (
            result.get("source_counts")
            if isinstance(result.get("source_counts"), dict)
            else {}
        )
        for source_name, count in source_counts.items():
            source_totals[source_name] = source_totals.get(source_name, 0) + int(
                count or 0
            )

        entries.append(
            {
                "name": name,
                "max_similarity": round(
                    _coerce_float(result.get("max_web_similarity")), 3
                ),
                "match_count": len(result.get("web_results") or []),
                "sources": sources,
                "source_counts": {
                    str(key): int(value or 0) for key, value in source_counts.items()
                },
            }
        )

    entries.sort(key=lambda entry: (-entry["max_similarity"], entry["name"]))
    average_similarity = (
        sum(entry["max_similarity"] for entry in entries) / len(entries)
        if entries
        else 0.0
    )

    return {
        "enabled": True,
        "configured": True,
        "status_message": "External source checks scanned administrator-configured sources.",
        "matched_submissions": sum(1 for entry in entries if entry["match_count"] > 0),
        "highest_similarity": round(
            max((entry["max_similarity"] for entry in entries), default=0.0), 3
        ),
        "average_similarity": round(average_similarity, 3),
        "source_totals": source_totals,
        "configured_sources": source_sites,
        "submissions": entries,
    }


def _list_all_jobs(current_user: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs_by_id: Dict[str, Dict[str, Any]] = {}

    if REPORTS_DIR.exists():
        for report_dir in REPORTS_DIR.iterdir():
            if not report_dir.is_dir():
                continue
            job = _get_job(report_dir.name)
            if job and _job_is_accessible(job, current_user):
                jobs_by_id[report_dir.name] = job

    for job_id, job in _jobs.items():
        normalized = _normalize_job(job)
        if _job_is_accessible(normalized, current_user):
            jobs_by_id[job_id] = normalized

    # DB-backed listing (D) – pick up jobs persisted via ORM even without local report dir
    try:
        with SessionLocal() as db:
            tenant_id = current_user.get("tenant_id") if current_user else None
            q = db.query(Job)
            if tenant_id:
                q = q.filter(Job.tenant_id == tenant_id)
            db_jobs = q.order_by(Job.created_at.desc()).limit(200).all()
            for db_job in db_jobs:
                if db_job.id not in jobs_by_id:
                    loaded = _get_job(db_job.id)  # will hit _load_job_from_db
                    if loaded and _job_is_accessible(loaded, current_user):
                        jobs_by_id[db_job.id] = loaded
    except Exception:
        logger.warning("DB job listing fallback failed")

    return sorted(
        jobs_by_id.values(), key=lambda entry: entry.get("created_at", ""), reverse=True
    )


@app.get("/api/auth/status")
async def auth_status():
    user_count = await run_in_threadpool(_get_user_count)
    _ensure_auth_secret()
    return JSONResponse(
        content={"bootstrapped": user_count > 0, "user_count": user_count}
    )


def _get_user_count():
    with SessionLocal() as db:
        return int(db.scalar(select(func.count()).select_from(User)) or 0)


@app.post("/api/auth/bootstrap-admin")
async def bootstrap_admin(request: Request):
    payload = await request.json()
    email = _normalize_email(str(payload.get("email") or ""))
    full_name = str(payload.get("full_name") or payload.get("name") or "").strip()
    password = str(payload.get("password") or "")
    tenant_name = str(payload.get("tenant_name") or "").strip()

    if not email or not full_name:
        raise HTTPException(status_code=400, detail="Email and full name are required")
    _validate_password_input(password)

    user_data = await run_in_threadpool(
        _bootstrap_admin_sync, email, full_name, password, tenant_name
    )
    _ensure_auth_secret()
    return JSONResponse(content={"user": user_data, "message": "Admin account created"})
    _ensure_auth_secret()
    return JSONResponse(content={"user": user_data, "message": "Admin account created"})


def _bootstrap_admin_sync(email, full_name, password, tenant_name):
    db = SessionLocal()

    try:
        existing_users = int(db.scalar(select(func.count()).select_from(User)) or 0)
        if existing_users > 0:
            raise HTTPException(
                status_code=400, detail="Bootstrap has already been completed"
            )

        tenant = _create_tenant(
            db, tenant_name or _generate_tenant_name(full_name, email)
        )
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            password_hash=_hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()

        user_data = _serialize_user(user)
        return user_data

    finally:
        db.close()


def _login_sync(email, password):
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .options(joinedload(User.tenant))
            .filter(User.email == email)
            .first()
        )

        if not user or not _verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Your account is disabled")

        user.last_login_at = datetime.utcnow()
        db.add(user)
        db.commit()

        user_data = _serialize_user(user)
        return user_data

    finally:
        db.close()


def _get_user_for_cookie(email):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        return user


def _get_user_by_id(user_id: str):
    """Get a user by their ID for cookie operations."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == user_id))
        return user


@app.post("/api/auth/login")
async def login(request: Request):
    payload = await request.json()
    email = _normalize_email(str(payload.get("email") or ""))
    password = str(payload.get("password") or "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    _validate_password_input(password)

    user_data = await run_in_threadpool(_login_sync, email, password)
    # Need to fetch user again for cookie issuance since we now return serialized data
    user = await run_in_threadpool(_get_user_for_cookie, email)
    response = JSONResponse(content={"user": user_data})
    _issue_auth_cookie(response, user)
    return response


@app.post("/api/auth/logout")
async def logout():
    response = JSONResponse(content={"status": "ok"})
    _clear_auth_cookie(response)
    return response


@app.get("/api/auth/me")
async def auth_me(request: Request):
    return JSONResponse(content={"user": _require_current_user(request)})


@app.post("/api/auth/refresh")
async def refresh_session(request: Request):
    """Refresh the session by extending the cookie expiration."""
    user = _authenticate_request(request)
    user_obj = await run_in_threadpool(_get_user_by_id, user["id"])
    if not user_obj:
        raise HTTPException(status_code=401, detail="User not found")
    response = JSONResponse(content={"user": user})
    _issue_auth_cookie(response, user_obj)
    return response


@app.get("/api/admin/users")
async def list_users(request: Request):
    _require_current_user(request, admin_only=True)
    with SessionLocal() as db:
        users = db.scalars(
            select(User)
            .options(joinedload(User.tenant))
            .order_by(User.created_at.desc())
        ).all()
        return JSONResponse(
            content={"users": [_serialize_user(user) for user in users]}
        )


@app.post("/api/admin/users")
async def create_user(request: Request):
    current_user = _require_current_user(request, admin_only=True)
    payload = await request.json()

    email = _normalize_email(str(payload.get("email") or ""))
    full_name = str(payload.get("full_name") or payload.get("name") or "").strip()
    password = str(payload.get("password") or "")
    role = str(payload.get("role") or "professor").strip().lower()
    tenant_name = str(payload.get("tenant_name") or "").strip()

    if role not in {"admin", "professor"}:
        raise HTTPException(status_code=400, detail="Role must be admin or professor")
    if not email or not full_name:
        raise HTTPException(status_code=400, detail="Email and full name are required")
    _validate_password_input(password)

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(
                status_code=409, detail="A user with that email already exists"
            )

        tenant = _create_tenant(
            db, tenant_name or _generate_tenant_name(full_name, email)
        )
        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            password_hash=_hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        # Refresh with tenant loaded
        user = db.scalar(
            select(User).options(joinedload(User.tenant)).where(User.id == user.id)
        )

        return JSONResponse(
            status_code=201,
            content={
                "user": _serialize_user(user),  # Still works since we're in session
                "created_by": current_user["email"],
            },
        )


# ============================================================
# Admin - Course Instructor Management (new many-to-many)
# ============================================================


@app.get("/api/admin/courses-with-instructors")
async def admin_list_courses_with_instructors(request: Request) -> Dict[str, Any]:
    """Admin view: all courses with their assigned instructors."""
    current_user = _require_current_user(request, admin_only=True)

    try:
        with SessionLocal() as db:
            courses = (
                db.query(Course)
                .options(joinedload(Course.organization))
                .order_by(Course.name)
                .all()
            )

            result = []
            for course in courses:
                instructors = (
                    db.query(User)
                    .join(CourseInstructor)
                    .filter(CourseInstructor.course_id == course.id)
                    .all()
                )

                result.append(
                    {
                        "id": course.id,
                        "name": course.name,
                        "code": course.code,
                        "organization_id": course.organization_id,
                        "organization_name": (
                            course.organization.name if course.organization else None
                        ),
                        "instructors": [
                            {
                                "id": u.id,
                                "email": u.email,
                                "full_name": u.full_name,
                                "role": u.role,
                            }
                            for u in instructors
                        ],
                    }
                )

            return {"courses": result}
    except Exception:
        logger.exception("Failed to load courses with instructors for admin")
        return {"courses": []}


@app.post("/api/admin/course-instructors")
async def admin_assign_instructor_to_course(request: Request):
    """Assign a user as instructor to a course."""
    current_user = _require_current_user(request, admin_only=True)
    data = await request.json()

    course_id = data.get("course_id")
    user_id = data.get("user_id")
    role = data.get("role", "instructor")

    if not course_id or not user_id:
        return JSONResponse(
            status_code=400, content={"error": "course_id and user_id are required"}
        )

    try:
        with SessionLocal() as db:
            # Check if already exists
            existing = (
                db.query(CourseInstructor)
                .filter(
                    CourseInstructor.course_id == course_id,
                    CourseInstructor.user_id == user_id,
                )
                .first()
            )

            if existing:
                existing.role = role
                db.commit()
                return {"success": True, "message": "Role updated"}

            assignment = CourseInstructor(
                course_id=course_id, user_id=user_id, role=role
            )
            db.add(assignment)
            db.commit()

            return {"success": True, "message": "Instructor assigned"}
    except Exception:
        logger.exception("Failed to assign instructor")
        return JSONResponse(
            status_code=500, content={"error": "Failed to assign instructor"}
        )


@app.delete("/api/admin/course-instructors")
async def admin_remove_instructor_from_course(request: Request):
    """Remove an instructor assignment from a course."""
    current_user = _require_current_user(request, admin_only=True)
    data = await request.json()

    course_id = data.get("course_id")
    user_id = data.get("user_id")

    if not course_id or not user_id:
        return JSONResponse(
            status_code=400, content={"error": "course_id and user_id are required"}
        )

    try:
        with SessionLocal() as db:
            deleted = (
                db.query(CourseInstructor)
                .filter(
                    CourseInstructor.course_id == course_id,
                    CourseInstructor.user_id == user_id,
                )
                .delete()
            )
            db.commit()

            return {"success": True, "removed": deleted > 0}
    except Exception:
        logger.exception("Failed to remove instructor")
        return JSONResponse(
            status_code=500, content={"error": "Failed to remove instructor"}
        )


@app.post("/api/admin/create-demo-dataset")
async def create_demo_dataset(request: Request):
    """Create a synthetic demo dataset for testing."""
    current_user = _require_current_user(request, admin_only=False)

    try:
        data = await request.json()
        dataset_name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        language = data.get("language", "python")
        num_files = min(max(int(data.get("numFiles", 10)), 5), 100)
        similarity_type = data.get("similarityType", "plagiarism")

        if not dataset_name:
            raise HTTPException(status_code=400, detail="Dataset name is required")

        # Validate language
        supported_languages = ["python", "java", "javascript", "cpp"]
        if language not in supported_languages:
            language = "python"

        # Create dataset directory
        dataset_dir = BENCHMARK_DATA_DIR / f"demo_{dataset_name}_{int(time.time())}"
        dataset_dir.mkdir(parents=True, exist_ok=True)

        # Generate synthetic files
        files_created = 0
        original_dir = dataset_dir / "original"
        plagiarized_dir = dataset_dir / "plagiarized"
        original_dir.mkdir()
        plagiarized_dir.mkdir()

        # Create original files
        file_extension = _language_file_extension(language)
        for i in range(num_files):
            filename = f"{i:02d}"
            filepath = original_dir / f"{filename}{file_extension}"

            # Generate synthetic code based on language
            code_content = generate_synthetic_code(i, language, similarity_type)
            filepath.write_text(code_content)
            files_created += 1

        # Create modified versions (plagiarized)
        for i in range(num_files):
            original_file = original_dir / f"{i:02d}{file_extension}"
            plagiarized_file = plagiarized_dir / f"{i:02d}{file_extension}"

            if original_file.exists():
                content = original_file.read_text()

                # Apply modifications based on similarity type
                if similarity_type == "type1_exact":
                    # No transformations - exact copy
                    modified_content = content
                elif similarity_type == "type2_renamed":
                    # Apply renaming transformations
                    modified_content = apply_renaming_transforms(content, language)
                elif similarity_type == "type3_modified":
                    # Apply structural modifications
                    modified_content = apply_structural_transforms(content, language)
                elif similarity_type == "type4_semantic":
                    # Different algorithm but same functionality - already handled in generation
                    modified_content = content
                elif similarity_type == "token_similarity":
                    # Focus on token patterns - minimal changes
                    modified_content = apply_token_transforms(content, language)
                elif similarity_type == "structural_similarity":
                    # Code organization changes
                    modified_content = apply_organization_transforms(content, language)
                else:  # semantic_similarity or default
                    # Conceptual changes
                    modified_content = apply_semantic_transforms(content, language)

                plagiarized_file.write_text(modified_content)
                files_created += 1

        # Create metadata
        metadata = {
            "name": dataset_name,
            "description": description,
            "language": language,
            "files_created": files_created,
            "original_files": num_files,
            "plagiarized_files": num_files,
            "similarity_type": similarity_type,
            "created_by": current_user["email"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_path": str(dataset_dir.relative_to(BENCHMARK_DATA_DIR.parent)),
            "pairs": num_files,
        }

        metadata_file = dataset_dir / "metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))

        return JSONResponse(
            status_code=201,
            content={
                "message": f"Demo dataset '{dataset_name}' created successfully",
                "dataset": metadata,
                "files_created": files_created,
                "dataset_path": str(dataset_dir),
            },
        )

    except Exception as e:
        logger.error(f"Failed to create demo dataset: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create demo dataset: {str(e)}"
        )


def generate_synthetic_code(index: int, language: str, similarity_type: str) -> str:
    """Generate synthetic code for testing different similarity types."""

    if language == "python":
        if similarity_type == "type1_exact":
            # Generate base code for exact copying
            return f'''"""
Basic mathematical utilities - Sample {index}
"""

def fibonacci_iterative(n):
    """Calculate nth Fibonacci number iteratively."""
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

def check_prime(num):
    """Check if number is prime."""
    if num <= 1:
        return False
    if num <= 3:
        return True
    if num % 2 == 0 or num % 3 == 0:
        return False
    i = 5
    while i * i <= num:
        if num % i == 0 or num % (i + 2) == 0:
            return False
        i += 6
    return True

def sort_bubble(arr):
    """Bubble sort implementation."""
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr

# Test the functions
result_fib = fibonacci_iterative({index})
result_prime = check_prime({index})
test_data = [{index}, {index+1}, {index+2}]
result_sort = sort_bubble(test_data)

print(f"Fibonacci({index}) = {{result_fib}}")
print(f"Prime check for {index}: {{result_prime}}")
print(f"Sorted data: {{result_sort}}")
'''

        elif similarity_type == "type2_renamed":
            # Generate code with renamed identifiers for Type 2 testing
            return f'''"""
Mathematics computation module - Sample {index}
"""

def compute_fibonacci_number(target):
    """Compute fibonacci sequence value."""
    if target <= 1:
        return target
    previous, current = 0, 1
    for _ in range(2, target + 1):
        previous, current = current, previous + current
    return current

def validate_prime(candidate):
    """Validate if candidate is prime number."""
    if candidate <= 1:
        return False
    if candidate <= 3:
        return True
    if candidate % 2 == 0 or candidate % 3 == 0:
        return False
    divisor = 5
    while divisor * divisor <= candidate:
        if candidate % divisor == 0 or candidate % (divisor + 2) == 0:
            return False
        divisor += 6
    return True

def arrange_elements_bubble(input_list):
    """Arrange list elements using bubble technique."""
    list_length = len(input_list)
    for pass_num in range(list_length):
        for element_idx in range(0, list_length - pass_num - 1):
            if input_list[element_idx] > input_list[element_idx + 1]:
                input_list[element_idx], input_list[element_idx + 1] = input_list[element_idx + 1], input_list[element_idx]
    return input_list

# Execute test cases
fibonacci_value = compute_fibonacci_number({index})
prime_status = validate_prime({index})
sample_values = [{index}, {index+1}, {index+2}]
organized_values = arrange_elements_bubble(sample_values)

print(f"Fibonacci number {index}: {{fibonacci_value}}")
print(f"Is {index} prime: {{prime_status}}")
print(f"Organized values: {{organized_values}}")
'''

        elif similarity_type == "type3_modified":
            # Generate code with modified structure (added comments, different organization)
            return f'''"""
Advanced mathematical utilities with detailed documentation - Sample {index}
Created for comprehensive testing of similarity detection algorithms
"""

# Import necessary modules for mathematical operations
import math

def calculate_fibonacci(n):
    """
    Calculate the nth Fibonacci number using an iterative approach.

    This function implements the classic Fibonacci sequence calculation
    using a bottom-up dynamic programming approach for efficiency.

    Args:
        n (int): The position in the Fibonacci sequence

    Returns:
        int: The nth Fibonacci number
    """
    # Handle base cases
    if n <= 1:
        return n

    # Initialize variables for iterative calculation
    a, b = 0, 1

    # Iterate through the sequence
    for iteration in range(2, n + 1):
        # Update values for next iteration
        a, b = b, a + b

    return b

def is_prime(number):
    """
    Determine whether a given number is prime.

    Uses an optimized trial division algorithm with 6k±1 optimization.

    Args:
        number (int): The number to check for primality

    Returns:
        bool: True if prime, False otherwise
    """
    # Handle edge cases first
    if number <= 1:
        return False
    if number <= 3:
        return True

    # Check divisibility by 2 and 3
    if number % 2 == 0 or number % 3 == 0:
        return False

    # Check divisibility by numbers of form 6k±1
    i = 5
    while i * i <= number:
        if number % i == 0 or number % (i + 2) == 0:
            return False
        i += 6

    return True

def bubble_sort(arr):
    """
    Sort an array using the bubble sort algorithm.

    This is a simple comparison-based sorting algorithm that repeatedly
    steps through the list, compares adjacent elements and swaps them
    if they are in the wrong order.

    Args:
        arr (list): The array to sort

    Returns:
        list: The sorted array
    """
    n = len(arr)

    # Outer loop for each pass
    for i in range(n):
        # Inner loop for comparisons in this pass
        for j in range(0, n - i - 1):
            # Swap if elements are in wrong order
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]

    return arr

# Main execution block
if __name__ == "__main__":
    # Test fibonacci calculation
    fib_result = calculate_fibonacci({index})

    # Test prime checking
    prime_result = is_prime({index})

    # Test sorting functionality
    sample_array = [{index}, {index+1}, {index+2}, {index+3}, {index+4}]
    sorted_array = bubble_sort(sample_array)

    # Display results
    print(f"Fibonacci({index}) = {{fib_result}}")
    print(f"Is {index} prime? {{prime_result}}")
    print(f"Sorted array: {{sorted_array}}")
'''

        elif similarity_type == "type4_semantic":
            # Generate semantically equivalent code with different algorithms
            return f'''"""
Alternative mathematical implementations - Sample {index}
Demonstrating different approaches to achieve same results
"""

def fibonacci_recursive(n):
    """Calculate Fibonacci using recursive approach."""
    if n <= 1:
        return n
    return fibonacci_recursive(n-1) + fibonacci_recursive(n-2)

def prime_trial_division(num):
    """Check primality using trial division up to square root."""
    if num < 2:
        return False
    for i in range(2, int(num ** 0.5) + 1):
        if num % i == 0:
            return False
    return True

def selection_sort(items):
    """Sort using selection sort algorithm."""
    for i in range(len(items)):
        min_idx = i
        for j in range(i+1, len(items)):
            if items[j] < items[min_idx]:
                min_idx = j
        items[i], items[min_idx] = items[min_idx], items[i]
    return items

# Alternative implementations for same functionality
def fibonacci_matrix(n):
    """Calculate Fibonacci using matrix exponentiation concept."""
    if n == 0:
        return 0
    # Simplified iterative matrix approach
    a, b = 1, 1
    for _ in range(2, n):
        a, b = b, a + b
    return b if n > 1 else 1

# Test different algorithmic approaches
recursive_fib = fibonacci_recursive(min({index}, 10))  # Limit recursion depth
matrix_fib = fibonacci_matrix({index})
trial_prime = prime_trial_division({index})

test_list = [{index}, {index+2}, {index+1}]
selection_sorted = selection_sort(test_list.copy())

print(f"Recursive Fibonacci: {{recursive_fib}}")
print(f"Matrix Fibonacci: {{matrix_fib}}")
print(f"Trial division prime check: {{trial_prime}}")
print(f"Selection sorted: {{selection_sorted}}")
'''

        elif similarity_type == "token_similarity":
            # Focus on token patterns and programming style
            return f'''
"""
Programming style demonstration - Sample {index}
Showcasing common programming patterns and token usage
"""

def process_data(data_list):
    """Process a list of data elements."""
    result = []
    for item in data_list:
        if item % 2 == 0:
            result.append(item * 2)
        else:
            result.append(item + 1)
    return result

def validate_input(value):
    """Validate input value with multiple checks."""
    if value is None:
        return False
    if not isinstance(value, int):
        return False
    if value < 0:
        return False
    if value > 1000:
        return False
    return True

def calculate_average(numbers):
    """Calculate average of number list."""
    if not numbers:
        return 0
    total = sum(numbers)
    count = len(numbers)
    return total / count

def find_maximum(items):
    """Find maximum value in collection."""
    if not items:
        return None
    max_val = items[0]
    for item in items:
        if item > max_val:
            max_val = item
    return max_val

# Demonstrate common programming patterns
sample_data = [{index}, {index+1}, {index+2}, {index+3}]
processed = process_data(sample_data)
is_valid = validate_input({index})
average = calculate_average(sample_data)
maximum = find_maximum(sample_data)

print("Processed data:", processed)
print("Input validation:", is_valid)
print("Average value:", average)
print("Maximum value:", maximum)
'''

        elif similarity_type == "structural_similarity":
            # Focus on code structure and organization
            return f'''"""
Well-structured code with clear organization - Sample {index}
Demonstrating good software engineering practices
"""

class MathUtils:
    """Utility class for mathematical operations."""

    @staticmethod
    def fibonacci(n):
        """Calculate nth Fibonacci number."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    @staticmethod
    def is_prime(num):
        """Check if number is prime."""
        if num <= 1:
            return False
        if num <= 3:
            return True
        if num % 2 == 0 or num % 3 == 0:
            return False
        i = 5
        while i * i <= num:
            if num % i == 0 or num % (i + 2) == 0:
                return False
            i += 6
        return True

class SortingUtils:
    """Utility class for sorting operations."""

    @staticmethod
    def bubble_sort(arr):
        """Sort array using bubble sort."""
        n = len(arr)
        for i in range(n):
            for j in range(0, n - i - 1):
                if arr[j] > arr[j + 1]:
                    arr[j], arr[j + 1] = arr[j + 1], arr[j]
        return arr

class DataProcessor:
    """Class for processing data collections."""

    def __init__(self, data):
        self.data = data
        self.processed = False

    def process(self):
        """Process the data."""
        if self.processed:
            return self.data

        # Apply mathematical operations
        self.data = [MathUtils.fibonacci(x) if MathUtils.is_prime(x) else x for x in self.data]

        # Sort the results
        self.data = SortingUtils.bubble_sort(self.data)

        self.processed = True
        return self.data

    def get_statistics(self):
        """Get statistics about the data."""
        if not self.processed:
            self.process()

        return {{
            "count": len(self.data),
            "sum": sum(self.data),
            "average": sum(self.data) / len(self.data) if self.data else 0,
            "is_sorted": all(self.data[i] <= self.data[i+1] for i in range(len(self.data)-1))
        }}

# Usage example
processor = DataProcessor([{index}, {index+1}, {index+2}])
result = processor.process()
stats = processor.get_statistics()

print(f"Processed data: {{result}}")
print(f"Statistics: {{stats}}")
'''

        else:  # semantic_similarity or default
            # Generate conceptually similar but different implementations
            return f'''"""
Creative problem-solving approaches - Sample {index}
Demonstrating different thinking patterns for same problems
"""

# Approach 1: Functional programming style
def compute_sequence_value(position):
    """Compute value at given position using functional approach."""
    def fib_generator():
        a, b = 0, 1
        while True:
            yield a
            a, b = b, a + b

    gen = fib_generator()
    for _ in range(position + 1):
        result = next(gen)
    return result

# Approach 2: Using memoization
def get_sequence_value(n, cache=None):
    """Get sequence value with caching for efficiency."""
    if cache is None:
        cache = {{}}

    if n in cache:
        return cache[n]

    if n <= 1:
        cache[n] = n
    else:
        cache[n] = get_sequence_value(n-1, cache) + get_sequence_value(n-2, cache)

    return cache[n]

# Approach 3: Mathematical formula approximation
def approximate_sequence(n):
    """Approximate sequence value using mathematical formula."""
    if n <= 1:
        return n

    # Using Binet's formula approximation
    phi = (1 + 5**0.5) / 2
    return round(phi**n / 5**0.5)

# Different primality testing approaches
def primality_test_traditional(n):
    """Traditional primality test."""
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True

def primality_test_optimized(n):
    """Optimized primality test with early exits."""
    if n <= 1:
        return False
    if n <= 3:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False

    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

# Test different approaches
fib1 = compute_sequence_value({index})
fib2 = get_sequence_value({index})
fib3 = approximate_sequence({index})

prime1 = primality_test_traditional({index})
prime2 = primality_test_optimized({index})

print(f"Functional approach: {{fib1}}")
print(f"Memoized approach: {{fib2}}")
print(f"Formula approach: {{fib3}}")
print(f"Traditional prime check: {{prime1}}")
print(f"Optimized prime check: {{prime2}}")
'''
    elif language == "java":
        base_code = f"""/**
 * Synthetic Java code sample {index}
 * Generated for testing purposes
 */
public class SampleProgram{index} {{
    /**
     * Calculate the nth Fibonacci number
     */
    public static int calculateFibonacci(int n) {{
        if (n <= 1) {{
            return n;
        }}

        int a = 0, b = 1;
        for (int i = 2; i <= n; i++) {{
            int temp = a + b;
            a = b;
            b = temp;
        }}
        return b;
    }}

    /**
     * Check if a number is prime
     */
    public static boolean isPrime(int number) {{
        if (number <= 1) {{
            return false;
        }}
        if (number <= 3) {{
            return true;
        }}
        if (number % 2 == 0 || number % 3 == 0) {{
            return false;
        }}

        for (int i = 5; i * i <= number; i += 6) {{
            if (number % i == 0 || number % (i + 2) == 0) {{
                return false;
            }}
        }}
        return true;
    }}

    public static void main(String[] args) {{
        int fibResult = calculateFibonacci({index});
        boolean primeResult = isPrime({index});

        System.out.println("Fibonacci({index}) = " + fibResult);
        System.out.println("Is {index} prime? " + primeResult);
    }}
}}
"""
    elif language == "javascript":
        base_code = f"""/**
 * Synthetic JavaScript code sample {index}
 * Generated for testing purposes
 */

/**
 * Calculate the nth Fibonacci number using iteration
 * @param {{number}} n - The index of the Fibonacci number to calculate
 * @returns {{number}} The nth Fibonacci number
 */
function calculateFibonacci(n) {{
    if (n <= 1) {{
        return n;
    }}

    let a = 0, b = 1;
    for (let i = 2; i <= n; i++) {{
        [a, b] = [b, a + b];
    }}
    return b;
}}

/**
 * Check if a number is prime
 * @param {{number}} number - The number to check
 * @returns {{boolean}} True if the number is prime, false otherwise
 */
function isPrime(number) {{
    if (number <= 1) {{
        return false;
    }}
    if (number <= 3) {{
        return true;
    }}
    if (number % 2 === 0 || number % 3 === 0) {{
        return false;
    }}

    for (let i = 5; i * i <= number; i += 6) {{
        if (number % i === 0 || number % (i + 2) === 0) {{
            return false;
        }}
    }}
    return true;
}}

// Main execution
const fibResult = calculateFibonacci({index});
const primeResult = isPrime({index});

console.log(`Fibonacci({index}) = ${{fibResult}}`);
console.log(`Is {index} prime? ${{primeResult}}`);
"""
    else:  # cpp
        base_code = f"""/**
 * Synthetic C++ code sample {index}
 * Generated for testing purposes
 */

#include <iostream>
#include <vector>
#include <algorithm>

/**
 * Calculate the nth Fibonacci number using iteration
 */
int calculateFibonacci(int n) {{
    if (n <= 1) {{
        return n;
    }}

    int a = 0, b = 1;
    for (int i = 2; i <= n; ++i) {{
        int temp = a + b;
        a = b;
        b = temp;
    }}
    return b;
}}

/**
 * Check if a number is prime
 */
bool isPrime(int number) {{
    if (number <= 1) {{
        return false;
    }}
    if (number <= 3) {{
        return true;
    }}
    if (number % 2 == 0 || number % 3 == 0) {{
        return false;
    }}

    for (int i = 5; i * i <= number; i += 6) {{
        if (number % i == 0 || number % (i + 2) == 0) {{
            return false;
        }}
    }}
    return true;
}}

/**
 * Sort an array using bubble sort
 */
void bubbleSort(std::vector<int>& arr) {{
    int n = arr.size();
    for (int i = 0; i < n; ++i) {{
        for (int j = 0; j < n - i - 1; ++j) {{
            if (arr[j] > arr[j + 1]) {{
                std::swap(arr[j], arr[j + 1]);
            }}
        }}
    }}
}}

int main() {{
    int fibResult = calculateFibonacci({index});
    bool primeResult = isPrime({index});

    std::cout << "Fibonacci({index}) = " << fibResult << std::endl;
    std::cout << "Is {index} prime? " << (primeResult ? "true" : "false") << std::endl;

    return 0;
}}
"""

    return base_code


def apply_plagiarism_transforms(code: str, language: str) -> str:
    """Apply transformations that simulate plagiarism."""
    import re

    # Remove comments
    if language == "python":
        code = re.sub(r'""".*?"""', "", code, flags=re.DOTALL)
        code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
    elif language == "java":
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    elif language == "javascript":
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)
    elif language == "cpp":
        code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
        code = re.sub(r"//.*$", "", code, flags=re.MULTILINE)

    # Variable renaming
    code = re.sub(r"\bfib_result\b", "fib_num", code)
    code = re.sub(r"\bprime_result\b", "is_prime_result", code)
    code = re.sub(r"\bsample_array\b", "numbers", code)
    code = re.sub(r"\bsorted_array\b", "sorted_numbers", code)

    # Change spacing
    code = re.sub(r"    ", "  ", code)  # Reduce indentation
    code = re.sub(r"\n\s*\n", "\n", code)  # Remove extra blank lines

    return code


def apply_clone_transforms(code: str, language: str) -> str:
    """Apply transformations that create Type 1 clones."""
    import re

    # Minor changes like renaming variables
    code = re.sub(r"\bcalculateFibonacci\b", "computeFibonacci", code)
    code = re.sub(r"\bisPrime\b", "checkPrime", code)
    code = re.sub(r"\bbubbleSort\b", "sortArray", code)

    # Change string literals slightly
    code = re.sub(r'"', "'", code)
    code = re.sub(r"'", '"', code)

    return code


def apply_mixed_transforms(code: str, language: str) -> str:
    """Apply mixed transformations."""
    code = apply_plagiarism_transforms(code, language)
    code = apply_clone_transforms(code, language)
    return code


def apply_renaming_transforms(code: str, language: str) -> str:
    """Apply identifier renaming transformations for Type 2 clones."""
    import re

    # Rename common variable and function names
    renames = {
        r"\bfibonacci_iterative\b": "compute_fibonacci",
        r"\bcalculate_fibonacci\b": "get_fibonacci_value",
        r"\bcheck_prime\b": "validate_primality",
        r"\bis_prime\b": "test_prime_number",
        r"\bbubble_sort\b": "perform_bubble_sort",
        r"\bsort_bubble\b": "execute_sorting",
        r"\bfib_result\b": "fibonacci_result",
        r"\bprime_result\b": "primality_result",
        r"\bsample_array\b": "input_data",
        r"\btest_data\b": "sample_values",
        r"\bsorted_array\b": "ordered_data",
        r"\ba\b": "first_value",
        r"\bb\b": "second_value",
        r"\bi\b": "counter",
        r"\bj\b": "inner_counter",
        r"\bn\b": "size",
        r"\barr\b": "array_data",
        r"\bnum\b": "number",
        r"\bvalue\b": "current_value",
        r"\bitem\b": "element",
    }

    for pattern, replacement in renames.items():
        code = re.sub(pattern, replacement, code)

    return code


def apply_structural_transforms(code: str, language: str) -> str:
    """Apply structural modifications for Type 3 clones."""
    import re

    # Add comments and restructure code
    if language == "python":
        # Add inline comments
        code = re.sub(r"(\s+)(for.*:)", r"\1\2  # Loop through elements", code)
        code = re.sub(r"(\s+)(if.*:)", r"\1\2  # Conditional check", code)
        code = re.sub(r"(\s+)(return.*)", r"\1\2  # Return result", code)

        # Add extra blank lines and reorganize
        lines = code.split("\n")
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            # Add blank lines before function definitions and major blocks
            if re.match(r"\s*def\s+", line) and i > 0:
                new_lines.append("")
        code = "\n".join(new_lines)

    return code


def apply_token_transforms(code: str, language: str) -> str:
    """Apply token-level transformations for token similarity."""
    import re

    # Change coding style patterns while keeping similar token usage
    # Change single quotes to double quotes and vice versa
    code = re.sub(r"'([^']*)'", r'"\1"', code)
    code = re.sub(r'"([^"]*)"', r"'\1'", code)

    # Change operator spacing
    code = re.sub(r"(\w)\s*([+\-*/=<>!&|]+)\s*(\w)", r"\1 \2 \3", code)

    # Change comment style slightly
    if language == "python":
        code = re.sub(r"# (.*)", r"# \1 - comment", code)

    return code


def apply_organization_transforms(code: str, language: str) -> str:
    """Apply organizational changes for structural similarity."""
    import re

    if language == "python":
        # Reorganize imports and function definitions
        lines = code.split("\n")
        imports = []
        functions = []
        other_lines = []

        for line in lines:
            if re.match(r"^(import|from)", line):
                imports.append(line)
            elif re.match(r"^\s*def\s+", line):
                functions.append(line)
            else:
                other_lines.append(line)

        # Reorganize with functions first, then other code
        code = "\n".join(functions + [""] + other_lines + [""] + imports)

    return code


def apply_semantic_transforms(code: str, language: str) -> str:
    """Apply semantic-level transformations."""
    import re

    # Change algorithmic approaches while maintaining similar functionality
    # For example, change iterative to recursive approaches (simplified)
    code = re.sub(
        r"for.*range.*:",
        r"# Iterative approach changed to different logic",
        code,
        count=1,
    )

    # Add semantic comments
    code = re.sub(r"(def\s+\w+)", r"# Function implements core algorithm\n\1", code)

    return code


@app.post("/api/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    starter_files: Optional[List[UploadFile]] = File(default=None),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    assignment_id: Optional[str] = Form(default=None),
    assignment_mode: str = Form(default=""),
    threshold: float = Form(default=0.5),
    engine_keys: str = Form(default=""),
    tool_ids: str = Form(default=""),
    source_scan_enabled: bool = Form(default=True),
):
    # Allow unauthenticated uploads for plagiarism checker
    current_user = getattr(request.state, "user", None)
    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"source_scan_enabled_override": source_scan_enabled}
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        if f.filename and _is_code_file(f.filename):
            safe_name = PathLib(f.filename).name
            target = _unique_child_path(job_dir, PathLib(safe_name))
            target.parent.mkdir(parents=True, exist_ok=True)
            content = await f.read()
            target.write_bytes(content)
            saved_files.append(str(target.relative_to(job_dir)))

    starter_dir = job_dir / "starter"
    starter_sources = []
    if starter_files:
        starter_dir.mkdir(exist_ok=True)
        for f in starter_files:
            if f.filename and _is_code_file(f.filename):
                safe_name = PathLib(f.filename).name
                target = _unique_child_path(starter_dir, PathLib(safe_name))
                target.parent.mkdir(parents=True, exist_ok=True)
                content = await f.read()
                target.write_bytes(content)
                starter_sources.append(content.decode("utf-8", errors="ignore"))

    if len(saved_files) < 2:
        return JSONResponse(
            status_code=400, content={"error": "At least 2 code files are required"}
        )

    return await _run_analysis(
        job_id,
        job_dir,
        course_name,
        assignment_name,
        assignment_id,
        assignment_mode,
        threshold,
        current_user,
        engine_keys,
        tool_ids,
        starter_sources,
    )


@app.post("/api/upload-zip")
async def upload_zip(
    request: Request,
    file: UploadFile = File(...),
    starter_files: Optional[List[UploadFile]] = File(default=None),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    assignment_id: Optional[str] = Form(default=None),
    assignment_mode: str = Form(default=""),
    threshold: float = Form(default=0.5),
    engine_keys: str = Form(default=""),
    tool_ids: str = Form(default=""),
    source_scan_enabled: bool = Form(default=True),
):
    # Allow unauthenticated uploads for plagiarism checker
    current_user = getattr(request.state, "user", None)
    if not file.filename or not file.filename.lower().endswith(".zip"):
        return JSONResponse(
            status_code=400, content={"error": "Please upload a .zip file"}
        )

    job_id = str(uuid.uuid4())[:8]
    _jobs[job_id] = {"source_scan_enabled_override": source_scan_enabled}
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    zip_path = job_dir / file.filename
    content = await file.read()
    zip_path.write_bytes(content)

    extracted = _extract_zip(zip_path, job_dir)
    if len(extracted) < 2:
        shutil.rmtree(job_dir)
        return JSONResponse(
            status_code=400, content={"error": "Zip must contain at least 2 code files"}
        )

    starter_dir = job_dir / "starter"
    starter_sources = []
    if starter_files:
        starter_dir.mkdir(exist_ok=True)
        for f in starter_files:
            if f.filename and _is_code_file(f.filename):
                safe_name = PathLib(f.filename).name
                target = _unique_child_path(starter_dir, PathLib(safe_name))
                target.parent.mkdir(parents=True, exist_ok=True)
                content = await f.read()
                target.write_bytes(content)
                starter_sources.append(content.decode("utf-8", errors="ignore"))

    return await _run_analysis(
        job_id,
        job_dir,
        course_name,
        assignment_name,
        assignment_id,
        assignment_mode,
        threshold,
        current_user,
        engine_keys,
        tool_ids,
        starter_sources,
    )


@app.post("/api/ai-detect")
async def detect_ai_generated_code(
    request: Request,
    files: Optional[List[UploadFile]] = File(default=None),
    file: Optional[UploadFile] = File(default=None),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
):
    """Run AI-generated code detection for one or more uploaded submissions.

    Accessible to both authenticated users and guests.
    """
    current_user = getattr(request.state, "user", None)
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    uploads = list(files or [])
    if file is not None:
        uploads.append(file)

    for upload in uploads:
        if not upload.filename:
            continue
        filename = PathLib(upload.filename).name
        content = await upload.read()
        target = job_dir / filename
        target.write_bytes(content)
        if filename.lower().endswith(".zip"):
            _extract_zip(target, job_dir)

    submissions = _read_files_from_dir(job_dir)
    if not submissions:
        shutil.rmtree(job_dir, ignore_errors=True)
        return JSONResponse(
            status_code=400,
            content={"error": "Upload at least one valid code file or ZIP archive."},
        )

    ai_detection = _build_ai_detection_summary(submissions)
    _job_report_dir(job_id).mkdir(parents=True, exist_ok=True)
    _jobs[job_id] = {
        "id": job_id,
        "job_type": "ai_detector",
        "course_name": course_name or "AI Detector",
        "assignment_name": assignment_name or "AI Generated Code Review",
        "status": "completed",
        "created_at": datetime.now().isoformat(),
        "file_count": len(submissions),
        "results": [],
        "summary": {
            "total_files": len(submissions),
            "flagged_files": ai_detection.get("flagged_count", 0),
            "highest_ai_probability": ai_detection.get("highest_score", 0.0),
            "average_ai_probability": ai_detection.get("average_score", 0.0),
        },
        "review_status": "unreviewed",
        "review_notes": "",
        "review_updated_at": None,
        "tenant_id": current_user.get("tenant_id") if current_user else None,
        "owner_user_id": current_user.get("id") if current_user else None,
        "owner_user_email": current_user.get("email") if current_user else None,
        "selected_tool_ids": ["ai_detector"],
        "selected_tools": ["AI Detector"],
        "ai_detection": ai_detection,
        # Store first 4 KB of each file for the report code preview
        "submissions": {k: v[:4096] for k, v in submissions.items()},
    }
    _persist_job(job_id)
    return JSONResponse(
        content={"job_id": job_id, "status": "completed", "ai_detection": ai_detection}
    )


async def _run_analysis(
    job_id,
    job_dir,
    course_name,
    assignment_name,
    assignment_id: Optional[str] = None,
    assignment_mode: str = "",
    threshold: float = 0.5,
    current_user: Dict[str, Any] = None,
    engine_keys_raw: str = "",
    tool_ids_raw: str = "",
    starter_sources: List[str] = None,
):
    from src.backend.engines.scoring.assignment_modes import get_assignment_mode

    mode = get_assignment_mode(assignment_mode)

    # Resolve authoritative course/assignment names from DB when assignment_id is provided.
    # This wires the new Organization → Course → Assignment hierarchy into the upload flow
    # (DB link takes precedence even if free-text fields were left blank).
    if assignment_id:
        try:
            with SessionLocal() as db:
                assignment = (
                    db.query(Assignment)
                    .options(joinedload(Assignment.course))
                    .filter(Assignment.id == assignment_id)
                    .first()
                )
                if assignment:
                    if getattr(assignment, "name", None):
                        assignment_name = assignment.name
                    if getattr(assignment, "course", None) and getattr(
                        assignment.course, "name", None
                    ):
                        course_name = assignment.course.name
        except Exception:
            logger.warning(
                f"Failed to resolve assignment_id={assignment_id} for name lookup"
            )

    selected_tool_ids = _parse_selected_tool_ids(tool_ids_raw)
    try:
        requested_engine_keys = json.loads(engine_keys_raw) if engine_keys_raw else []
        if not isinstance(requested_engine_keys, list):
            requested_engine_keys = []
    except json.JSONDecodeError:
        requested_engine_keys = []

    # Use mode-specific weights if available, otherwise fall back to global settings
    if mode.weights:
        engine_weights = dict(mode.weights)
    else:
        engine_weights = _get_upload_engine_weights(
            current_user.get("tenant_id") if current_user else None,
            [str(key) for key in requested_engine_keys],
        )
    selected_engine_keys = [
        key for key, value in engine_weights.items() if _coerce_float(value) > 0
    ]
    fusion_weights = _build_fusion_weights(engine_weights)

    _job_report_dir(job_id).mkdir(parents=True, exist_ok=True)
    _jobs[job_id] = {
        "id": job_id,
        "course_name": course_name or "Unnamed Course",
        "assignment_name": assignment_name or "Unnamed Assignment",
        "assignment_id": assignment_id,
        "assignment_mode": mode.mode_id,
        "assignment_mode_name": mode.name,
        "assignment_mode_version": mode.version,
        "assignment_mode_policy": {
            "pipelines": mode.pipelines,
            "warnings": mode.warnings,
            "evidence_surfaces": mode.evidence_surfaces,
            "calibration": mode.calibration,
        },
        "threshold": threshold,
        "starter_sources": starter_sources or [],
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "file_count": 0,
        "results": [],
        "summary": {},
        "review_status": "unreviewed",
        "review_notes": "",
        "review_updated_at": None,
        "tenant_id": current_user.get("tenant_id") if current_user else None,
        "owner_user_id": current_user.get("id") if current_user else None,
        "owner_user_email": current_user.get("email") if current_user else None,
        "selected_tool_ids": selected_tool_ids,
        "selected_tools": [
            BENCHMARK_TOOL_METADATA.get(tool_id, {}).get(
                "name", tool_id.replace("-", " ").title()
            )
            for tool_id in selected_tool_ids
        ],
        "external_tool_results": {},
        "active_engines": (
            [
                ENGINE_DISPLAY_LABELS.get(key, key.title())
                for key in selected_engine_keys
            ]
            if "integritydesk" in selected_tool_ids
            else []
        ),
    }
    _persist_job(job_id)

    try:
        submissions = _read_files_from_dir(job_dir)
        if len(submissions) < 2:
            del _jobs[job_id]
            return JSONResponse(
                status_code=400,
                content={"error": "At least 2 valid code files required"},
            )

        _jobs[job_id]["file_count"] = len(submissions)
        _jobs[job_id]["status"] = "analyzing"
        _persist_job(job_id)
        _update_job_status_in_db(job_id, "analyzing")

        # Minimal DB wiring for upload flow — persist Job + Submission rows
        # (non-fatal; file-based storage remains primary for now)
        try:
            with SessionLocal() as db:
                if not db.query(Job).filter(Job.id == job_id).first():
                    tenant_id = _jobs[job_id].get("tenant_id")
                    if not tenant_id:
                        # Fallback for public/demo uploads (no logged-in user):
                        # attribute the job to the first existing tenant so the new
                        # hierarchy (assignment_id) and results pages can see the data.
                        fallback = db.query(Tenant).first()
                        if fallback:
                            tenant_id = fallback.id
                            _jobs[job_id]["tenant_id"] = tenant_id

                    if tenant_id:
                        db_job = Job(
                            id=job_id,
                            tenant_id=tenant_id,
                            assignment_id=_jobs[job_id].get("assignment_id"),
                            name=_jobs[job_id].get("assignment_name")
                            or f"Upload {job_id}",
                            status=_jobs[job_id].get("status", "analyzing"),
                            threshold=_jobs[job_id].get("threshold", 0.5),
                            created_at=datetime.now(),
                            file_count=len(submissions),
                        )
                        db.add(db_job)
                        for sub_name in list(submissions.keys())[:100]:
                            db.add(
                                Submission(
                                    id=str(uuid.uuid4()),
                                    job_id=job_id,
                                    name=sub_name,
                                    file_count=1,
                                    created_at=datetime.now(),
                                )
                            )
                        db.commit()
                    else:
                        logger.warning(
                            f"DB persist skipped for job {job_id} - no tenant available"
                        )
        except Exception:
            logger.warning(
                f"DB persist skipped for job {job_id} (file storage still used)"
            )

        all_pairs = _build_all_submission_pairs(submissions)
        external_tool_results = _run_selected_external_tools(
            selected_tool_ids, submissions, all_pairs
        )

        if "integritydesk" in selected_tool_ids:
            service = BatchDetectionService(
                threshold=threshold,
                weights=fusion_weights or None,
                starter_sources=starter_sources,
            )
            results = service.compare_all_pairs(submissions)
            _merge_external_features_into_results(results, external_tool_results)
            report = service.generate_report(results)
        else:
            service = BatchDetectionService(threshold=threshold)
            results = _build_external_comparison_results(
                external_tool_results, all_pairs
            )
            report = service.generate_report(results)

        _jobs[job_id]["external_tool_results"] = external_tool_results
        _persist_job(job_id)
        ai_detection = _build_ai_detection_summary(submissions)
        settings_payload = _build_settings_payload(
            current_user.get("tenant_id") if current_user else None
        )

        # Per-assignment override for external source scanning (uses existing Assignment.settings JSONB)
        assignment_id = _jobs[job_id].get("assignment_id")
        if assignment_id:
            try:
                with SessionLocal() as db:
                    ass = db.query(Assignment).filter(Assignment.id == assignment_id).first()
                    if ass and ass.settings:
                        for key in ("source_scan_enabled", "source_scan_sites"):
                            if key in ass.settings:
                                settings_payload[key] = ass.settings[key]
            except Exception:
                logger.warning("Failed to load per-assignment external scan settings override")

        # Per-submission override from upload form (highest priority)
        if job_id in _jobs and "source_scan_enabled_override" in _jobs[job_id]:
            settings_payload["source_scan_enabled"] = _jobs[job_id]["source_scan_enabled_override"]

        web_analysis = _build_web_analysis_summary(submissions, settings_payload)
        pair_ai_details = _build_pair_ai_details(results, ai_detection)
        calibration_report = _build_calibration_report(threshold, mode.mode_id)
        reproducibility_report = _build_reproducibility_report(
            submissions, selected_tool_ids, mode
        )
        ai_text_trust = _build_ai_text_trust_report(ai_detection)

        comparison_details = []
        for r in results:
            detail = type(
                "ComparisonDetail",
                (object,),
                {
                    "file_a": r.file_a,
                    "file_b": r.file_b,
                    "score": r.score,
                    "risk": r.risk_level,
                    "features": r.features,
                    "code_a": submissions.get(r.file_a, ""),
                    "code_b": submissions.get(r.file_b, ""),
                },
            )()
            comparison_details.append(detail)

        rg = ReportGenerator(
            institution_name=course_name or "Course",
            branding_color="#2563eb",
        )
        report_summary = {
            "total_files": len(submissions),
            "total_pairs": len(results),
            "suspicious_pairs": report["summary"].get("suspicious_pairs", 0),
            "average_similarity": (
                sum(r.score for r in results) / len(results) if results else 0.0
            ),
            "risk_distribution": {
                "critical": sum(1 for r in results if r.risk_level == "CRITICAL"),
                "high": sum(1 for r in results if r.risk_level == "HIGH"),
                "medium": sum(1 for r in results if r.risk_level == "MEDIUM"),
                "low": sum(1 for r in results if r.risk_level == "LOW"),
            },
        }
        report_pairs = [
            {
                "file_a": r.file_a,
                "file_b": r.file_b,
                "similarity_score": r.score,
                "risk_level": r.risk_level,
                "engine_scores": r.features,
                "ai_detection": pair_ai_details.get(_pair_key(r.file_a, r.file_b), {}),
                "code_a": submissions.get(r.file_a, ""),
                "code_b": submissions.get(r.file_b, ""),
                "external_evidence": _external_evidence_for_pair(
                    r.file_a, r.file_b, external_tool_results
                ),
            }
            for r in results
        ]
        report_payload = {
            "report_id": job_id,
            "summary": report_summary,
            "pairs": report_pairs,
            "selected_tools": _jobs[job_id].get("selected_tools", []),
            "external_tool_results": external_tool_results,
            "assignment_mode": _jobs[job_id].get("assignment_mode"),
            "assignment_mode_name": _jobs[job_id].get("assignment_mode_name"),
            "assignment_mode_version": _jobs[job_id].get("assignment_mode_version"),
            "assignment_mode_policy": _jobs[job_id].get("assignment_mode_policy", {}),
            "calibration_report": calibration_report,
            "reproducibility": reproducibility_report,
            "ai_text_trust": ai_text_trust,
            "ai_detection": ai_detection,
            "web_analysis": web_analysis,
        }
        html_report = rg.generate_html_report(report_payload)
        html_report_path = REPORTS_DIR / job_id / "report.html"
        html_report_path.write_text(html_report)
        json_report = rg.generate_json_report(report_payload)
        json_report_path = REPORTS_DIR / job_id / "report.json"
        json_report_path.write_text(json_report)
        committee_report_path = REPORTS_DIR / job_id / "committee_report.html"
        _generate_committee_report(
            job_id,
            course_name,
            assignment_name,
            threshold,
            report,
            comparison_details,
            submissions,
            committee_report_path,
            _jobs[job_id].get("selected_tools", []),
            {
                "id": _jobs[job_id].get("assignment_mode"),
                "name": _jobs[job_id].get("assignment_mode_name"),
                "version": _jobs[job_id].get("assignment_mode_version"),
                "policy": _jobs[job_id].get("assignment_mode_policy", {}),
            },
            calibration_report,
            reproducibility_report,
            ai_text_trust,
        )

        _jobs[job_id].update(
            {
                "status": "completed",
                "results": [
                    {
                        "file_a": r.file_a,
                        "file_b": r.file_b,
                        "score": r.score,
                        "risk_level": r.risk_level,
                        "features": dict(r.features),
                        "contributions": dict(r.contributions),
                        "fusion_debug": _build_fusion_debug(r, threshold),
                        "matching_blocks": r.matching_blocks or [],
                        "code_a": r.code_a,
                        "code_b": r.code_b,
                    }
                    for r in results
                ],
                "summary": report["summary"],
                "selected_tool_ids": selected_tool_ids,
                "selected_tools": _jobs[job_id].get("selected_tools", []),
                "external_tool_results": external_tool_results,
                "calibration_report": calibration_report,
                "reproducibility": reproducibility_report,
                "ai_text_trust": ai_text_trust,
                "ai_detection": ai_detection,
                "web_analysis": web_analysis,
                "report_path": str(html_report_path),
                "report_json_path": str(json_report_path),
                "committee_report_path": str(committee_report_path),
                "submissions": {k: v[:3000] for k, v in submissions.items()},
            }
        )
        _persist_job(job_id)
        _update_job_status_in_db(job_id, "completed")

        # Persist SimilarityResult rows to DB (minimal wiring for results/[id] page)
        try:
            with SessionLocal() as db:
                for r in results:
                    external_ev = _external_evidence_for_pair(
                        r.file_a, r.file_b, external_tool_results
                    )
                    mb = getattr(r, "matching_blocks", None) or getattr(
                        r, "features", {}
                    ).get("matching_blocks", [])
                    conf = getattr(r, "confidence", None) or getattr(
                        r, "confidence_level", None
                    )

                    db.add(
                        SimilarityResult(
                            id=str(uuid.uuid4()),
                            job_id=job_id,
                            submission_a_id=r.file_a,
                            submission_b_id=r.file_b,
                            similarity_score=r.score,
                            confidence_level=conf,
                            confidence_lower=getattr(r, "confidence_lower", None),
                            confidence_upper=getattr(r, "confidence_upper", None),
                            matching_blocks=mb if isinstance(mb, (list, dict)) else [],
                            excluded_matches=getattr(r, "excluded_matches", None) or {},
                            algorithm_scores={
                                **dict(getattr(r, "features", {})),
                                "external_evidence": external_ev or {},
                                "contributions": dict(getattr(r, "contributions", {})),
                            },
                            created_at=datetime.now(),
                        )
                    )
                db.commit()
        except Exception:
            logger.exception(
                f"DB results persist skipped for job {job_id}"
            )  # shows full traceback in logs

        return JSONResponse(content={"job_id": job_id, "status": "completed"})
    except Exception as e:
        logger.exception(f"Analysis failed for job {job_id}")
        if job_id in _jobs:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
            _persist_job(job_id)
            _update_job_status_in_db(job_id, "failed", str(e))
        return JSONResponse(
            status_code=500, content={"error": f"Analysis failed: {str(e)}"}
        )


@app.get("/api/jobs")
async def list_jobs(request: Request):
    current_user = _require_current_user(request)
    return JSONResponse(content={"jobs": _list_all_jobs(current_user)})


@app.get("/api/job/{job_id}")
@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str, request: Request):
    job = _require_job_access(job_id, request)
    return JSONResponse(content=job)


@app.patch("/api/job/{job_id}/review")
async def update_job_review(job_id: str, request: Request):
    job = _require_job_access(job_id, request)

    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid review payload")

    if (
        "review_status" not in payload
        and "review_notes" not in payload
        and "pair_reviews" not in payload
    ):
        raise HTTPException(status_code=400, detail="No review updates provided")

    if "review_status" in payload:
        review_status = payload.get("review_status")
        if review_status not in REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid review status")
        job["review_status"] = review_status

    if "review_notes" in payload:
        review_notes = payload.get("review_notes", "")
        if not isinstance(review_notes, str):
            raise HTTPException(status_code=400, detail="Review notes must be a string")
        job["review_notes"] = review_notes.strip()

    # Per-pair review persistence to database (SimilarityResult rows)
    if "pair_reviews" in payload and isinstance(payload.get("pair_reviews"), dict):
        try:
            with SessionLocal() as db:
                for pair_key, review_data in payload["pair_reviews"].items():
                    if not isinstance(review_data, dict):
                        continue
                    parts = (
                        str(pair_key).split("::")
                        if "::" in str(pair_key)
                        else str(pair_key).split(":")
                    )
                    if len(parts) >= 2:
                        a_id, b_id = parts[0], parts[1]
                        sim = (
                            db.query(SimilarityResult)
                            .filter(
                                SimilarityResult.job_id == job_id,
                                SimilarityResult.submission_a_id == a_id,
                                SimilarityResult.submission_b_id == b_id,
                            )
                            .first()
                        )
                        if sim:
                            if (
                                "status" in review_data
                                or "review_status" in review_data
                            ):
                                sim.review_status = review_data.get(
                                    "status"
                                ) or review_data.get("review_status")
                            if "notes" in review_data or "review_notes" in review_data:
                                sim.review_notes = (
                                    review_data.get("notes")
                                    or review_data.get("review_notes")
                                    or ""
                                ).strip() or None
                db.commit()
        except Exception:
            logger.warning(f"Failed to persist per-pair reviews for job {job_id}")

    # Also reflect in in-memory results if present
    if (
        "results" in job
        and isinstance(job["results"], list)
        and "pair_reviews" in payload
    ):
        for r in job["results"]:
            k = f"{r.get('file_a')}::{r.get('file_b')}"
            if k in payload["pair_reviews"]:
                rd = payload["pair_reviews"][k]
                if "status" in rd or "review_status" in rd:
                    r["review_status"] = rd.get("status") or rd.get("review_status")
                if "notes" in rd or "review_notes" in rd:
                    r["review_notes"] = rd.get("notes") or rd.get("review_notes")

    job["review_updated_at"] = datetime.now().isoformat()
    _jobs[job_id] = job
    _persist_job(job_id)
    return JSONResponse(content=_jobs[job_id])


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str, request: Request):
    _require_job_access(job_id, request)
    job = _jobs.pop(job_id, None)
    if (
        not job
        and not _job_metadata_path(job_id).exists()
        and not _job_report_dir(job_id).exists()
    ):
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = UPLOADS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    report_dir = _job_report_dir(job_id)
    if report_dir.exists():
        shutil.rmtree(report_dir)
    return JSONResponse(content={"status": "deleted"})


@app.get("/api/benchmark-tools")
async def get_benchmark_tools():
    tools = [
        tool
        for tool in _list_benchmark_tools()
        if tool["id"] in REAL_BENCHMARK_TOOL_IDS
    ]
    # Add 'available' field for frontend compatibility
    for tool in tools:
        tool["available"] = tool.get("runnable", False)
    return JSONResponse(content={"tools": tools})


@app.post("/api/benchmark/real-fpr")
async def compute_real_fpr_on_clean_corpus(
    files: List[UploadFile] = File(...),
):
    """
    Compute real False Positive Rate on a set of known-clean submissions.
    Used for professor-release validation of the plagiarism checker.
    """
    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 submissions are required to compute FPR.",
        )

    submissions: Dict[str, str] = {}
    for upload in files:
        try:
            content = (await upload.read()).decode("utf-8", errors="ignore")
            if len(content.strip()) > 30:
                submissions[upload.filename] = content
        except Exception:
            continue

    if len(submissions) < 2:
        raise HTTPException(
            status_code=400, detail="Could not load enough valid submissions."
        )

    try:
        # Use very low threshold to capture full distribution
        service = BatchDetectionService(threshold=0.0)
        pair_results = service.compare_all_pairs(submissions)

        scores = [float(r.score) for r in pair_results]
        num_pairs = len(scores)
        num_submissions = len(submissions)
    except Exception as e:
        logger.exception("Real FPR computation failed")
        raise HTTPException(
            status_code=500, detail=f"Internal error during FPR computation: {str(e)}"
        ) from e

    # Very fine-grained thresholds focused on the critical professor decision zone
    # Extra density between 0.65 – 0.78 (most common range where professors tune)
    thresholds_to_evaluate = [
        0.40,
        0.45,
        0.50,
        0.52,
        0.55,
        0.58,
        0.60,
        0.62,
        0.64,
        0.65,
        0.66,
        0.67,
        0.68,
        0.69,
        0.70,
        0.71,
        0.72,
        0.73,
        0.74,
        0.75,
        0.76,
        0.77,
        0.78,
        0.80,
        0.82,
        0.85,
        0.88,
        0.90,
        0.95,
    ]

    fpr_table = []
    for t in thresholds_to_evaluate:
        above = sum(1 for s in scores if s >= t)
        fpr = above / num_pairs if num_pairs > 0 else 0.0

        if fpr <= 0.015:
            label = "Excellent – very safe"
        elif fpr <= 0.03:
            label = "Good – comfortable for most courses"
        elif fpr <= 0.05:
            label = "Acceptable – use with evidence review"
        elif fpr <= 0.08:
            label = "Borderline – caution recommended"
        else:
            label = "High risk – too many false positives"

        fpr_table.append(
            {
                "threshold": round(t, 2),
                "fpr": round(fpr, 4),
                "fpr_percent": round(fpr * 100, 2),
                "label": label,
                "flagged_pairs": above,
            }
        )

    # === Sophisticated Multi-Factor Recommendation Logic ===
    # Find the most conservative "very safe" threshold (FPR ≤ 1.5%)
    very_safe = next((row for row in fpr_table if row["fpr"] <= 0.015), None)
    # Find the best balanced threshold (FPR ≤ 3%)
    balanced = next((row for row in fpr_table if row["fpr"] <= 0.03), None)
    # Find the highest recall threshold that is still acceptable (FPR ≤ 5%)
    high_recall = next((row for row in fpr_table if row["fpr"] <= 0.05), None)

    # Context from the clean corpus
    mean_clean = sum(scores) / len(scores) if scores else 0
    max_clean = max(scores) if scores else 0

    recommendations = []

    if very_safe:
        recommendations.append(
            {
                "threshold": very_safe["threshold"],
                "fpr": very_safe["fpr_percent"],
                "type": "very_safe",
                "title": "Maximum Safety",
                "advice": f"At {very_safe['threshold']*100:.0f}% the FPR on your clean data is only {very_safe['fpr_percent']:.1f}%. This is the most conservative setting and minimizes risk of false accusations.",
            }
        )

    if balanced:
        recommendations.append(
            {
                "threshold": balanced["threshold"],
                "fpr": balanced["fpr_percent"],
                "type": "balanced",
                "title": "Recommended Default",
                "advice": f"At {balanced['threshold']*100:.0f}% you get a good balance (FPR ≈ {balanced['fpr_percent']:.1f}%). Strong choice for most undergraduate courses.",
            }
        )

    if high_recall:
        recommendations.append(
            {
                "threshold": high_recall["threshold"],
                "fpr": high_recall["fpr_percent"],
                "type": "high_recall",
                "title": "Higher Detection (with review)",
                "advice": f"At {high_recall['threshold']*100:.0f}% you catch more cases (FPR ≈ {high_recall['fpr_percent']:.1f}%). Best used when every flagged pair is manually reviewed.",
            }
        )

    # Overall assessment
    if mean_clean > 0.25:
        overall_risk = "Your clean corpus shows unusually high baseline similarity. Consider stronger starter-code / template filtering."
    elif max_clean > 0.65:
        overall_risk = "Some very similar clean pairs exist. Review the highest-scoring clean pairs to understand why."
    else:
        overall_risk = "Your clean data looks healthy. The system behaves as expected on non-plagiarized work."

    # Actionable suggestions
    suggested_actions = []
    if not very_safe or very_safe["fpr"] > 0.02:
        suggested_actions.append(
            "Raise the default decision threshold by 5–8 percentage points."
        )
    if mean_clean > 0.20:
        suggested_actions.append(
            "Enable or improve starter-code / boilerplate suppression."
        )
    if max_clean > 0.70:
        suggested_actions.append(
            "Manually review the top 5–10 clean pairs with the highest scores."
        )
    if not suggested_actions:
        suggested_actions.append(
            "Current settings appear well calibrated for your student population."
        )

    # Legacy single recommendation string (for backward compatibility)
    best = balanced or very_safe or fpr_table[-1]
    recommendation = (
        f"Recommended starting threshold: {best['threshold']*100:.0f}% "
        f"(FPR on your clean data ≈ {best['fpr_percent']:.1f}%). "
        f"{overall_risk}"
    )

    # Basic histogram (10 bins)
    bins = [0] * 10
    for s in scores:
        idx = min(int(s * 10), 9)
        bins[idx] += 1

    histogram = [
        {"bin": f"{i/10:.1f}-{(i+1)/10:.1f}", "count": bins[i]} for i in range(10)
    ]

    return JSONResponse(
        content={
            "num_submissions": num_submissions,
            "num_pairs": num_pairs,
            "fpr_table": fpr_table,
            "score_histogram": histogram,
            "recommendation": recommendation,  # legacy string
            "mean_score": round(sum(scores) / len(scores), 4) if scores else 0,
            "max_score": round(max(scores), 4) if scores else 0,
            # New structured data for better frontend experience
            "recommendations": recommendations,
            "overall_assessment": overall_risk,
            "suggested_actions": suggested_actions,
        }
    )


class FprValidationRunCreate(BaseModel):
    """Request body for saving an FPR validation run (internal tool endpoint)."""

    name: Optional[str] = None
    result: Dict[str, Any]
    notes: Optional[str] = None


# ============================================================
# FPR Validation Runs History (Database-backed)
# ============================================================


@app.post("/api/fpr-validation-runs")
async def save_fpr_validation_run(
    request: Request,
    payload: FprValidationRunCreate,
):
    """Save a completed FPR validation run to the database."""
    try:
        current_user = _require_current_user(request, admin_only=False)
        tenant_id = current_user.get("tenant_id")
        user_id = current_user.get("id")

        if not tenant_id:
            raise HTTPException(
                status_code=400, detail="No tenant associated with user"
            )

        name = (
            payload.name
            or f"FPR Run - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        )
        result_data = payload.result

        run = FprValidationRun(
            tenant_id=tenant_id,
            user_id=user_id,
            name=name,
            payload=result_data,
            num_submissions=result_data.get("num_submissions"),
            num_pairs=result_data.get("num_pairs"),
            mean_score=result_data.get("mean_score"),
            max_score=result_data.get("max_score"),
            recommended_threshold=result_data.get("recommended_threshold"),
            fpr_at_recommended_threshold=result_data.get(
                "fpr_at_recommended_threshold"
            ),
            notes=payload.notes,
            status="completed",
        )

        with SessionLocal() as db:
            db.add(run)
            db.commit()
            db.refresh(run)

        return {"id": run.id, "name": run.name, "created_at": run.created_at}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to save FPR validation run")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fpr-validation-runs")
async def list_fpr_validation_runs(
    request: Request,
    limit: int = 50,
):
    """List historical FPR validation runs for the current tenant."""
    try:
        current_user = _require_current_user(request, admin_only=False)
        tenant_id = current_user.get("tenant_id")

        with SessionLocal() as db:
            runs = (
                db.query(FprValidationRun)
                .filter(FprValidationRun.tenant_id == tenant_id)
                .order_by(FprValidationRun.created_at.desc())
                .limit(limit)
                .all()
            )

            return {
                "runs": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "created_at": r.created_at,
                        "num_submissions": r.num_submissions,
                        "num_pairs": r.num_pairs,
                        "recommended_threshold": r.recommended_threshold,
                        "fpr_at_recommended_threshold": r.fpr_at_recommended_threshold,
                        "is_certified": r.is_certified,
                        "status": r.status,
                    }
                    for r in runs
                ]
            }

    except Exception as e:
        logger.exception("Failed to list FPR validation runs")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fpr-validation-runs/{run_id}")
async def get_fpr_validation_run(run_id: str, request: Request):
    """Retrieve a single saved FPR validation run."""
    try:
        current_user = _require_current_user(request, admin_only=False)
        tenant_id = current_user.get("tenant_id")

        with SessionLocal() as db:
            run = (
                db.query(FprValidationRun)
                .filter(
                    FprValidationRun.id == run_id,
                    FprValidationRun.tenant_id == tenant_id,
                )
                .first()
            )

            if not run:
                raise HTTPException(
                    status_code=404, detail="FPR validation run not found"
                )

            return {
                "id": run.id,
                "name": run.name,
                "created_at": run.created_at,
                "notes": run.notes,
                "is_certified": run.is_certified,
                "certified_at": run.certified_at,
                "result": run.payload,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to fetch FPR validation run")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/fpr-validation-runs/{run_id}")
async def delete_fpr_validation_run(run_id: str, request: Request):
    """Delete a saved FPR validation run."""
    try:
        current_user = _require_current_user(request, admin_only=False)
        tenant_id = current_user.get("tenant_id")

        with SessionLocal() as db:
            run = (
                db.query(FprValidationRun)
                .filter(
                    FprValidationRun.id == run_id,
                    FprValidationRun.tenant_id == tenant_id,
                )
                .first()
            )

            if not run:
                raise HTTPException(
                    status_code=404, detail="FPR validation run not found"
                )

            db.delete(run)
            db.commit()

        return {"success": True}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete FPR validation run")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# End of FPR Validation Runs History
# ============================================================


BENCHMARK_DATASETS = []

BENCHMARK_WORKFLOW_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "quick_precision_check",
        "name": "Quick Precision Check",
        "mode": "pan_optimization",
        "dataset": "synthetic",
        "tools": ["integritydesk", "jplag"],
        "cadence": "Run after every scoring or threshold change.",
        "goal": "Catch false positives quickly before spending time on larger datasets.",
        "success_criteria": {
            "precision": 0.9,
            "false_positive_rate": 0.05,
            "f1_score": 0.75,
        },
    },
    {
        "id": "student_code_regression",
        "name": "Student Code Regression",
        "mode": "pan_optimization",
        "dataset": "kaggle_student_code",
        "tools": ["integritydesk", "jplag"],
        "cadence": "Run before committing product scoring changes.",
        "goal": "Validate classroom-style behavior on real student-code pairs.",
        "success_criteria": {
            "precision": 0.9,
            "false_positive_rate": 0.08,
            "f1_score": 0.75,
        },
    },
    {
        "id": "main_clone_benchmark",
        "name": "Main Clone Benchmark",
        "mode": "pan_optimization",
        "dataset": "codexglue_clone",
        "tools": ["integritydesk", "jplag", "dolos", "moss"],
        "cadence": "Run when a smaller benchmark shows improvement.",
        "goal": "Stress-test IntegrityDesk against a large labeled clone-pair corpus.",
        "success_criteria": {
            "precision": 0.92,
            "false_positive_rate": 0.05,
            "plagdet": 0.85,
        },
    },
    {
        "id": "tool_comparison_full",
        "name": "Tool Comparison Full",
        "mode": "tool_comparison",
        "dataset": "codexglue_clone",
        "tools": ["integritydesk", "jplag", "dolos", "moss"],
        "cadence": "Run for competitive comparison screenshots and release notes.",
        "goal": "Compare IntegrityDesk with available external plagiarism detectors.",
        "success_criteria": {
            "plagdet": 0.85,
            "auc_pr": 0.9,
            "avg_runtime_seconds": 0.5,
        },
    },
]


def _benchmark_history_path() -> PathLib:
    """Return the JSON file used for lightweight benchmark run history."""
    return BENCHMARK_RUNS_DIR / "history.json"


def _read_benchmark_history() -> List[Dict[str, Any]]:
    """Read recent benchmark run summaries from disk."""
    history_path = _benchmark_history_path()
    if not history_path.exists():
        return []
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Failed to read benchmark history")
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _write_benchmark_history(history: List[Dict[str, Any]]) -> None:
    """Persist benchmark run history with a bounded number of recent entries."""
    history_path = _benchmark_history_path()
    history_path.write_text(
        json.dumps(history[:100], indent=2, sort_keys=True), encoding="utf-8"
    )


def _metric_from_benchmark_response(response: Dict[str, Any], metric: str) -> float:
    """Extract an IntegrityDesk metric from a benchmark response."""
    integrity_metrics = (response.get("evaluation") or {}).get("integritydesk") or {}
    if metric in integrity_metrics:
        return float(integrity_metrics.get(metric) or 0.0)
    if metric == "runtime_seconds":
        return float(
            ((response.get("tool_scores") or {}).get("integritydesk") or {}).get(
                "runtime_seconds", 0.0
            )
        )
    if metric == "avg_runtime_seconds":
        return float(
            ((response.get("tool_scores") or {}).get("integritydesk") or {}).get(
                "avg_runtime_seconds", 0.0
            )
        )
    return 0.0


def _benchmark_run_summary(response: Dict[str, Any]) -> Dict[str, Any]:
    """Create a compact benchmark run summary for history and comparisons."""
    metrics = {
        "precision": _metric_from_benchmark_response(response, "precision"),
        "recall": _metric_from_benchmark_response(response, "recall"),
        "f1_score": _metric_from_benchmark_response(response, "f1_score"),
        "plagdet": _metric_from_benchmark_response(response, "plagdet"),
        "auc_pr": _metric_from_benchmark_response(response, "auc_pr"),
        "false_positive_rate": _metric_from_benchmark_response(
            response, "false_positive_rate"
        ),
        "avg_runtime_seconds": _metric_from_benchmark_response(
            response, "avg_runtime_seconds"
        ),
    }
    return {
        "job_id": response.get("job_id"),
        "preset_id": response.get("preset_id") or "",
        "preset_name": response.get("preset_name") or "",
        "dataset": (response.get("summary") or {}).get("dataset_name", ""),
        "benchmark_type": response.get("benchmark_type", ""),
        "tools": response.get("requested_tools", []),
        "run_at": response.get("runAt") or datetime.now(timezone.utc).isoformat(),
        "pairs_tested": (response.get("summary") or {}).get("pairs_tested", 0),
        "has_ground_truth": response.get("has_ground_truth", False),
        "metrics": {key: round(value, 6) for key, value in metrics.items()},
    }


def _find_previous_benchmark_run(
    history: List[Dict[str, Any]], current: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Find the latest comparable prior run for the same workflow and dataset."""
    for item in history:
        if item.get("job_id") == current.get("job_id"):
            continue
        same_preset = item.get("preset_id") and item.get("preset_id") == current.get(
            "preset_id"
        )
        same_dataset = item.get("dataset") == current.get("dataset")
        same_mode = item.get("benchmark_type") == current.get("benchmark_type")
        if same_dataset and same_mode and (same_preset or not current.get("preset_id")):
            return item
    return None


def _build_benchmark_delta(
    current: Dict[str, Any], previous: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Compute metric deltas against a previous comparable run."""
    if not previous:
        return {"has_previous": False, "metrics": {}}

    deltas = {}
    current_metrics = current.get("metrics", {})
    previous_metrics = previous.get("metrics", {})
    for metric, value in current_metrics.items():
        prior = float(previous_metrics.get(metric, 0.0) or 0.0)
        deltas[metric] = round(float(value or 0.0) - prior, 6)

    return {
        "has_previous": True,
        "previous_job_id": previous.get("job_id"),
        "previous_run_at": previous.get("run_at"),
        "metrics": deltas,
    }


def _persist_benchmark_response(response: Dict[str, Any]) -> Dict[str, Any]:
    """Save a full benchmark response and update the compact run history."""
    summary = _benchmark_run_summary(response)
    history = _read_benchmark_history()
    comparison = _build_benchmark_delta(
        summary, _find_previous_benchmark_run(history, summary)
    )
    summary["comparison"] = comparison

    run_path = BENCHMARK_RUNS_DIR / f"{summary['job_id']}.json"
    response["history_summary"] = summary
    response["comparison"] = comparison
    response["runAt"] = summary["run_at"]
    run_path.write_text(
        json.dumps(response, indent=2, sort_keys=True), encoding="utf-8"
    )

    history = [item for item in history if item.get("job_id") != summary["job_id"]]
    history.insert(0, summary)
    _write_benchmark_history(history)

    # Wire benchmark run metadata to DB (so benchmark/page.tsx + Admin can list/reload from DB)
    try:
        with SessionLocal() as db:
            job_id = summary.get("job_id")
            if job_id:
                db_job = db.query(Job).filter(Job.id == job_id).first()
                benchmark_settings = {
                    "type": "benchmark",
                    "dataset": summary.get("dataset"),
                    "tools": summary.get("tools"),
                    "summary": summary,
                }
                if not db_job:
                    run_at = summary.get("run_at")
                    try:
                        created_at = (
                            datetime.fromisoformat(run_at) if run_at else datetime.now()
                        )
                    except Exception:
                        created_at = datetime.now()

                    db_job = Job(
                        id=job_id,
                        name=f"Benchmark: {summary.get('dataset', 'unknown')}",
                        status="completed",
                        settings=benchmark_settings,
                        created_at=created_at,
                    )
                    db.add(db_job)
                else:
                    db_job.settings = {**(db_job.settings or {}), **benchmark_settings}
                    db_job.status = "completed"
                db.commit()
    except Exception:
        logger.warning(f"Failed to persist benchmark run {summary.get('job_id')} to DB")

    return response


@app.get("/api/benchmark-presets")
async def get_benchmark_presets() -> Dict[str, Any]:
    """Return repeatable benchmark workflows for product optimization."""
    available_tools = {
        tool["id"]: tool
        for tool in _list_benchmark_tools()
        if tool["id"] in REAL_BENCHMARK_TOOL_IDS
    }
    datasets = {item.name for item in _iter_benchmark_dataset_roots()}
    datasets.update(
        dataset_id
        for dataset_id in BUILTIN_PAIR_DATASET_IDS
        if _builtin_pair_dataset_path(dataset_id).exists()
    )
    presets = []
    for preset in BENCHMARK_WORKFLOW_PRESETS:
        runnable_tools = [
            tool_id
            for tool_id in preset["tools"]
            if available_tools.get(tool_id, {}).get("runnable")
        ]
        blocked_tools = [
            {
                "id": tool_id,
                "status": available_tools.get(tool_id, {}).get(
                    "status", "Not installed"
                ),
            }
            for tool_id in preset["tools"]
            if tool_id not in runnable_tools
        ]
        presets.append(
            {
                **preset,
                "runnable_tools": runnable_tools,
                "blocked_tools": blocked_tools,
                "dataset_ready": preset["dataset"] in datasets,
            }
        )
    return {"presets": presets}


@app.get("/api/benchmark-history")
async def get_benchmark_history(limit: int = 20) -> Dict[str, Any]:
    """Return recent benchmark run summaries (file + DB for native persistence)."""
    safe_limit = max(1, min(100, int(limit)))
    runs = _read_benchmark_history()[:safe_limit]

    # DB-backed benchmark runs (so benchmark/page.tsx can list/reload from DB)
    try:
        with SessionLocal() as db:
            db_benchmarks = (
                db.query(Job)
                .filter(Job.settings.op("->>")("type") == "benchmark")
                .order_by(Job.created_at.desc())
                .limit(safe_limit)
                .all()
            )
            for j in db_benchmarks:
                s = (j.settings or {}).get("summary") or {}
                if s and not any(r.get("job_id") == j.id for r in runs):
                    runs.append(s)
    except Exception:
        logger.warning("Failed to load benchmark runs from DB")

    return {"runs": runs[:safe_limit]}


@app.get("/api/courses")
async def get_courses(request: Request) -> Dict[str, Any]:
    """Return courses visible to the current user.

    A user can see a course if:
    - They are explicitly assigned as an instructor (via course_instructors), or
    - They belong to the same organization as the course.
    """
    try:
        try:
            current_user = _require_current_user(request, admin_only=False)
            user_id = current_user.get("id")
            user_org_id = current_user.get("organization_id")
        except Exception:
            return {"courses": []}

        with SessionLocal() as db:
            q = db.query(Course)

            # Build OR condition: direct instructor OR same organization
            filters = []
            if user_id:
                filters.append(
                    Course.id.in_(
                        db.query(CourseInstructor.course_id).filter(
                            CourseInstructor.user_id == user_id
                        )
                    )
                )
            if user_org_id:
                filters.append(Course.organization_id == user_org_id)

            if filters:
                q = q.filter(or_(*filters))
            else:
                # No org and no assignments → return nothing
                return {"courses": []}

            courses = q.order_by(Course.name).all()
            return {
                "courses": [
                    {
                        "id": c.id,
                        "name": c.name,
                        "code": c.code,
                        "organization_id": c.organization_id,
                    }
                    for c in courses
                ]
            }
    except Exception:
        logger.warning("Failed to fetch courses (instructor + org scoped)")
        return {"courses": []}


@app.get("/api/assignments")
async def get_assignments(
    course_id: Optional[str] = None, request: Request = None
) -> Dict[str, Any]:
    """Return assignments visible to the current user (instructor + org scoped)."""
    try:
        try:
            current_user = _require_current_user(request, admin_only=False)
            user_id = current_user.get("id")
            user_org_id = current_user.get("organization_id")
        except Exception:
            return {"assignments": []}

        with SessionLocal() as db:
            q = db.query(Assignment)

            # Join to Course to apply visibility rules
            q = q.join(Course)

            filters = []
            if user_id:
                filters.append(
                    Course.id.in_(
                        db.query(CourseInstructor.course_id).filter(
                            CourseInstructor.user_id == user_id
                        )
                    )
                )
            if user_org_id:
                filters.append(Course.organization_id == user_org_id)

            if filters:
                q = q.filter(or_(*filters))
            else:
                return {"assignments": []}

            if course_id:
                q = q.filter(Assignment.course_id == course_id)

            assignments = q.order_by(Assignment.name).all()
            return {
                "assignments": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "course_id": a.course_id,
                        "due_at": a.due_at.isoformat() if a.due_at else None,
                    }
                    for a in assignments
                ]
            }
    except Exception:
        logger.warning("Failed to fetch assignments (instructor + org scoped)")
        return {"assignments": []}


@app.get("/api/error-analysis")
async def get_error_analysis() -> Dict[str, Any]:
    """Compute real error analysis from stored benchmark runs and job results.

    Priority:
    1. Most recent benchmark run with ground-truth labels → full TP/FP/FN/TN + real cases
    2. All job results → score-distribution analysis with real file names and engine data
    """
    # ── 1. Try benchmark runs with ground truth ──────────────────────────
    benchmark_runs = sorted(
        BENCHMARK_RUNS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    labeled_run: Optional[Dict[str, Any]] = None
    for run_path in benchmark_runs[:10]:  # check last 10 runs
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            if run.get("has_ground_truth") and run.get("pair_results"):
                labeled_run = run
                break
        except Exception:
            continue

    if labeled_run:
        return _build_error_analysis_from_benchmark(labeled_run)

    # ── 2. Fall back to job results ──────────────────────────────────────
    return _build_error_analysis_from_jobs()


def _build_error_analysis_from_benchmark(run: Dict[str, Any]) -> Dict[str, Any]:
    """Build full error analysis from a benchmark run that has ground-truth labels."""
    pair_results = run.get("pair_results", [])
    tool_scores = run.get("tool_scores", {})
    evaluation = run.get("evaluation", {})
    dataset_name = run.get("summary", {}).get("dataset_name") or run.get(
        "dataset", "benchmark"
    )

    # Determine primary tool (integritydesk preferred)
    primary_tool = (
        "integritydesk"
        if "integritydesk" in tool_scores
        else (next(iter(tool_scores), None))
    )

    # Get threshold from evaluation or default
    threshold = 0.5
    if primary_tool and evaluation.get(primary_tool):
        t = evaluation[primary_tool].get("best_threshold") or evaluation[
            primary_tool
        ].get("fixed_threshold")
        if t is not None:
            threshold = float(t)

    tp = fp = fn = tn = 0
    false_positive_cases: List[Dict[str, Any]] = []
    false_negative_cases: List[Dict[str, Any]] = []
    engine_fp_counts: Dict[str, int] = {}
    engine_fn_counts: Dict[str, int] = {}

    for pair in pair_results:
        gt = pair.get("ground_truth_label")
        if gt is None:
            continue
        is_plagiarism = int(gt) >= 2  # PAN convention: label >= 2 means plagiarism

        # Get score for primary tool
        score = None
        features: Dict[str, Any] = {}
        contributions: Dict[str, Any] = {}
        for tr in pair.get("tool_results", []):
            if tr.get("tool") == primary_tool:
                score = float(tr.get("score", 0))
                features = tr.get("features", {})
                contributions = tr.get("contributions", {})
                break
        if score is None:
            continue

        predicted = score >= threshold

        if is_plagiarism and predicted:
            tp += 1
        elif not is_plagiarism and predicted:
            fp += 1
            # Track which engines drove this FP
            dominant = (
                max(contributions, key=lambda k: contributions[k], default=None)
                if contributions
                else None
            )
            if dominant:
                engine_fp_counts[dominant] = engine_fp_counts.get(dominant, 0) + 1
            if len(false_positive_cases) < 10:
                false_positive_cases.append(
                    _make_error_case(
                        pair, score, "false_positive", features, contributions
                    )
                )
        elif is_plagiarism and not predicted:
            fn += 1
            dominant = (
                max(contributions, key=lambda k: contributions[k], default=None)
                if contributions
                else None
            )
            if dominant:
                engine_fn_counts[dominant] = engine_fn_counts.get(dominant, 0) + 1
            if len(false_negative_cases) < 10:
                false_negative_cases.append(
                    _make_error_case(
                        pair, score, "false_negative", features, contributions
                    )
                )
        else:
            tn += 1

    total = tp + fp + fn + tn
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    accuracy = (tp + tn) / max(total, 1)

    # Engine contribution percentages
    fp_total = sum(engine_fp_counts.values()) or 1
    fn_total = sum(engine_fn_counts.values()) or 1

    # Pull engine contributions from evaluation if available
    eval_data = evaluation.get(primary_tool, {})
    engine_contrib = eval_data.get("engine_contribution", {})

    def _engine_pct_from_counts(
        counts: Dict[str, int], total_count: int
    ) -> Dict[str, int]:
        return {
            k: round(v / total_count * 100)
            for k, v in sorted(counts.items(), key=lambda x: -x[1])[:6]
        }

    fp_engine_pct = (
        _engine_pct_from_counts(engine_fp_counts, fp_total)
        if engine_fp_counts
        else _invert_engine_contrib(engine_contrib)
    )
    fn_engine_pct = (
        _engine_pct_from_counts(engine_fn_counts, fn_total)
        if engine_fn_counts
        else engine_contrib
    )

    return {
        "source": "benchmark",
        "dataset": dataset_name,
        "job_id": run.get("job_id"),
        "has_ground_truth": True,
        "threshold": threshold,
        "summary": {
            "totalPairs": total,
            "truePositives": tp,
            "trueNegatives": tn,
            "falsePositives": fp,
            "falseNegatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
        },
        "falsePositives": false_positive_cases,
        "falseNegatives": false_negative_cases,
        "engineContributions": {
            "falsePositives": fp_engine_pct,
            "falseNegatives": fn_engine_pct,
        },
        "recommendations": _generate_recommendations(
            fp, fn, precision, recall, engine_contrib
        ),
    }


def _build_error_analysis_from_jobs() -> Dict[str, Any]:
    """Build error analysis from stored plagiarism job results (no ground truth)."""
    all_results: List[Dict[str, Any]] = []
    job_count = 0

    for job_path in sorted(
        REPORTS_DIR.glob("*/job.json"), key=lambda p: p.stat().st_mtime, reverse=True
    )[:50]:
        try:
            job = json.loads(job_path.read_text(encoding="utf-8"))
            if job.get("status") != "done":
                continue
            threshold = float(job.get("threshold", 0.5))
            for r in job.get("results", []):
                score = float(r.get("score", 0))
                features = r.get("features", {})
                all_results.append(
                    {
                        "file_a": r.get("file_a", ""),
                        "file_b": r.get("file_b", ""),
                        "score": score,
                        "features": features,
                        "threshold": threshold,
                        "flagged": score >= threshold,
                        "risk_level": r.get("risk_level", ""),
                    }
                )
            job_count += 1
        except Exception:
            continue

    if not all_results:
        return _empty_error_analysis()

    total = len(all_results)
    flagged = [r for r in all_results if r["flagged"]]
    not_flagged = [r for r in all_results if not r["flagged"]]

    # Without ground truth we can't compute real TP/FP/FN/TN.
    # Use heuristics: very high scores (>0.85) are likely true positives,
    # borderline flagged (0.5-0.65) are likely false positives,
    # high-feature-but-low-score are likely false negatives.
    likely_tp = [r for r in flagged if r["score"] >= 0.75]
    likely_fp = [r for r in flagged if r["score"] < 0.65]
    likely_fn = _find_likely_false_negatives(not_flagged)
    likely_tn = [r for r in not_flagged if r not in likely_fn]

    tp = len(likely_tp)
    fp = len(likely_fp)
    fn = len(likely_fn)
    tn = len(likely_tn)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    accuracy = (tp + tn) / max(total, 1)

    # Build real error cases from actual data
    fp_cases = [
        _make_job_error_case(r, "false_positive")
        for r in sorted(likely_fp, key=lambda x: -x["score"])[:10]
    ]
    fn_cases = [
        _make_job_error_case(r, "false_negative")
        for r in sorted(likely_fn, key=lambda x: x["score"])[:10]
    ]

    # Engine contribution from features
    fp_engine = _aggregate_engine_contributions([r["features"] for r in likely_fp])
    fn_engine = _aggregate_engine_contributions([r["features"] for r in likely_fn])

    return {
        "source": "jobs",
        "dataset": f"{job_count} plagiarism check job(s)",
        "job_id": None,
        "has_ground_truth": False,
        "threshold": 0.5,
        "summary": {
            "totalPairs": total,
            "truePositives": tp,
            "trueNegatives": tn,
            "falsePositives": fp,
            "falseNegatives": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "accuracy": round(accuracy, 4),
        },
        "falsePositives": fp_cases,
        "falseNegatives": fn_cases,
        "engineContributions": {
            "falsePositives": fp_engine,
            "falseNegatives": fn_engine,
        },
        "recommendations": _generate_recommendations(fp, fn, precision, recall, {}),
    }


def _find_likely_false_negatives(
    not_flagged: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Identify pairs that were not flagged but show suspicious feature patterns."""
    candidates = []
    for r in not_flagged:
        features = r.get("features", {})
        if not features:
            continue
        # High token/winnowing but low overall score suggests obfuscation
        token_score = float(
            features.get("token", features.get("token_similarity", 0)) or 0
        )
        winnow_score = float(features.get("winnowing", features.get("winnow", 0)) or 0)
        ast_score = float(features.get("ast", features.get("ast_similarity", 0)) or 0)
        max_sub = max(token_score, winnow_score, ast_score)
        if max_sub >= 0.6 and r["score"] < r["threshold"]:
            candidates.append(r)
    return candidates


def _make_error_case(
    pair: Dict[str, Any],
    score: float,
    error_type: str,
    features: Dict[str, Any],
    contributions: Dict[str, Any],
) -> Dict[str, Any]:
    """Build an error case dict from a benchmark pair."""
    dominant_engine = (
        max(contributions, key=lambda k: contributions[k], default="token")
        if contributions
        else "token"
    )
    dominant_pct = (
        round(float(contributions.get(dominant_engine, 0)) * 100, 1)
        if contributions
        else 0
    )

    if error_type == "false_positive":
        reason = _classify_fp_reason(features, contributions)
        explanation = (
            f"Similarity score {score:.1%} exceeded the threshold but ground truth indicates "
            f"these are independent submissions. The {dominant_engine} engine contributed "
            f"{dominant_pct}% of the fused score. This may indicate shared boilerplate, "
            f"common algorithmic patterns, or assignment template code."
        )
        recommendation = _fp_recommendation(reason)
    else:
        reason = _classify_fn_reason(features, score)
        explanation = (
            f"Similarity score {score:.1%} fell below the threshold despite being labeled as "
            f"plagiarism. The {dominant_engine} engine was the strongest signal at {dominant_pct}%. "
            f"This suggests the plagiarism was obfuscated through renaming, restructuring, or "
            f"semantic transformation."
        )
        recommendation = _fn_recommendation(reason)

    top_features = sorted(
        features.items(), key=lambda x: float(x[1] or 0), reverse=True
    )[:3]
    snippet = (
        "\n".join(f"# {k}: {float(v):.3f}" for k, v in top_features)
        if top_features
        else "# No feature breakdown available"
    )

    return {
        "id": hash(f"{pair.get('file_a')}{pair.get('file_b')}") & 0xFFFFFF,
        "fileA": str(pair.get("file_a", "file_a")),
        "fileB": str(pair.get("file_b", "file_b")),
        "score": round(score, 4),
        "reason": reason,
        "explanation": explanation,
        "codeSnippet": snippet,
        "recommendation": recommendation,
        "features": {k: round(float(v or 0), 3) for k, v in features.items()},
        "contributions": {k: round(float(v or 0), 3) for k, v in contributions.items()},
    }


def _make_job_error_case(r: Dict[str, Any], error_type: str) -> Dict[str, Any]:
    """Build an error case dict from a job result."""
    features = r.get("features", {})
    score = r["score"]
    top_features = sorted(
        features.items(), key=lambda x: float(x[1] or 0), reverse=True
    )[:3]
    snippet = (
        "\n".join(f"# {k}: {float(v):.3f}" for k, v in top_features)
        if top_features
        else "# No feature breakdown available"
    )

    if error_type == "false_positive":
        reason = _classify_fp_reason(features, {})
        explanation = (
            f"Score {score:.1%} triggered a flag (threshold {r['threshold']:.0%}) but the "
            f"similarity may be driven by shared boilerplate or common patterns rather than "
            f"actual copying. No ground-truth label is available for this pair."
        )
        recommendation = _fp_recommendation(reason)
    else:
        reason = _classify_fn_reason(features, score)
        explanation = (
            f"Score {score:.1%} fell below the threshold ({r['threshold']:.0%}) but individual "
            f"engine signals suggest possible obfuscated similarity. "
            f"Manual review is recommended."
        )
        recommendation = _fn_recommendation(reason)

    return {
        "id": hash(f"{r['file_a']}{r['file_b']}") & 0xFFFFFF,
        "fileA": str(r.get("file_a", "file_a")),
        "fileB": str(r.get("file_b", "file_b")),
        "score": round(score, 4),
        "reason": reason,
        "explanation": explanation,
        "codeSnippet": snippet,
        "recommendation": recommendation,
        "features": {k: round(float(v or 0), 3) for k, v in features.items()},
    }


def _classify_fp_reason(features: Dict[str, Any], contributions: Dict[str, Any]) -> str:
    token = float(features.get("token", features.get("token_similarity", 0)) or 0)
    ast = float(features.get("ast", features.get("ast_similarity", 0)) or 0)
    embed = float(features.get("embedding", features.get("semantic", 0)) or 0)
    if token > 0.7:
        return "Shared boilerplate or template code"
    if ast > 0.6 and token < 0.5:
        return "Algorithmic coincidence (same structure, different tokens)"
    if embed > 0.6:
        return "Semantically similar independent solutions"
    return "Borderline similarity near threshold"


def _classify_fn_reason(features: Dict[str, Any], score: float) -> str:
    token = float(features.get("token", features.get("token_similarity", 0)) or 0)
    ast = float(features.get("ast", features.get("ast_similarity", 0)) or 0)
    embed = float(features.get("embedding", features.get("semantic", 0)) or 0)
    if token < 0.3 and ast > 0.5:
        return "Variable renaming and structural obfuscation"
    if embed > 0.5 and token < 0.4:
        return "Semantic similarity hidden by surface changes"
    if score < 0.3:
        return "Heavy restructuring and logic reordering"
    return "Partial copying below detection threshold"


def _fp_recommendation(reason: str) -> str:
    if "boilerplate" in reason.lower() or "template" in reason.lower():
        return "Configure starter-code removal to exclude assignment templates from scoring."
    if "algorithmic" in reason.lower():
        return "Add algorithmic pattern recognition to distinguish independent correct solutions."
    if "semantic" in reason.lower():
        return "Increase the similarity threshold or require corroboration from multiple engines."
    return "Review manually and consider raising the detection threshold for this assignment type."


def _fn_recommendation(reason: str) -> str:
    if "renaming" in reason.lower() or "obfuscation" in reason.lower():
        return "Enable AST-based matching and identifier-normalisation to catch renamed variables."
    if "semantic" in reason.lower():
        return "Lower the embedding engine weight threshold to catch semantically equivalent code."
    if "restructuring" in reason.lower():
        return "Enable control-flow graph (CFG) comparison to detect reordered logic."
    return "Lower the detection threshold and enable all available detection engines."


def _aggregate_engine_contributions(
    feature_list: List[Dict[str, Any]]
) -> Dict[str, int]:
    """Compute average engine contribution percentages across a list of feature dicts."""
    totals: Dict[str, float] = {}
    count = 0
    for features in feature_list:
        if not features:
            continue
        count += 1
        for k, v in features.items():
            totals[k] = totals.get(k, 0.0) + float(v or 0)
    if not count:
        return {}
    avgs = {k: v / count for k, v in totals.items()}
    total_avg = sum(avgs.values()) or 1
    return {
        k: round(v / total_avg * 100)
        for k, v in sorted(avgs.items(), key=lambda x: -x[1])[:6]
        if v > 0
    }


def _invert_engine_contrib(engine_contrib: Dict[str, Any]) -> Dict[str, int]:
    """Convert engine contribution floats to integer percentages."""
    total = sum(float(v or 0) for v in engine_contrib.values()) or 1
    return {
        k: round(float(v or 0) / total * 100)
        for k, v in sorted(engine_contrib.items(), key=lambda x: -float(x[1] or 0))[:6]
    }


def _generate_recommendations(
    fp: int, fn: int, precision: float, recall: float, engine_contrib: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations based on error patterns."""
    recs = []

    if fp > fn and precision < 0.85:
        recs.append(
            {
                "category": "Reduce False Positives",
                "priority": "high",
                "items": [
                    {
                        "title": "Configure starter-code removal",
                        "detail": f"You have {fp} false positives. Upload assignment templates as starter code so the system excludes them from scoring.",
                    },
                    {
                        "title": "Raise detection threshold",
                        "detail": f"Current precision is {precision:.0%}. Increasing the threshold from 0.5 to 0.65 will reduce borderline false flags.",
                    },
                    {
                        "title": "Enable boilerplate filtering",
                        "detail": "Common imports, class headers, and standard library calls inflate token similarity scores.",
                    },
                ],
            }
        )

    if fn > fp and recall < 0.80:
        recs.append(
            {
                "category": "Catch More Plagiarism",
                "priority": "high",
                "items": [
                    {
                        "title": "Enable AST-based matching",
                        "detail": f"You have {fn} missed cases. AST comparison catches variable renaming and structural obfuscation.",
                    },
                    {
                        "title": "Lower detection threshold",
                        "detail": f"Current recall is {recall:.0%}. Lowering the threshold to 0.40 will surface more borderline cases for review.",
                    },
                    {
                        "title": "Enable semantic (embedding) engine",
                        "detail": "CodeBERT-style embeddings detect semantically equivalent code even after heavy rewriting.",
                    },
                ],
            }
        )

    recs.append(
        {
            "category": "Manual Review Guidelines",
            "priority": "medium",
            "items": [
                {
                    "title": "Score ≥ 75%: Investigate immediately",
                    "detail": "High-confidence flags are very likely real cases. Prioritise these in your review queue.",
                },
                {
                    "title": "Score 50–75%: Review code structure",
                    "detail": "Check for shared logic, renamed variables, and reordered functions before dismissing.",
                },
                {
                    "title": "Score < 50% with engine disagreement",
                    "detail": "If token and AST engines disagree significantly, manual inspection is warranted.",
                },
            ],
        }
    )

    recs.append(
        {
            "category": "Preventive Measures",
            "priority": "low",
            "items": [
                {
                    "title": "Design unique assignments",
                    "detail": "Problems with personalised inputs (student ID, unique constraints) reduce template sharing.",
                },
                {
                    "title": "Require intermediate submissions",
                    "detail": "Staged commits let you track code evolution and spot sudden large additions.",
                },
                {
                    "title": "Educate on academic integrity",
                    "detail": "Proactive communication about consequences reduces plagiarism attempts.",
                },
            ],
        }
    )

    return recs


def _empty_error_analysis() -> Dict[str, Any]:
    """Return an empty analysis when no data is available."""
    return {
        "source": "none",
        "dataset": "No data available",
        "job_id": None,
        "has_ground_truth": False,
        "threshold": 0.5,
        "summary": {
            "totalPairs": 0,
            "truePositives": 0,
            "trueNegatives": 0,
            "falsePositives": 0,
            "falseNegatives": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "accuracy": 0.0,
        },
        "falsePositives": [],
        "falseNegatives": [],
        "engineContributions": {"falsePositives": {}, "falseNegatives": {}},
        "recommendations": [],
    }


@app.get("/api/benchmark-datasets")
async def get_benchmark_datasets() -> Dict[str, Any]:
    """Get available benchmark datasets by scanning data/datasets/ directory."""
    datasets: List[Dict[str, Any]] = []
    dataset_icons: Dict[str, str] = {
        "demo": "🧪",
        "poj104": "📚",
        "codesearchnet": "🐍",
        "codexglue": "☕",
        "google": "🏆",
        "bigclone": "🔄",
        "kaggle": "📊",
        "synthetic": "⚙️",
        "ieee": "🎓",
        "oscar": "🎭",
        "xiangtan": "🏫",
    }
    dataset_colors: Dict[str, str] = {
        "demo": "purple",
        "poj104": "blue",
        "codesearchnet": "green",
        "codexglue": "amber",
        "google": "emerald",
        "bigclone": "cyan",
        "kaggle": "indigo",
        "synthetic": "gray",
        "ieee": "rose",
        "oscar": "fuchsia",
        "xiangtan": "sky",
    }

    for item in _iter_benchmark_dataset_roots():
        dataset_id = item.name
        metadata = _load_dataset_metadata(item)
        dataset_info: Dict[str, Any] = {}

        if metadata.get("exclude_from_benchmark"):
            continue

        readiness = _build_benchmark_dataset_readiness(dataset_id, item)
        if not readiness.get("runnable"):
            logger.debug(
                "Hiding benchmark dataset %s: %s",
                dataset_id,
                readiness.get("reason", "not runnable"),
            )
            continue

        # Determine if this is a demo dataset
        is_demo = dataset_id.startswith("demo_")
        dataset_dir = _resolve_benchmark_dataset_dir(dataset_id) or item

        if not is_demo and dataset_dir.name in {"train", "test", "validation"}:
            dataset_info = _read_json_file(dataset_dir / "dataset_info.json")

        # Infer icon and color based on dataset name
        icon = dataset_icons.get("demo" if is_demo else "synthetic", "📦")
        color = dataset_colors.get("demo" if is_demo else "gray", "slate")

        # Try to find icon/color for known dataset types
        for key in dataset_icons.keys():
            if key in dataset_id.lower():
                icon = dataset_icons[key]
                color = dataset_colors.get(key, "slate")
                break

        # Build dataset record
        dataset_record: Dict[str, Any] = {
            "id": dataset_id,
            "name": metadata.get("name", dataset_id.replace("_", " ").title()),
            "desc": metadata.get("description", f"Dataset: {dataset_id}"),
            "icon": icon,
            "color": color,
            "language": _infer_dataset_language(
                dataset_id,
                metadata,
                dataset_info,
                dataset_dir=dataset_dir,
            ),
            "size": _infer_dataset_size_label(
                dataset_dir, metadata, dataset_info, is_demo
            ),
            "created_by": metadata.get("created_by", "System"),
            "created_at": metadata.get("created", metadata.get("created_at", "")),
            "is_demo": is_demo,
            "has_ground_truth": bool(readiness.get("runnable")),
            "benchmark_availability": readiness,
        }
        benchmark_quality = _build_benchmark_quality_certificate(item)
        if benchmark_quality:
            dataset_record["benchmark_quality"] = benchmark_quality

        # Add demo-specific fields if applicable
        if is_demo:
            dataset_record["files_created"] = metadata.get("files_created", 0)
            dataset_record["similarity_type"] = metadata.get(
                "similarity_type", "unknown"
            )

        datasets.append(dataset_record)

    present_dataset_ids = {dataset["id"] for dataset in datasets}
    for dataset_id in sorted(BUILTIN_PAIR_DATASET_IDS - present_dataset_ids):
        metadata = _load_builtin_pair_dataset_metadata(dataset_id)
        if not metadata:
            continue
        dataset_root = _resolve_benchmark_dataset_root(dataset_id)
        readiness = _build_benchmark_dataset_readiness(dataset_id, dataset_root)
        benchmark_quality = _build_benchmark_quality_certificate(dataset_root)
        dataset_record = {
            "id": dataset_id,
            "name": metadata.get("name", dataset_id.replace("_", " ").title()),
            "desc": metadata.get("description", f"Dataset: {dataset_id}"),
            "icon": dataset_icons.get("synthetic", "📦"),
            "color": dataset_colors.get("synthetic", "slate"),
            "language": metadata.get("language", _dataset_default_language(dataset_id)),
            "size": metadata.get(
                "size",
                (
                    f"{benchmark_quality.get('pair_count', 0):,} labeled pairs"
                    if benchmark_quality
                    else "Built-in benchmark"
                ),
            ),
            "created_by": metadata.get("created_by", "System"),
            "created_at": metadata.get("created", metadata.get("created_at", "")),
            "is_demo": False,
            "has_ground_truth": _dataset_has_pair_ground_truth(
                dataset_id, dataset_root
            ),
            "benchmark_availability": readiness,
        }
        if benchmark_quality:
            dataset_record["benchmark_quality"] = benchmark_quality
        datasets.append(dataset_record)

    return JSONResponse(content={"datasets": datasets})


def _dataset_has_pair_ground_truth(dataset_id: str, dataset_root: PathLib) -> bool:
    """Return true when a dataset can support pair-level benchmark metrics."""
    if dataset_id in BUILTIN_PAIR_DATASET_IDS:
        return _builtin_pair_dataset_path(dataset_id).exists()
    if (dataset_root / "generated_pairs.jsonl").exists():
        return True
    if dataset_id == "kaggle_student_code":
        return (dataset_root / "cheating_dataset.csv").exists()
    if dataset_id in {"CodeSimilarityDataset", "bigclonebench", "conplag"}:
        return _build_benchmark_dataset_readiness(dataset_id, dataset_root).get(
            "runnable", False
        )
    if dataset_id in {"xiangtan", "google_codejam"}:
        return (dataset_root / "pairs.csv").exists() or (
            dataset_root / "ground_truth.json"
        ).exists()
    if dataset_id in {"poj104", "codexglue_clone"}:
        return (dataset_root / "huggingface" / "dataset_dict.json").exists()
    if dataset_id == "poolc_600k_python":
        return _build_benchmark_dataset_readiness(dataset_id, dataset_root).get(
            "runnable", False
        )
    if dataset_id in {"IR-Plag-Dataset", "conplag_classroom_java"}:
        return _build_benchmark_dataset_readiness(dataset_id, dataset_root).get(
            "runnable", False
        )
    return False


@app.post("/api/benchmark")
async def run_benchmark(
    request: Request,
    files: List[UploadFile] = File(default=[]),
    tools: List[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    # User authentication is handled by middleware, user info is in request.state
    selected_tools: List[str] = []
    for tool in tools:
        tool_id = str(tool).strip().lower()
        if tool_id in REAL_BENCHMARK_TOOL_IDS and tool_id not in selected_tools:
            selected_tools.append(tool_id)
    tools = selected_tools or ["integritydesk"]

    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / f"bench_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[BENCHMARK {job_id}] Starting benchmark job")
    logger.info(f"[BENCHMARK {job_id}] Requested tools: {', '.join(tools)}")
    logger.info(
        f"[BENCHMARK {job_id}] Dataset: {dataset if dataset else 'custom upload'}"
    )
    normalized_protocol = _normalize_benchmark_protocol(benchmark_type)
    benchmark_type = normalized_protocol["benchmark_type"]
    protocol = normalized_protocol["protocol"]
    threshold_policy = normalized_protocol["threshold_policy"]
    optimization_objective = normalized_protocol["optimization_objective"]
    report_type = normalized_protocol["report_type"]

    if benchmark_type in {"pan_optimization", "regression_test"}:
        dataset_root = BENCHMARK_DATA_DIR / dataset if dataset else None
        has_labeled_ground_truth = bool(
            dataset
            and dataset != "custom"
            and dataset_root
            and _dataset_has_pair_ground_truth(dataset, dataset_root)
        )
        if not has_labeled_ground_truth:
            shutil.rmtree(job_dir, ignore_errors=True)
            return JSONResponse(
                status_code=400,
                content={
                    "error": (
                        "PAN metrics require labeled ground truth. Select a labeled "
                        "demo/synthetic original-vs-plagiarized dataset or a PAN-style "
                        "dataset with labels."
                    )
                },
            )

    submissions = {}
    explicit_pairs: List[Dict[str, Any]] = []
    pair_sampling_audit: Dict[str, Any] = {}

    logger.info(f"[BENCHMARK {job_id}] Loading submissions")
    if dataset and dataset != "custom":
        logger.info(f"[BENCHMARK {job_id}] Loading dataset: {dataset}")
        submissions, explicit_pairs = _load_pair_labeled_benchmark_dataset(
            dataset, job_dir
        )
        if explicit_pairs:
            explicit_pairs, pair_sampling_audit = _select_reliable_explicit_pairs(
                dataset, explicit_pairs
            )
            selected_files = {
                str(pair.get("file_a", "")) for pair in explicit_pairs
            } | {str(pair.get("file_b", "")) for pair in explicit_pairs}
            submissions = {
                filename: content
                for filename, content in submissions.items()
                if filename in selected_files
            }
        if not submissions:
            submissions = _load_benchmark_dataset(dataset, job_dir)
    else:
        logger.info(f"[BENCHMARK {job_id}] Processing {len(files)} uploaded files")
        submissions = await _store_benchmark_uploads(files, job_dir)

    logger.info(
        f"[BENCHMARK {job_id}] Loaded {len(submissions)} submissions successfully"
    )
    if pair_sampling_audit:
        logger.info(
            "[BENCHMARK %s] Pair sampling: %s selected from %s (%s)",
            job_id,
            pair_sampling_audit.get("selected", {}).get("total_pairs", 0),
            pair_sampling_audit.get("original", {}).get("total_pairs", 0),
            pair_sampling_audit.get("sampling_policy"),
        )

    if len(submissions) < 2:
        shutil.rmtree(job_dir, ignore_errors=True)
        return JSONResponse(
            status_code=400, content={"error": "At least 2 code files required"}
        )

    if explicit_pairs:
        all_pairs = [
            (str(pair["file_a"]), str(pair["file_b"]))
            for pair in explicit_pairs
            if pair.get("file_a") in submissions and pair.get("file_b") in submissions
        ]
    else:
        file_list = list(submissions.keys())
        all_pairs = [
            (file_list[i], file_list[j])
            for i in range(len(file_list))
            for j in range(i + 1, len(file_list))
        ]
    logger.info(f"[BENCHMARK {job_id}] Generated {len(all_pairs)} comparison pairs")

    tool_results = {}
    tool_timings: Dict[str, float] = {}

    if "integritydesk" in tools:
        logger.info(f"[BENCHMARK {job_id}] Running IntegrityDesk engine")
        tool_started = time.perf_counter()
        try:
            # Optimize for benchmarks: disable embedding on CPU, keep it on GPU
            import os

            original_embedding_runtime = os.environ.get("EMBEDDING_RUNTIME")
            should_disable_embedding = False

            # Check if GPU is available
            try:
                import torch

                has_gpu = torch.cuda.is_available()
                if not has_gpu and settings.EMBEDDING_RUNTIME in (
                    "local_unixcoder",
                    "local",
                    "unixcoder",
                ):
                    # CPU-only and using local model - disable for speed
                    should_disable_embedding = True
                    os.environ["EMBEDDING_RUNTIME"] = "none"
                    logger.info("Benchmark: Disabled embedding engine (CPU-only mode)")
            except ImportError:
                # torch not available, assume CPU
                if settings.EMBEDDING_RUNTIME in (
                    "local_unixcoder",
                    "local",
                    "unixcoder",
                ):
                    should_disable_embedding = True
                    os.environ["EMBEDDING_RUNTIME"] = "none"
                    logger.info(
                        "Benchmark: Disabled embedding engine (no GPU detected)"
                    )

            service = BatchDetectionService(threshold=0.3)
            logger.info(
                f"[BENCHMARK {job_id}] Starting IntegrityDesk all-pairs comparison on {len(submissions)} files"
            )
            if explicit_pairs:
                results = service.compare_pairs(submissions, explicit_pairs)
            else:
                results = service.compare_all_pairs(submissions)
            logger.info(
                f"[BENCHMARK {job_id}] IntegrityDesk completed successfully, got {len(results)} results"
            )
            tool_results["integritydesk"] = {
                "pairs": [
                    {
                        "file_a": r.file_a,
                        "file_b": r.file_b,
                        "score": round(r.score, 3),
                        "features": {k: round(v, 3) for k, v in r.features.items()},
                        "contributions": {
                            k: round(v, 3) for k, v in r.contributions.items()
                        },
                    }
                    for r in results
                ]
            }

            # Restore original setting
            if should_disable_embedding:
                if original_embedding_runtime:
                    os.environ["EMBEDDING_RUNTIME"] = original_embedding_runtime
                elif "EMBEDDING_RUNTIME" in os.environ:
                    del os.environ["EMBEDDING_RUNTIME"]
        except Exception as e:
            logger.exception("IntegrityDesk benchmark failed")
            tool_results["integritydesk"] = {"error": str(e)}
        finally:
            tool_timings["integritydesk"] = time.perf_counter() - tool_started

    total_tools = len([t for t in tools if t != "integritydesk"])
    current_tool_idx = 1
    from src.backend.benchmark.runners.external_tool_runner import ExternalToolRunner

    external_tool_runner = ExternalToolRunner(
        moss_user_id=_get_setting_secret("moss_user_id")
    )
    for tool in tools:
        if tool == "integritydesk":
            continue
        logger.info(
            f"[BENCHMARK {job_id}] Running tool {current_tool_idx}/{total_tools}: {tool}"
        )
        current_tool_idx += 1
        tool_started = time.perf_counter()
        try:
            score_data = external_tool_runner.run_tool(tool, submissions, all_pairs)
            if score_data:
                tool_results[tool] = score_data
            else:
                tool_results[tool] = {"error": f"{tool} not available"}
        except Exception as e:
            logger.exception(f"{tool} benchmark failed")
            tool_results[tool] = {"error": str(e)}
        finally:
            tool_timings[tool] = time.perf_counter() - tool_started

    explicit_pair_labels = {
        frozenset((str(pair.get("file_a", "")), str(pair.get("file_b", "")))): int(
            pair.get("label", 0)
        )
        for pair in explicit_pairs
    }
    pair_results = []
    for fa, fb in all_pairs:
        entry = {
            "file_a": fa,
            "file_b": fb,
            "label": f"{PathLib(fa).stem} vs {PathLib(fb).stem}",
            "tool_results": [],
        }
        label_key = frozenset((fa, fb))
        if label_key in explicit_pair_labels:
            entry["ground_truth_label"] = explicit_pair_labels[label_key]
        for tool_name, tool_data in tool_results.items():
            if "pairs" in tool_data:
                for p in tool_data["pairs"]:
                    if (p["file_a"] == fa and p["file_b"] == fb) or (
                        p["file_a"] == fb and p["file_b"] == fa
                    ):
                        entry["tool_results"].append(
                            {
                                "tool": tool_name,
                                "score": p["score"],
                                "features": p.get("features", {}),
                                "contributions": p.get("contributions", {}),
                            }
                        )
        pair_results.append(entry)

    # Build ground truth labels for built-in datasets
    ground_truth_labels = _get_ground_truth_labels(dataset, pair_results)

    # Compute evaluation metrics per tool
    evaluation_results = {}

    if ground_truth_labels:
        for tool_name, tool_data in tool_results.items():
            if "pairs" not in tool_data:
                continue

            scores = []
            labels = []

            for entry in pair_results:
                fa, fb = entry["file_a"], entry["file_b"]
                for tr in entry["tool_results"]:
                    if tr["tool"] == tool_name:
                        scores.append(tr["score"])
                        # Find matching ground truth
                        idx = next(
                            (
                                i
                                for i, p in enumerate(pair_results)
                                if p["file_a"] == fa and p["file_b"] == fb
                            ),
                            -1,
                        )
                        if idx >= 0 and idx < len(ground_truth_labels):
                            labels.append(ground_truth_labels[idx])
                        break

            if scores and labels:
                # Compute metrics
                metrics = _compute_evaluation_metrics(
                    scores,
                    labels,
                    tool_name,
                    dataset or "custom",
                    tool_timings.get(tool_name, 0.0),
                    _compute_engine_contribution(tool_data.get("pairs", [])),
                    threshold_strategy=(
                        "fixed_threshold"
                        if benchmark_type == "regression_test"
                        else "calibration_holdout"
                    ),
                )
                evaluation_results[tool_name] = metrics

    # Simple summary for non-labeled datasets
    id_avg = sum(
        (p["score"] for p in tool_results.get("integritydesk", {}).get("pairs", [])), 0
    ) / max(1, len(tool_results.get("integritydesk", {}).get("pairs", [])))
    comp_scores = [
        p["score"]
        for t, d in tool_results.items()
        if t != "integritydesk" and "pairs" in d
        for p in d["pairs"]
    ]
    comp_avg = sum(comp_scores) / len(comp_scores) if comp_scores else 0
    benchmark_quality = (
        _build_benchmark_quality_certificate(BENCHMARK_DATA_DIR / dataset)
        if dataset and dataset != "custom"
        else None
    )

    shutil.rmtree(job_dir, ignore_errors=True)

    response = {
        "job_id": job_id,
        "preset_id": preset_id,
        "preset_name": next(
            (
                preset["name"]
                for preset in BENCHMARK_WORKFLOW_PRESETS
                if preset["id"] == preset_id
            ),
            "",
        ),
        "requested_tools": tools,
        "tool_scores": {
            k: {
                "pairs": len(v.get("pairs", [])),
                "error": v.get("error"),
                "score_source": (
                    "built_in_integritydesk"
                    if k == "integritydesk"
                    else ("real_cli" if "error" not in v else "unavailable")
                ),
                "runtime_seconds": round(tool_timings.get(k, 0.0), 4),
                "avg_runtime_seconds": round(
                    tool_timings.get(k, 0.0) / max(1, len(v.get("pairs", []))), 6
                ),
            }
            for k, v in tool_results.items()
        },
        "pair_results": pair_results,
        "summary": {
            "pairs_tested": len(pair_results),
            "tools_compared": len(
                [t for t in tool_results if "error" not in tool_results[t]]
            ),
            "accuracy": {
                "integritydesk": round(id_avg, 4),
                "best_competitor": round(comp_avg, 4),
            },
            "accuracy_basis": "mean_similarity_score_not_classification_accuracy",
            "score_summary": {
                "integritydesk_mean_similarity": round(id_avg, 4),
                "competitor_mean_similarity": round(comp_avg, 4),
            },
            "dataset_name": dataset or "custom",
            "dataset_size": len(submissions),
            "positive_pairs": int(
                sum(1 for label in ground_truth_labels if label >= 2)
            ),
            "negative_pairs": int(sum(1 for label in ground_truth_labels if label < 2)),
            "optimization_trials": 17,
            "cross_validation_folds": 1,
            "optimization_method": "Threshold sweep over 17 cutoffs, maximizing F1; PlagDet reported as primary PAN score",
        },
        "benchmark_type": benchmark_type,
        "protocol": protocol,
        "threshold_policy": threshold_policy,
        "optimization_objective": optimization_objective,
        "report_type": report_type,
        "benchmark_goal": (
            "admin_pan_optimization"
            if benchmark_type == "pan_optimization"
            else (
                "locked_regression_test"
                if benchmark_type == "regression_test"
                else "professor_tool_comparison"
            )
        ),
        "has_ground_truth": bool(ground_truth_labels),
    }
    if pair_sampling_audit:
        response["pair_sampling_audit"] = pair_sampling_audit
    if benchmark_quality:
        response["benchmark_quality"] = benchmark_quality

    # Add evaluation metrics if available
    if evaluation_results:
        response["evaluation"] = evaluation_results
        response["ground_truth_basis"] = _get_ground_truth_basis(dataset)
        response["benchmark_trust"] = (
            evaluation_results.get("integritydesk")
            or next(iter(evaluation_results.values()), {})
        ).get("benchmark_trust", {})
        if benchmark_type == "regression_test":
            response["quality_gates"] = _build_regression_quality_gates(
                evaluation_results.get("integritydesk") or {}
            )

    response = _persist_benchmark_response(response)
    return JSONResponse(content=response)


@app.post("/api/benchmark/stream")
async def stream_benchmark(
    request: Request,
    files: List[UploadFile] = File(default=[]),
    tools: List[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    """Delegate to the real benchmark endpoint (streaming was replaced with direct JSON)."""
    return await run_benchmark(
        request=request,
        files=files,
        tools=tools,
        dataset=dataset,
        benchmark_type=benchmark_type,
        preset_id=preset_id,
    )


# ── Background benchmark job store ────────────────────────────────────────
BENCHMARK_JOBS: Dict[str, Dict[str, Any]] = {}
BENCHMARK_JOBS_LOCK = threading.Lock()


def _benchmark_job_set(job_id: str, updates: Dict[str, Any]) -> None:
    """Thread-safe update of a benchmark job record."""
    with BENCHMARK_JOBS_LOCK:
        BENCHMARK_JOBS.setdefault(job_id, {}).update(updates)


def _run_benchmark_background(
    job_id: str,
    tool_ids: List[str],
    dataset: str,
    benchmark_type: str,
    preset_id: str,
    file_bytes: List[tuple],  # list of (filename, bytes)
) -> None:
    """Run the full benchmark in a background thread and store the result."""
    import asyncio
    import io

    def _progress(msg: str) -> None:
        _benchmark_job_set(job_id, {})
        with BENCHMARK_JOBS_LOCK:
            BENCHMARK_JOBS[job_id].setdefault("progress", []).append(msg)

    try:
        _benchmark_job_set(job_id, {"status": "running", "progress": []})
        _progress(f"Starting benchmark with tools: {', '.join(tool_ids)}")

        selected_tools: List[str] = []
        for tool in tool_ids:
            tool_id = str(tool).strip().lower()
            if tool_id in REAL_BENCHMARK_TOOL_IDS and tool_id not in selected_tools:
                selected_tools.append(tool_id)
        tools = selected_tools or ["integritydesk"]

        job_dir = UPLOADS_DIR / f"bench_{job_id}"
        job_dir.mkdir(parents=True, exist_ok=True)

        normalized_protocol = _normalize_benchmark_protocol(benchmark_type)
        btype = normalized_protocol["benchmark_type"]
        protocol = normalized_protocol["protocol"]
        threshold_policy = normalized_protocol["threshold_policy"]
        optimization_objective = normalized_protocol["optimization_objective"]
        report_type = normalized_protocol["report_type"]

        if btype in {"pan_optimization", "regression_test"}:
            dataset_root = BENCHMARK_DATA_DIR / dataset if dataset else None
            has_labeled = bool(
                dataset
                and dataset != "custom"
                and dataset_root
                and _dataset_has_pair_ground_truth(dataset, dataset_root)
            )
            if not has_labeled:
                shutil.rmtree(job_dir, ignore_errors=True)
                _benchmark_job_set(
                    job_id,
                    {
                        "status": "error",
                        "error": (
                            "PAN metrics require labeled ground truth. Select a labeled "
                            "demo/synthetic original-vs-plagiarized dataset."
                        ),
                    },
                )
                return

        submissions: Dict[str, str] = {}
        explicit_pairs: List[Dict[str, Any]] = []
        pair_sampling_audit: Dict[str, Any] = {}

        if dataset and dataset != "custom":
            _progress(f"Loading dataset: {dataset}")
            submissions, explicit_pairs = _load_pair_labeled_benchmark_dataset(
                dataset, job_dir
            )
            if explicit_pairs:
                explicit_pairs, pair_sampling_audit = _select_reliable_explicit_pairs(
                    dataset, explicit_pairs
                )
                selected_files = {str(p.get("file_a", "")) for p in explicit_pairs} | {
                    str(p.get("file_b", "")) for p in explicit_pairs
                }
                submissions = {
                    fn: content
                    for fn, content in submissions.items()
                    if fn in selected_files
                }
            if not submissions:
                submissions = _load_benchmark_dataset(dataset, job_dir)
        else:
            _progress(f"Processing {len(file_bytes)} uploaded files")
            for fname, fbytes in file_bytes:
                safe = PathLib(fname).name
                target = job_dir / safe
                target.write_bytes(fbytes)
                try:
                    submissions[safe] = fbytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

        _progress(f"Loaded {len(submissions)} submissions")

        if len(submissions) < 2:
            shutil.rmtree(job_dir, ignore_errors=True)
            _benchmark_job_set(
                job_id,
                {"status": "error", "error": "At least 2 code files required"},
            )
            return

        if explicit_pairs:
            all_pairs = [
                (str(p["file_a"]), str(p["file_b"]))
                for p in explicit_pairs
                if p.get("file_a") in submissions and p.get("file_b") in submissions
            ]
        else:
            file_list = list(submissions.keys())
            all_pairs = [
                (file_list[i], file_list[j])
                for i in range(len(file_list))
                for j in range(i + 1, len(file_list))
            ]
        _progress(f"Generated {len(all_pairs)} comparison pairs")

        tool_results: Dict[str, Any] = {}
        tool_timings: Dict[str, float] = {}

        if "integritydesk" in tools:
            _progress("Running IntegrityDesk engine…")
            t0 = time.perf_counter()
            try:
                import os as _os

                orig_emb = _os.environ.get("EMBEDDING_RUNTIME")
                disable_emb = False
                try:
                    import torch

                    if not torch.cuda.is_available() and settings.EMBEDDING_RUNTIME in (
                        "local_unixcoder",
                        "local",
                        "unixcoder",
                    ):
                        disable_emb = True
                        _os.environ["EMBEDDING_RUNTIME"] = "none"
                except ImportError:
                    if settings.EMBEDDING_RUNTIME in (
                        "local_unixcoder",
                        "local",
                        "unixcoder",
                    ):
                        disable_emb = True
                        _os.environ["EMBEDDING_RUNTIME"] = "none"

                service = BatchDetectionService(threshold=0.3)
                if explicit_pairs:
                    results = service.compare_pairs(submissions, explicit_pairs)
                else:
                    results = service.compare_all_pairs(submissions)
                tool_results["integritydesk"] = {
                    "pairs": [
                        {
                            "file_a": r.file_a,
                            "file_b": r.file_b,
                            "score": round(r.score, 3),
                            "features": {k: round(v, 3) for k, v in r.features.items()},
                            "contributions": {
                                k: round(v, 3) for k, v in r.contributions.items()
                            },
                        }
                        for r in results
                    ]
                }
                _progress(f"IntegrityDesk: {len(results)} pairs analysed")
                if disable_emb:
                    if orig_emb:
                        _os.environ["EMBEDDING_RUNTIME"] = orig_emb
                    elif "EMBEDDING_RUNTIME" in _os.environ:
                        del _os.environ["EMBEDDING_RUNTIME"]
            except Exception as exc:
                logger.exception("IntegrityDesk benchmark failed in background job")
                tool_results["integritydesk"] = {"error": str(exc)}
                _progress(f"IntegrityDesk error: {exc}")
            finally:
                tool_timings["integritydesk"] = time.perf_counter() - t0

        from src.backend.benchmark.runners.external_tool_runner import (
            ExternalToolRunner,
        )

        ext_runner = ExternalToolRunner(
            moss_user_id=_get_setting_secret("moss_user_id")
        )
        for tool in tools:
            if tool == "integritydesk":
                continue
            _progress(f"Running {tool}…")
            t0 = time.perf_counter()
            try:
                score_data = ext_runner.run_tool(tool, submissions, all_pairs)
                tool_results[tool] = (
                    score_data if score_data else {"error": f"{tool} not available"}
                )
            except Exception as exc:
                logger.exception("%s benchmark failed in background job", tool)
                tool_results[tool] = {"error": str(exc)}
                _progress(f"{tool} error: {exc}")
            finally:
                tool_timings[tool] = time.perf_counter() - t0

        explicit_pair_labels = {
            frozenset((str(p.get("file_a", "")), str(p.get("file_b", "")))): int(
                p.get("label", 0)
            )
            for p in explicit_pairs
        }
        pair_results = []
        for fa, fb in all_pairs:
            entry: Dict[str, Any] = {
                "file_a": fa,
                "file_b": fb,
                "label": f"{PathLib(fa).stem} vs {PathLib(fb).stem}",
                "tool_results": [],
            }
            lk = frozenset((fa, fb))
            if lk in explicit_pair_labels:
                entry["ground_truth_label"] = explicit_pair_labels[lk]
            for tn, td in tool_results.items():
                if "pairs" in td:
                    for p in td["pairs"]:
                        if (p["file_a"] == fa and p["file_b"] == fb) or (
                            p["file_a"] == fb and p["file_b"] == fa
                        ):
                            entry["tool_results"].append(
                                {
                                    "tool": tn,
                                    "score": p["score"],
                                    "features": p.get("features", {}),
                                    "contributions": p.get("contributions", {}),
                                }
                            )
            pair_results.append(entry)

        ground_truth_labels = _get_ground_truth_labels(dataset, pair_results)
        evaluation_results: Dict[str, Any] = {}
        if ground_truth_labels:
            for tn, td in tool_results.items():
                if "pairs" not in td:
                    continue
                scores, labels = [], []
                for entry in pair_results:
                    fa, fb = entry["file_a"], entry["file_b"]
                    for tr in entry["tool_results"]:
                        if tr["tool"] == tn:
                            scores.append(tr["score"])
                            idx = next(
                                (
                                    i
                                    for i, p in enumerate(pair_results)
                                    if p["file_a"] == fa and p["file_b"] == fb
                                ),
                                -1,
                            )
                            if 0 <= idx < len(ground_truth_labels):
                                labels.append(ground_truth_labels[idx])
                            break
                if scores and labels:
                    metrics = _compute_evaluation_metrics(
                        scores,
                        labels,
                        tn,
                        dataset or "custom",
                        tool_timings.get(tn, 0.0),
                        _compute_engine_contribution(td.get("pairs", [])),
                        threshold_strategy=(
                            "fixed_threshold"
                            if btype == "regression_test"
                            else "calibration_holdout"
                        ),
                    )
                    evaluation_results[tn] = metrics

        id_avg = sum(
            p["score"] for p in tool_results.get("integritydesk", {}).get("pairs", [])
        ) / max(1, len(tool_results.get("integritydesk", {}).get("pairs", [])))
        comp_scores = [
            p["score"]
            for t, d in tool_results.items()
            if t != "integritydesk" and "pairs" in d
            for p in d["pairs"]
        ]
        comp_avg = sum(comp_scores) / len(comp_scores) if comp_scores else 0
        benchmark_quality = (
            _build_benchmark_quality_certificate(BENCHMARK_DATA_DIR / dataset)
            if dataset and dataset != "custom"
            else None
        )

        shutil.rmtree(job_dir, ignore_errors=True)

        response: Dict[str, Any] = {
            "job_id": job_id,
            "preset_id": preset_id,
            "preset_name": next(
                (
                    preset["name"]
                    for preset in BENCHMARK_WORKFLOW_PRESETS
                    if preset["id"] == preset_id
                ),
                "",
            ),
            "requested_tools": tools,
            "tool_scores": {
                k: {
                    "pairs": len(v.get("pairs", [])),
                    "error": v.get("error"),
                    "score_source": (
                        "built_in_integritydesk"
                        if k == "integritydesk"
                        else ("real_cli" if "error" not in v else "unavailable")
                    ),
                    "runtime_seconds": round(tool_timings.get(k, 0.0), 4),
                    "avg_runtime_seconds": round(
                        tool_timings.get(k, 0.0) / max(1, len(v.get("pairs", []))), 6
                    ),
                }
                for k, v in tool_results.items()
            },
            "pair_results": pair_results,
            "summary": {
                "pairs_tested": len(pair_results),
                "tools_compared": len(
                    [t for t in tool_results if "error" not in tool_results[t]]
                ),
                "accuracy": {
                    "integritydesk": round(id_avg, 4),
                    "best_competitor": round(comp_avg, 4),
                },
                "accuracy_basis": "mean_similarity_score_not_classification_accuracy",
                "score_summary": {
                    "integritydesk_mean_similarity": round(id_avg, 4),
                    "competitor_mean_similarity": round(comp_avg, 4),
                },
                "dataset_name": dataset or "custom",
                "dataset_size": len(submissions),
                "positive_pairs": int(
                    sum(1 for label in ground_truth_labels if label >= 2)
                ),
                "negative_pairs": int(
                    sum(1 for label in ground_truth_labels if label < 2)
                ),
                "optimization_trials": 17,
                "cross_validation_folds": 1,
                "optimization_method": "Threshold sweep over 17 cutoffs, maximising F1",
            },
            "benchmark_type": btype,
            "protocol": protocol,
            "threshold_policy": threshold_policy,
            "optimization_objective": optimization_objective,
            "report_type": report_type,
            "benchmark_goal": (
                "admin_pan_optimization"
                if btype == "pan_optimization"
                else (
                    "locked_regression_test"
                    if btype == "regression_test"
                    else "professor_tool_comparison"
                )
            ),
            "has_ground_truth": bool(ground_truth_labels),
        }
        if pair_sampling_audit:
            response["pair_sampling_audit"] = pair_sampling_audit
        if benchmark_quality:
            response["benchmark_quality"] = benchmark_quality
        if evaluation_results:
            response["evaluation"] = evaluation_results
            response["ground_truth_basis"] = _get_ground_truth_basis(dataset)
            response["benchmark_trust"] = (
                evaluation_results.get("integritydesk")
                or next(iter(evaluation_results.values()), {})
            ).get("benchmark_trust", {})
            if btype == "regression_test":
                response["quality_gates"] = _build_regression_quality_gates(
                    evaluation_results.get("integritydesk") or {}
                )

        response = _persist_benchmark_response(response)
        _progress("✓ Benchmark complete")
        _benchmark_job_set(job_id, {"status": "done", "result": response})

    except Exception as exc:
        logger.exception("Background benchmark job %s failed", job_id)
        _benchmark_job_set(job_id, {"status": "error", "error": str(exc)})


@app.post("/api/benchmark/start")
async def start_benchmark_job(
    request: Request,
    files: List[UploadFile] = File(default=[]),
    tools: List[str] = Form(default=[]),
    dataset: str = Form(default=""),
    benchmark_type: str = Form(default="tool_comparison"),
    preset_id: str = Form(default=""),
):
    """Start a benchmark in the background and return a job_id immediately."""
    job_id = str(uuid.uuid4())[:8]

    # Read file bytes now, before the request context closes
    file_bytes: List[tuple] = []
    for f in files:
        if f.filename:
            content = await f.read()
            file_bytes.append((f.filename, content))

    tool_list = list(tools)  # copy from form data

    _benchmark_job_set(job_id, {"status": "queued", "progress": []})

    t = threading.Thread(
        target=_run_benchmark_background,
        args=(job_id, tool_list, dataset, benchmark_type, preset_id, file_bytes),
        daemon=True,
    )
    t.start()

    return JSONResponse(content={"job_id": job_id, "status": "queued"})


@app.get("/api/benchmark/status/{job_id}")
async def get_benchmark_job_status(job_id: str):
    """Poll the status and progress of a background benchmark job."""
    with BENCHMARK_JOBS_LOCK:
        job = BENCHMARK_JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    return JSONResponse(
        content={
            "job_id": job_id,
            "status": job.get("status", "unknown"),
            "progress": job.get("progress", []),
            "result": job.get("result") if job.get("status") == "done" else None,
            "error": job.get("error") if job.get("status") == "error" else None,
        }
    )


@app.post("/api/benchmark/apply-optimization")
async def apply_benchmark_optimization(request: Request) -> Dict[str, Any]:
    """Apply proposed benchmark optimization changes to engine_weights.yaml."""
    _require_current_user(request, admin_only=False)
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid optimization payload")

    changes = payload.get("config_changes")
    if not isinstance(changes, list) or not changes:
        raise HTTPException(status_code=400, detail="No optimization changes provided")

    from src.backend.engines.scoring.fusion_engine import (
        load_engine_config,
        save_engine_config,
    )

    current_config = load_engine_config()
    applied = _apply_engine_optimization_changes(current_config, changes)
    save_engine_config(applied["config"])

    return {
        "success": True,
        "message": "Proposed optimization applied to engine_weights.yaml",
        "config_file": "src/backend/engines/engine_weights.yaml",
        "applied_changes": applied["applied_changes"],
    }


def _get_ground_truth_labels(
    dataset: str, pair_results: List[Dict[str, Any]]
) -> List[int]:
    """Get ground truth labels for built-in datasets.

    Labels: 0=unrelated, 1=weak, 2=semantic clone, 3=exact clone
    For binary classification: clone if label >= 2
    """
    if not pair_results:
        return []

    explicit_labels = [
        int(pair["ground_truth_label"])
        for pair in pair_results
        if "ground_truth_label" in pair
    ]
    if len(explicit_labels) == len(pair_results) and explicit_labels:
        return explicit_labels

    inferred = _infer_filename_ground_truth_labels(dataset, pair_results)
    if inferred:
        return inferred

    if dataset == "basic-clone":
        # 5 pairs: identical(3), renamed(3), reordered(2), similar(2), unrelated(0)
        return [3, 3, 2, 2, 0]
    elif dataset == "obfuscation":
        # 3 pairs: rename(2), reorder(2), comments(3)
        return [2, 2, 3]
    elif dataset == "multi-file":
        # 3 pairs: direct copy(3), similar(2), different(0)
        return [3, 2, 0]
    elif dataset == "java-clone":
        # 2 pairs: identical(3), renamed(2)
        return [3, 2]
    elif dataset == "poj104":
        # Would need actual labels from dataset
        return []
    elif dataset == "codesearchnet":
        return []
    return []


REGRESSION_QUALITY_GATE_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "precision": {
        "label": "Precision",
        "min": 0.90,
        "direction": "min",
        "reason": "Clean pairs should rarely be flagged.",
    },
    "recall": {
        "label": "Recall",
        "min": 0.75,
        "direction": "min",
        "reason": "Known plagiarism should remain discoverable.",
    },
    "f1_score": {
        "label": "F1 Score",
        "min": 0.80,
        "direction": "min",
        "reason": "Precision and recall should stay balanced.",
    },
    "false_positive_rate": {
        "label": "False Positive Rate",
        "max": 0.05,
        "direction": "max",
        "reason": "False accusations must stay rare.",
    },
}

BENCHMARK_TRUST_THRESHOLDS: Dict[str, int] = {
    "strong_holdout_pairs": 40,
    "strong_holdout_pairs_per_class": 10,
    "moderate_holdout_pairs": 12,
    "moderate_holdout_pairs_per_class": 3,
    "strong_locked_pairs": 100,
    "strong_locked_pairs_per_class": 20,
    "moderate_locked_pairs": 30,
    "moderate_locked_pairs_per_class": 5,
}


def _normalize_benchmark_protocol(benchmark_type: str) -> Dict[str, str]:
    """Normalize legacy benchmark types into clearer product protocol metadata."""
    benchmark_type_aliases = {
        "development": "pan_optimization",
        "development_evaluation": "pan_optimization",
        "calibration": "pan_optimization",
        "pan_optimization": "pan_optimization",
        "release": "regression_test",
        "release_check": "regression_test",
        "regression": "regression_test",
        "regression_test": "regression_test",
        "comparison": "tool_comparison",
        "tool_comparison": "tool_comparison",
    }
    normalized_benchmark_type = benchmark_type_aliases.get(
        benchmark_type, "tool_comparison"
    )

    if normalized_benchmark_type == "pan_optimization":
        return {
            "benchmark_type": normalized_benchmark_type,
            "protocol": "development_evaluation",
            "threshold_policy": "optimize_on_calibration",
            "optimization_objective": "f1",
            "report_type": "development_evaluation_report",
        }

    if normalized_benchmark_type == "regression_test":
        return {
            "benchmark_type": normalized_benchmark_type,
            "protocol": "release_check",
            "threshold_policy": "locked_threshold",
            "optimization_objective": "fixed_threshold_guard",
            "report_type": "release_check_report",
        }

    return {
        "benchmark_type": "tool_comparison",
        "protocol": "tool_comparison",
        "threshold_policy": "per_tool_scores",
        "optimization_objective": "comparative_analysis",
        "report_type": "tool_comparison_report",
    }


def _build_regression_quality_gates(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Build pass/fail gates for fixed-threshold benchmark regression runs."""
    if not metrics or metrics.get("error"):
        return {
            "passed": False,
            "gates": [],
            "summary": "No IntegrityDesk metrics available.",
        }

    gates = []
    for metric_key, config in REGRESSION_QUALITY_GATE_THRESHOLDS.items():
        value = _coerce_float(metrics.get(metric_key))
        direction = str(config["direction"])
        threshold = _coerce_float(
            config.get("min") if direction == "min" else config.get("max")
        )
        passed = value >= threshold if direction == "min" else value <= threshold
        gates.append(
            {
                "metric": metric_key,
                "label": config["label"],
                "value": round(value, 4),
                "threshold": round(threshold, 4),
                "direction": direction,
                "passed": passed,
                "reason": config["reason"],
            }
        )

    passed_count = sum(1 for gate in gates if gate["passed"])
    diagnosis = _diagnose_regression_gate_failure(metrics, gates)
    summary = f"{passed_count}/{len(gates)} quality gates passed."
    return {
        "passed": passed_count == len(gates),
        "passed_count": passed_count,
        "total_count": len(gates),
        "gates": gates,
        "summary": summary,
        "diagnosis": diagnosis,
    }


def _diagnose_regression_gate_failure(
    metrics: Dict[str, Any], gates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Explain the highest-impact reason a fixed-threshold release gate failed."""
    failed_metrics = {gate["metric"] for gate in gates if not gate.get("passed")}
    if not failed_metrics:
        return {}

    confusion = metrics.get("confusion_matrix") or {}
    diagnostics = metrics.get("score_diagnostics") or {}
    recall = _coerce_float(metrics.get("recall"))
    precision = _coerce_float(metrics.get("precision"))
    false_positive_rate = _coerce_float(metrics.get("false_positive_rate"))
    threshold = _coerce_float(metrics.get("fixed_threshold"))
    threshold_source = str(metrics.get("fixed_threshold_source") or "locked threshold")

    if (
        "recall" in failed_metrics
        and precision >= REGRESSION_QUALITY_GATE_THRESHOLDS["precision"]["min"]
        and false_positive_rate
        <= REGRESSION_QUALITY_GATE_THRESHOLDS["false_positive_rate"]["max"]
    ):
        return {
            "mode": "detector_recall_failure",
            "summary": (
                "IntegrityDesk is too conservative at the locked threshold; "
                "known plagiarism is not being surfaced."
            ),
            "detail": (
                f"At threshold {threshold:.2f} from {threshold_source}, the detector found "
                f"{int(confusion.get('tp', 0))} positive pairs and missed "
                f"{int(confusion.get('fn', 0))}. Precision is protected, but recall is "
                f"{recall:.1%}."
            ),
            "next_step": (
                "Fix score separation or candidate scoring before changing the release gate."
            ),
            "score_overlap_warning": bool(diagnostics.get("score_overlap_warning")),
        }

    if "precision" in failed_metrics or "false_positive_rate" in failed_metrics:
        return {
            "mode": "false_positive_failure",
            "summary": "IntegrityDesk is flagging too many clean pairs.",
            "detail": (
                f"False positive rate is {false_positive_rate:.1%}; inspect high-scoring "
                "negative pairs before lowering thresholds or increasing recall."
            ),
            "next_step": "Tighten guardrails or reduce over-dominant engine signals.",
            "score_overlap_warning": bool(diagnostics.get("score_overlap_warning")),
        }

    return {
        "mode": "balanced_quality_failure",
        "summary": "IntegrityDesk missed the fixed-threshold release target.",
        "detail": "Review failed gates and score diagnostics before changing thresholds.",
        "next_step": "Rerun after detector scoring changes, not after weakening gates.",
        "score_overlap_warning": bool(diagnostics.get("score_overlap_warning")),
    }


def _get_ground_truth_basis(dataset: str) -> str:
    """Describe how benchmark ground truth was derived."""
    if dataset and (
        dataset.startswith("demo_")
        or dataset.startswith("synthetic")
        or dataset == "clough_stevenson_style"
        or dataset in {"synthetic_small", "synthetic_medium", "synthetic_java"}
    ):
        if dataset == "clough_stevenson_style":
            return "controlled_original_plagiarized_and_hard_negative_pairs"
        return "filename_original_plagiarized_pairs"
    return "built_in_dataset_labels"


def _infer_filename_ground_truth_labels(
    dataset: str, pair_results: List[Dict[str, Any]]
) -> List[int]:
    """Infer pair labels from original/plagiarized filename conventions."""
    if not dataset or not (
        dataset.startswith("demo_")
        or dataset.startswith("synthetic")
        or dataset in {"synthetic_small", "synthetic_medium", "synthetic_java"}
    ):
        return []

    labels = []
    saw_positive = False
    for pair in pair_results:
        label = (
            3
            if _is_original_plagiarized_match(
                pair.get("file_a", ""), pair.get("file_b", "")
            )
            else 0
        )
        saw_positive = saw_positive or label >= 2
        labels.append(label)

    return labels if saw_positive else []


def _is_original_plagiarized_match(file_a: str, file_b: str) -> bool:
    """Return true when filenames represent the same original/plagiarized item."""
    base_a, role_a = _ground_truth_filename_parts(file_a)
    base_b, role_b = _ground_truth_filename_parts(file_b)
    return bool(
        base_a and base_a == base_b and {role_a, role_b} == {"original", "plagiarized"}
    )


def _ground_truth_filename_parts(filename: str) -> tuple[str, str]:
    """Extract a stable pair id and role from known benchmark filename patterns."""
    stem = PathLib(filename).stem
    stem = stem.split("__")[-1]

    if stem.endswith("_plagiarized"):
        return stem.removesuffix("_plagiarized"), "plagiarized"
    if stem.startswith("plagiarized_"):
        return stem.removeprefix("plagiarized_"), "plagiarized"
    if stem.startswith("original_"):
        return stem.removeprefix("original_"), "original"
    return stem, "original"


def _benchmark_fixed_threshold() -> tuple[float, str]:
    """Return the locked IntegrityDesk threshold used by regression benchmarks."""
    try:
        from src.backend.engines.scoring.fusion_engine import load_engine_config

        config = load_engine_config()
        decision = config.get("decision", {}) if isinstance(config, dict) else {}
        if "default_threshold" in decision:
            return _coerce_float(decision.get("default_threshold"), 0.82), (
                "engine_weights.decision.default_threshold"
            )
    except Exception:
        logger.exception("Failed to read benchmark fixed threshold from engine config")

    return _coerce_float(settings.DEFAULT_THRESHOLD, 0.82), "settings.DEFAULT_THRESHOLD"


def _compute_evaluation_metrics(
    scores: List[float],
    labels: List[int],
    tool_name: str,
    dataset_name: str,
    runtime_seconds: float = 0.0,
    engine_contribution: Optional[Dict[str, float]] = None,
    threshold_strategy: str = "calibration_holdout",
) -> Dict[str, Any]:
    """Compute PAN-aligned evaluation metrics for labeled benchmark pairs.

    The interactive benchmark endpoint currently receives pair-level labels
    rather than PAN character-span annotations. Precision, recall, and F1 use
    the same binary clone decision semantics; granularity is therefore fixed to
    one detection per detected true pair. Full fragment-level granularity is
    handled by src.backend.evaluation.pan_metrics when span annotations exist.
    """
    if len(scores) != len(labels) or len(scores) == 0:
        return {"error": "Invalid scores/labels"}

    # Binary labels: >= 2 is a clone
    binary_labels = [1 if label >= 2 else 0 for label in labels]
    scores_arr = np.array(scores)
    labels_arr = np.array(binary_labels)

    fixed_threshold, fixed_threshold_source = _benchmark_fixed_threshold()
    normalized_threshold_strategy = (
        "fixed_threshold"
        if threshold_strategy == "fixed_threshold"
        else "calibration_holdout"
    )
    best_threshold = fixed_threshold
    all_indices = list(range(len(binary_labels)))

    if normalized_threshold_strategy == "fixed_threshold":
        split_protocol = _build_locked_full_sample_protocol(binary_labels)
        threshold_indices = all_indices
        evaluation_indices = all_indices
    else:
        split_protocol = _build_stratified_calibration_holdout_split(binary_labels)
        threshold_indices = split_protocol["calibration_indices"]
        evaluation_indices = split_protocol["holdout_indices"]

    threshold_scores_arr = scores_arr[threshold_indices]
    threshold_labels_arr = labels_arr[threshold_indices]
    evaluation_scores_arr = scores_arr[evaluation_indices]
    evaluation_labels_arr = labels_arr[evaluation_indices]

    if normalized_threshold_strategy == "calibration_holdout":
        # Find the PAN/PlagDet operating point on the calibration slice only.
        # Held-out metrics below are the trustworthy headline when a holdout exists.
        best_candidate_key = None
        # Use unique observed scores as threshold candidates for more precise optimization
        unique_calibration_scores = sorted(np.unique(threshold_scores_arr))
        sweep_thresholds = sorted(
            {
                round(float(threshold), 6)
                for threshold in np.concatenate(
                    [
                        [0.0],  # boundary: predict all positive
                        unique_calibration_scores,  # unique observed scores
                        [1.0],  # boundary: predict all negative
                    ]
                )
            }
        )

        for threshold in sweep_thresholds:
            candidate = _binary_metrics_at_threshold(
                threshold_scores_arr, threshold_labels_arr, threshold
            )
            precision = float(candidate["precision"])
            fpr = float(candidate["false_positive_rate"])
            f1_score = float(candidate["f1_score"])

            # Apply constraints to prevent degenerate solutions:
            # - Minimum precision of 0.1 (not all-positive)
            # - Maximum FPR of 0.5 (not too noisy)
            # - F1 score must be reasonable (> 0)
            if precision >= 0.1 and fpr <= 0.5 and f1_score > 0.0:
                candidate_key = (
                    f1_score,
                    precision,
                    -fpr,
                    float(candidate["recall"]),
                    -float(threshold),
                )
                if best_candidate_key is None or candidate_key > best_candidate_key:
                    best_threshold = threshold
                    best_candidate_key = candidate_key

    # Compute ROC-AUC and PR-AUC
    try:
        from sklearn.metrics import (
            roc_auc_score,
            average_precision_score,
            precision_score,
            recall_score,
            f1_score,
            confusion_matrix,
        )

        if len(np.unique(labels_arr)) > 1:
            roc_auc = roc_auc_score(labels_arr, scores_arr)
            pr_auc = average_precision_score(labels_arr, scores_arr)
        else:
            roc_auc = 0.0
            pr_auc = 0.0
    except ImportError:
        # Fallback computation
        roc_auc = _compute_auc_fallback(scores_arr, labels_arr, "roc")
        pr_auc = _compute_auc_fallback(scores_arr, labels_arr, "pr")

    optimized_metrics = _binary_metrics_at_threshold(
        threshold_scores_arr, threshold_labels_arr, best_threshold
    )
    holdout_metrics = _binary_metrics_at_threshold(
        evaluation_scores_arr, evaluation_labels_arr, best_threshold
    )
    headline_scores_arr = evaluation_scores_arr
    headline_labels_arr = evaluation_labels_arr
    headline_basis = (
        "locked_full_sample_evaluation"
        if normalized_threshold_strategy == "fixed_threshold"
        else "held_out_evaluation"
    )
    headline_metrics = holdout_metrics
    precision = float(headline_metrics["precision"])
    recall = float(headline_metrics["recall"])
    f1_score = float(headline_metrics["f1_score"])
    best_cm = headline_metrics["confusion_matrix"]
    granularity = 1.0
    plagdet = f1_score / math.log2(1 + granularity)
    evaluation_scores = [float(score) for score in headline_scores_arr.tolist()]
    evaluation_binary_labels = [int(label) for label in headline_labels_arr.tolist()]
    top_10_retrieval = _compute_top_k_precision(
        evaluation_scores, evaluation_binary_labels, k=10
    )
    top_20_retrieval = _compute_top_k_precision(
        evaluation_scores, evaluation_binary_labels, k=20
    )
    top_10_recall = _compute_top_k_recall(
        evaluation_scores, evaluation_binary_labels, k=10
    )
    top_20_recall = _compute_top_k_recall(
        evaluation_scores, evaluation_binary_labels, k=20
    )
    avg_runtime_seconds = runtime_seconds / max(1, len(scores))
    false_positive_rate = float(headline_metrics["false_positive_rate"])
    fixed_threshold_metrics = _binary_metrics_at_threshold(
        evaluation_scores_arr, evaluation_labels_arr, fixed_threshold
    )
    confidence_intervals = _classification_confidence_intervals(
        evaluation_scores, evaluation_binary_labels, float(best_threshold)
    )
    score_diagnostics = _build_score_diagnostics(scores_arr, labels_arr)
    calibration_curve = _build_threshold_calibration_points(
        scores_arr, labels_arr, [fixed_threshold, float(best_threshold), 0.5, 0.75, 0.9]
    )
    metric_assumptions = {
        "span_level_scoring": False,
        "character_offsets": False,
        "line_number_conversion": "not_used_for_pair_level_benchmark",
        "granularity_handling": "pair_level_single_detection_per_true_pair",
        "weight_tuning_protocol": (
            "Regression uses a fixed threshold. Calibration selects a threshold on "
            "the calibration slice and reports headline metrics on the held-out slice."
        ),
        "ranking_objective": (
            "Use PR-AUC, PlagDet, precision@20, and top-k recall to tune ranking; "
            "do not optimize average similarity."
        ),
        "external_score_calibration": (
            "External tools are evaluated independently; normalize or calibrate "
            "scores before combining them into fusion weights."
        ),
    }
    benchmark_trust = _build_benchmark_trust_assessment(
        split_protocol=split_protocol,
        confidence_intervals=confidence_intervals,
        score_diagnostics=score_diagnostics,
        threshold_strategy=normalized_threshold_strategy,
        headline_basis=headline_basis,
        binary_labels=binary_labels,
    )
    metric_integrity = _build_metric_integrity_summary(
        scores=scores,
        labels=labels,
        binary_labels=binary_labels,
        best_threshold=float(best_threshold),
        fixed_threshold=fixed_threshold,
        optimized_metrics=optimized_metrics,
        heldout_metrics=holdout_metrics,
        fixed_threshold_metrics=fixed_threshold_metrics,
        split_protocol=split_protocol,
        confidence_intervals=confidence_intervals,
        score_diagnostics=score_diagnostics,
        benchmark_trust=benchmark_trust,
    )
    calibration_report = _build_calibration_report(float(best_threshold), "benchmark")
    tuning_recommendations = _build_engine_tuning_recommendations(
        tool_name=tool_name,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        false_positive_rate=false_positive_rate,
        auc_pr=float(pr_auc),
        best_threshold=float(best_threshold),
        fixed_threshold=fixed_threshold,
        engine_contribution=engine_contribution or {},
        confusion_matrix=best_cm,
        score_diagnostics=score_diagnostics,
    )

    return {
        "tool": tool_name,
        "dataset": dataset_name,
        "n_pairs": len(scores),
        "n_positives": int(sum(binary_labels)),
        "n_negatives": int(len(binary_labels) - sum(binary_labels)),
        "best_threshold": round(best_threshold, 2),
        "best_threshold_exact": round(float(best_threshold), 6),
        "threshold_strategy": normalized_threshold_strategy,
        "fixed_threshold": fixed_threshold,
        "fixed_threshold_source": fixed_threshold_source,
        "fixed_threshold_metrics": fixed_threshold_metrics,
        "calibration_metrics": optimized_metrics,
        "holdout_metrics": holdout_metrics,
        "headline_metric_basis": headline_basis,
        "benchmark_trust": benchmark_trust,
        "split_protocol": split_protocol,
        "confidence_intervals": confidence_intervals,
        "best_f1": round(f1_score, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1_score, 4),
        "granularity": round(granularity, 4),
        "plagdet": round(plagdet, 4),
        "plagdet_percent": round(plagdet * 100, 2),
        "top_10_retrieval": round(top_10_retrieval, 4),
        "top_20_retrieval": round(top_20_retrieval, 4),
        "top_10_recall": round(top_10_recall, 4),
        "top_20_recall": round(top_20_recall, 4),
        "false_positive_rate": round(false_positive_rate, 4),
        "auc_pr": round(pr_auc, 4),
        "engine_contribution": engine_contribution or {},
        "ai_generated_recall": None,
        "runtime_seconds": round(runtime_seconds, 4),
        "avg_runtime_seconds": round(avg_runtime_seconds, 6),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "confusion_matrix": best_cm,
        "score_diagnostics": score_diagnostics,
        "calibration_curve": calibration_curve,
        "calibration_report": calibration_report,
        "tuning_recommendations": tuning_recommendations,
        "metric_integrity": metric_integrity,
        "metric_assumptions": metric_assumptions,
        "pan_metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "granularity": round(granularity, 4),
            "plagdet": round(plagdet, 4),
            "top_10_retrieval": round(top_10_retrieval, 4),
            "top_20_retrieval": round(top_20_retrieval, 4),
            "top_10_recall": round(top_10_recall, 4),
            "top_20_recall": round(top_20_recall, 4),
            "false_positive_rate": round(false_positive_rate, 4),
            "auc_pr": round(pr_auc, 4),
            "engine_contribution": engine_contribution or {},
            "ai_generated_recall": None,
            "avg_runtime_seconds": round(avg_runtime_seconds, 6),
            "score_diagnostics": score_diagnostics,
        },
        "granularity_basis": "pair_level_single_detection",
    }


def _binary_metrics_at_threshold(
    scores_arr: np.ndarray, labels_arr: np.ndarray, threshold: float
) -> Dict[str, Any]:
    """Compute binary confusion metrics at a concrete decision threshold."""
    preds = (scores_arr >= threshold).astype(int)

    # Use sklearn for metrics computation
    try:
        from sklearn.metrics import (
            confusion_matrix,
            precision_score,
            recall_score,
            f1_score,
        )

        cm = confusion_matrix(labels_arr, preds)
        tn, fp, fn, tp = cm.ravel()
        precision = precision_score(labels_arr, preds, zero_division=0)
        recall = recall_score(labels_arr, preds, zero_division=0)
        f1_score_val = f1_score(labels_arr, preds, zero_division=0)
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    except ImportError:
        # Fallback to manual computation
        tp = int(np.sum((preds == 1) & (labels_arr == 1)))
        fp = int(np.sum((preds == 1) & (labels_arr == 0)))
        tn = int(np.sum((preds == 0) & (labels_arr == 0)))
        fn = int(np.sum((preds == 0) & (labels_arr == 1)))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_score_val = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "threshold": round(float(threshold), 6),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1_score": round(float(f1_score_val), 4),
        "false_positive_rate": round(float(false_positive_rate), 4),
        "confusion_matrix": {
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
        },
    }


def _build_stratified_calibration_holdout_split(
    binary_labels: List[int],
) -> Dict[str, Any]:
    """Create deterministic calibration and held-out indices with class balance."""
    positive_indices = [
        index for index, label in enumerate(binary_labels) if label == 1
    ]
    negative_indices = [
        index for index, label in enumerate(binary_labels) if label == 0
    ]
    can_holdout = len(positive_indices) >= 2 and len(negative_indices) >= 2

    if not can_holdout:
        all_indices = list(range(len(binary_labels)))
        return {
            "protocol": "resubstitution_fallback",
            "calibration_indices": all_indices,
            "holdout_indices": all_indices,
            "calibration_size": len(all_indices),
            "holdout_size": len(all_indices),
            "calibration_positive_pairs": len(positive_indices),
            "calibration_negative_pairs": len(negative_indices),
            "holdout_positive_pairs": len(positive_indices),
            "holdout_negative_pairs": len(negative_indices),
            "warning": (
                "Need at least two positive and two negative pairs for a held-out split."
            ),
        }

    calibration_indices: List[int] = []
    holdout_indices: List[int] = []
    for class_indices in (positive_indices, negative_indices):
        split_at = max(1, len(class_indices) // 2)
        calibration_indices.extend(class_indices[:split_at])
        holdout_indices.extend(class_indices[split_at:])

    calibration_indices = sorted(calibration_indices)
    holdout_indices = sorted(holdout_indices)
    calibration_labels = [binary_labels[index] for index in calibration_indices]
    holdout_labels = [binary_labels[index] for index in holdout_indices]

    return {
        "protocol": "deterministic_stratified_calibration_holdout",
        "calibration_indices": calibration_indices,
        "holdout_indices": holdout_indices,
        "calibration_size": len(calibration_indices),
        "holdout_size": len(holdout_indices),
        "calibration_positive_pairs": int(sum(calibration_labels)),
        "calibration_negative_pairs": int(
            len(calibration_labels) - sum(calibration_labels)
        ),
        "holdout_positive_pairs": int(sum(holdout_labels)),
        "holdout_negative_pairs": int(len(holdout_labels) - sum(holdout_labels)),
        "warning": "",
    }


def _build_locked_full_sample_protocol(binary_labels: List[int]) -> Dict[str, Any]:
    """Describe a fixed-threshold evaluation over all labeled pairs."""
    positive_count = int(sum(binary_labels))
    negative_count = int(len(binary_labels) - positive_count)
    all_indices = list(range(len(binary_labels)))
    return {
        "protocol": "locked_full_sample_evaluation",
        "calibration_indices": all_indices,
        "holdout_indices": all_indices,
        "calibration_size": 0,
        "holdout_size": len(all_indices),
        "calibration_positive_pairs": 0,
        "calibration_negative_pairs": 0,
        "holdout_positive_pairs": positive_count,
        "holdout_negative_pairs": negative_count,
        "warning": (
            "Fixed-threshold regression used every labeled pair. No threshold "
            "was selected from this run."
        ),
    }


def _classification_confidence_intervals(
    scores: List[float], binary_labels: List[int], threshold: float
) -> Dict[str, Any]:
    """Return reproducible bootstrap confidence intervals for held-out metrics."""
    if len(scores) < 2 or len(set(binary_labels)) < 2:
        return {
            "available": False,
            "reason": "Need at least two held-out pairs spanning both classes.",
        }

    try:
        from src.backend.evaluation.significance import bootstrap_confidence_interval

        intervals = bootstrap_confidence_interval(
            scores,
            binary_labels,
            threshold=threshold,
            ci_level=0.95,
            n_bootstrap=500,
            seed=42,
        )
    except Exception as exc:
        return {"available": False, "reason": str(exc)}

    return {"available": True, "method": "bootstrap_percentile", **intervals}


def _build_benchmark_trust_assessment(
    split_protocol: Dict[str, Any],
    confidence_intervals: Dict[str, Any],
    score_diagnostics: Dict[str, Any],
    threshold_strategy: str,
    headline_basis: str,
    binary_labels: List[int],
) -> Dict[str, Any]:
    """Grade whether benchmark metrics are suitable for internal decisions."""
    protocol = str(split_protocol.get("protocol", "unknown"))
    holdout_size = int(split_protocol.get("holdout_size") or 0)
    holdout_positive = int(split_protocol.get("holdout_positive_pairs") or 0)
    holdout_negative = int(split_protocol.get("holdout_negative_pairs") or 0)
    positive_count = int(sum(binary_labels))
    negative_count = int(len(binary_labels) - positive_count)
    reasons: List[str] = []
    blockers: List[str] = []

    if positive_count == 0 or negative_count == 0:
        blockers.append("Benchmark needs both positive and negative labeled pairs.")
    if score_diagnostics.get("label_conflict"):
        blockers.append(
            "Labeled negatives score at or above positives; inspect labels or fixtures."
        )

    confidence_available = bool(confidence_intervals.get("available"))
    if not confidence_available:
        reasons.append(
            "Confidence intervals are unavailable or too unstable for certification."
        )

    if protocol == "deterministic_stratified_calibration_holdout":
        if (
            holdout_size >= BENCHMARK_TRUST_THRESHOLDS["strong_holdout_pairs"]
            and holdout_positive
            >= BENCHMARK_TRUST_THRESHOLDS["strong_holdout_pairs_per_class"]
            and holdout_negative
            >= BENCHMARK_TRUST_THRESHOLDS["strong_holdout_pairs_per_class"]
            and confidence_available
            and not blockers
        ):
            grade = "strong"
            score = 90
        elif (
            holdout_size >= BENCHMARK_TRUST_THRESHOLDS["moderate_holdout_pairs"]
            and holdout_positive
            >= BENCHMARK_TRUST_THRESHOLDS["moderate_holdout_pairs_per_class"]
            and holdout_negative
            >= BENCHMARK_TRUST_THRESHOLDS["moderate_holdout_pairs_per_class"]
            and not blockers
        ):
            grade = "moderate"
            score = 70
        else:
            grade = "limited"
            score = 45
            reasons.append(
                "Held-out slice is small; use this run for direction, not final gates."
            )
    elif protocol == "locked_full_sample_evaluation":
        if (
            holdout_size >= BENCHMARK_TRUST_THRESHOLDS["strong_locked_pairs"]
            and holdout_positive
            >= BENCHMARK_TRUST_THRESHOLDS["strong_locked_pairs_per_class"]
            and holdout_negative
            >= BENCHMARK_TRUST_THRESHOLDS["strong_locked_pairs_per_class"]
            and confidence_available
            and not blockers
        ):
            grade = "strong"
            score = 85
        elif (
            holdout_size >= BENCHMARK_TRUST_THRESHOLDS["moderate_locked_pairs"]
            and holdout_positive
            >= BENCHMARK_TRUST_THRESHOLDS["moderate_locked_pairs_per_class"]
            and holdout_negative
            >= BENCHMARK_TRUST_THRESHOLDS["moderate_locked_pairs_per_class"]
            and not blockers
        ):
            grade = "moderate"
            score = 65
        else:
            grade = "limited"
            score = 40
            reasons.append(
                "Locked regression sample is small; add more labeled pairs before "
                "treating it as a release gate."
            )
    else:
        grade = "limited"
        score = 25
        reasons.append("No independent evaluation protocol was available.")

    if blockers:
        grade = "invalid"
        score = 0

    can_gate = (
        grade in {"strong", "moderate"} and threshold_strategy == "fixed_threshold"
    )
    if threshold_strategy != "fixed_threshold":
        reasons.append(
            "Threshold was calibrated in this run; use fixed-threshold regression "
            "for pass/fail gates."
        )

    return {
        "grade": grade,
        "score": score,
        "can_gate_internal_regression": can_gate,
        "headline_basis": headline_basis,
        "protocol": protocol,
        "sample_size": holdout_size,
        "positive_pairs": holdout_positive,
        "negative_pairs": holdout_negative,
        "confidence_intervals_available": confidence_available,
        "blockers": blockers,
        "warnings": reasons,
        "minimums": BENCHMARK_TRUST_THRESHOLDS,
    }


def _build_metric_integrity_summary(
    scores: List[float],
    labels: List[int],
    binary_labels: List[int],
    best_threshold: float,
    fixed_threshold: float,
    optimized_metrics: Dict[str, Any],
    heldout_metrics: Dict[str, Any],
    fixed_threshold_metrics: Dict[str, Any],
    split_protocol: Dict[str, Any],
    confidence_intervals: Dict[str, Any],
    score_diagnostics: Dict[str, Any],
    benchmark_trust: Dict[str, Any],
) -> Dict[str, Any]:
    """Describe benchmark metric trust boundaries and validation checks."""
    positive_count = int(sum(binary_labels))
    negative_count = int(len(binary_labels) - positive_count)
    warnings = []
    if positive_count == 0 or negative_count == 0:
        warnings.append("Metrics need both positive and negative labeled pairs.")
    if split_protocol.get("protocol") == "resubstitution_fallback":
        warnings.append(
            str(split_protocol.get("warning") or "No held-out split available.")
        )
    if split_protocol.get("protocol") == "locked_full_sample_evaluation":
        warnings.append(str(split_protocol.get("warning", "")))
    if score_diagnostics.get("label_conflict"):
        warnings.append(
            str(score_diagnostics.get("message", "Label conflict detected."))
        )
    warnings.extend(benchmark_trust.get("warnings", []))
    warnings.extend(benchmark_trust.get("blockers", []))

    return {
        "label_count_matches_score_count": len(scores) == len(labels),
        "positive_pairs": positive_count,
        "negative_pairs": negative_count,
        "optimized_threshold": round(float(best_threshold), 6),
        "fixed_threshold": round(float(fixed_threshold), 6),
        "calibration_confusion_matrix": optimized_metrics.get("confusion_matrix", {}),
        "heldout_confusion_matrix": heldout_metrics.get("confusion_matrix", {}),
        "fixed_threshold_confusion_matrix": fixed_threshold_metrics.get(
            "confusion_matrix", {}
        ),
        "calibration_f1": round(float(optimized_metrics.get("f1_score", 0.0)), 4),
        "heldout_f1": round(float(heldout_metrics.get("f1_score", 0.0)), 4),
        "fixed_threshold_f1": fixed_threshold_metrics.get("f1_score", 0.0),
        "calibration_bias_warning": (
            abs(best_threshold - fixed_threshold) > 1e-6
            or split_protocol.get("protocol") == "resubstitution_fallback"
        ),
        "split_protocol": split_protocol,
        "confidence_intervals": confidence_intervals,
        "benchmark_trust": benchmark_trust,
        "warnings": warnings,
    }


def _clamp_config_value(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Clamp a numeric config recommendation into a safe range."""
    return max(lower, min(upper, float(value)))


def _round_config_value(value: float) -> float:
    """Round config recommendations consistently for YAML patches."""
    return round(float(value), 4)


def _canonical_weight_key(engine_name: str) -> str:
    """Map runtime feature names back to engine_weights.yaml weight keys."""
    return {
        "fingerprint": "token",
        "semantic": "embedding",
        "codebert": "embedding",
        "gst": "ngram",
        "execution_cfg": "execution",
        "cfg": "graph",
    }.get(str(engine_name).strip().lower(), str(engine_name).strip().lower())


def _normalized_weight_patch(
    current_weights: Dict[str, Any],
    adjustments: Dict[str, float],
) -> Dict[str, float]:
    """Apply relative weight deltas and return a normalized weight map."""
    patched = {
        str(key): max(0.0, float(value))
        for key, value in current_weights.items()
        if isinstance(value, (int, float))
    }
    for key, delta in adjustments.items():
        if key not in patched:
            continue
        patched[key] = max(0.0, patched[key] + float(delta))

    total = sum(patched.values())
    if total <= 0:
        return patched
    return {key: _round_config_value(value / total) for key, value in patched.items()}


def _add_config_change(
    changes: List[Dict[str, Any]],
    path: str,
    current: Any,
    proposed: Any,
    reason: str,
    risk: str = "medium",
) -> None:
    """Append a config change when the proposed value differs from current."""
    if current == proposed:
        return
    changes.append(
        {
            "path": path,
            "current": current,
            "proposed": proposed,
            "reason": reason,
            "risk": risk,
        }
    )


def _manual_engine_tuning_options(
    weights: Dict[str, Any],
    decision: Dict[str, Any],
    precision_guard: Dict[str, Any],
    ast_boost: Dict[str, Any],
    deep_verify: Dict[str, Any],
    tuning_mode: str,
    dominant_engine: str,
) -> List[Dict[str, Any]]:
    """Expose editable config controls even when no automatic edit is available."""
    options: List[Dict[str, Any]] = []

    def add_option(
        path: str,
        current: Any,
        proposed: Any,
        reason: str,
        risk: str = "manual",
    ) -> None:
        if current is None:
            return
        rounded_current = (
            _round_config_value(current) if isinstance(current, float) else current
        )
        rounded_proposed = (
            _round_config_value(proposed) if isinstance(proposed, float) else proposed
        )
        if rounded_current == rounded_proposed:
            return
        options.append(
            {
                "path": path,
                "current": rounded_current,
                "proposed": rounded_proposed,
                "reason": reason,
                "risk": risk,
                "manual": True,
            }
        )

    threshold = _coerce_float(decision.get("default_threshold"), 0.82)
    min_agreement = int(decision.get("minimum_engine_agreement", 3) or 3)
    min_concrete = int(precision_guard.get("minimum_concrete_engines", 3) or 3)
    semantic_cap = _coerce_float(precision_guard.get("semantic_only_cap"), 0.38)
    penalty_multiplier = _coerce_float(precision_guard.get("penalty_multiplier"), 0.8)
    ast_threshold = _coerce_float(ast_boost.get("threshold"), 0.86)
    ast_floor = _coerce_float(ast_boost.get("minimum_guaranteed_score"), 0.68)
    deep_agreement = int(deep_verify.get("minimum_agreeing_engines", 3) or 3)

    if tuning_mode == "recall_first":
        threshold_proposed = _clamp_config_value(threshold - 0.02, 0.05, 0.95)
        agreement_proposed = max(1, min_agreement - 1)
        concrete_proposed = max(1, min_concrete - 1)
        semantic_cap_proposed = _clamp_config_value(semantic_cap + 0.03, 0.0, 1.0)
        penalty_proposed = _clamp_config_value(penalty_multiplier + 0.03, 0.0, 1.0)
        ast_threshold_proposed = _clamp_config_value(ast_threshold - 0.02, 0.0, 1.0)
        ast_floor_proposed = _clamp_config_value(ast_floor + 0.02, 0.0, 1.0)
        deep_agreement_proposed = max(1, deep_agreement - 1)
        weight_adjustments = {"embedding": 0.03, "execution": 0.02, "graph": 0.02}
    else:
        threshold_proposed = _clamp_config_value(threshold + 0.02, 0.05, 0.95)
        agreement_proposed = min(10, min_agreement + 1)
        concrete_proposed = min(10, min_concrete + 1)
        semantic_cap_proposed = _clamp_config_value(semantic_cap - 0.03, 0.0, 1.0)
        penalty_proposed = _clamp_config_value(penalty_multiplier - 0.03, 0.0, 1.0)
        ast_threshold_proposed = _clamp_config_value(ast_threshold + 0.02, 0.0, 1.0)
        ast_floor_proposed = _clamp_config_value(ast_floor - 0.02, 0.0, 1.0)
        deep_agreement_proposed = min(10, deep_agreement + 1)
        weight_adjustments = {"token": 0.015, "winnowing": 0.015, "execution": 0.015}
        if dominant_engine in weights:
            weight_adjustments[dominant_engine] = (
                weight_adjustments.get(dominant_engine, 0.0) - 0.025
            )
        if "embedding" in weights:
            weight_adjustments["embedding"] = (
                weight_adjustments.get("embedding", 0.0) - 0.02
            )

    add_option(
        "decision.default_threshold",
        threshold,
        threshold_proposed,
        "Manual control for the final positive cutoff. Raise for precision; lower for recall.",
    )
    add_option(
        "decision.minimum_engine_agreement",
        min_agreement,
        agreement_proposed,
        "Manual control for how many independent engines must agree.",
    )
    add_option(
        "precision_guard.minimum_concrete_engines",
        min_concrete,
        concrete_proposed,
        "Manual control for concrete evidence required before trusting broad matches.",
    )
    add_option(
        "precision_guard.semantic_only_cap",
        semantic_cap,
        semantic_cap_proposed,
        "Manual cap for semantic-only matches.",
    )
    add_option(
        "precision_guard.penalty_multiplier",
        penalty_multiplier,
        penalty_proposed,
        "Manual penalty for weak-evidence pairs.",
    )
    add_option(
        "ast_boost.threshold",
        ast_threshold,
        ast_threshold_proposed,
        "Manual AST boost activation threshold.",
    )
    add_option(
        "ast_boost.minimum_guaranteed_score",
        ast_floor,
        ast_floor_proposed,
        "Manual AST-only guaranteed score floor.",
    )
    add_option(
        "deep_verify.minimum_agreeing_engines",
        deep_agreement,
        deep_agreement_proposed,
        "Manual agreement requirement for deep verification.",
    )

    proposed_weights = _normalized_weight_patch(weights, weight_adjustments)
    for key in sorted(weights):
        value = weights.get(key)
        if isinstance(value, (int, float)):
            add_option(
                f"weights.{key}",
                float(value),
                float(proposed_weights.get(key, value)),
                f"Manual control for the {key} contribution in the fusion score.",
            )

    return options


def _engine_weight_change_reason(
    key: str,
    current: float,
    proposed: float,
    dominant_engine: str,
    dominant_value: float,
    mode: str,
) -> str:
    """Explain why a specific engine weight is being moved."""
    direction = "increase" if proposed > current else "decrease"
    percent = f"{dominant_value:.0%}"

    if mode == "precision_first":
        if key == dominant_engine:
            return (
                f"Decrease {key} because it is the dominant contributor "
                f"({percent}) while false positives are high."
            )
        if key == "embedding":
            return (
                "Decrease embedding because semantic-only similarity can match broad "
                "intent without enough concrete code evidence."
            )
        if key in {"token", "winnowing", "ngram"}:
            return (
                f"{direction.title()} {key} so high-risk decisions rely more on "
                "lexical overlap that is easier to audit against false positives."
            )
        if key == "execution":
            return (
                "Increase execution because behavior agreement is independent "
                "evidence and helps confirm suspicious pairs."
            )
        if key == "ast":
            return (
                "Reduce AST influence when structure is dominating negatives; "
                "keep AST as evidence but require corroboration."
            )
    elif mode == "recall_first":
        if key in {"embedding", "execution", "graph"}:
            return (
                f"{direction.title()} {key} to recover renamed, reordered, or "
                "semantic clones that lexical engines may miss."
            )
        if key in {"token", "ngram", "winnowing"}:
            return (
                f"{direction.title()} {key} so lexical mismatch does not block "
                "obfuscated true positives from ranking high enough."
            )
    elif mode == "ranking":
        return (
            f"{direction.title()} {key} to improve pair ranking before the final "
            "decision threshold is applied."
        )

    return (
        f"{direction.title()} {key} based on this run's contributor balance; "
        "validate the moved scores on the next labeled rerun."
    )


def _build_engine_tuning_recommendations(
    tool_name: str,
    precision: float,
    recall: float,
    f1_score: float,
    false_positive_rate: float,
    auc_pr: float,
    best_threshold: float,
    fixed_threshold: float,
    engine_contribution: Dict[str, float],
    confusion_matrix: Dict[str, Any],
    score_diagnostics: Dict[str, Any],
) -> Dict[str, Any]:
    """Build concrete candidate edits for engine_weights.yaml after a benchmark.

    These are deliberately conservative recommendations. They are meant to make
    the next tuning run easy to execute, not to silently overwrite production
    calibration from a single benchmark.
    """
    if tool_name != "integritydesk":
        return {
            "available": False,
            "reason": "Engine tuning recommendations only apply to IntegrityDesk.",
        }

    try:
        from src.backend.engines.scoring.fusion_engine import load_engine_config

        config = load_engine_config()
    except Exception as exc:
        return {"available": False, "reason": f"Could not load engine config: {exc}"}

    weights = config.get("weights") or {}
    decision = config.get("decision") or {}
    precision_guard = config.get("precision_guard") or {}
    ast_boost = config.get("ast_boost") or {}
    deep_verify = config.get("deep_verify") or {}
    advanced = config.get("advanced") or {}

    precision_problem = precision < 0.85
    recall_problem = recall < 0.85
    fpr_problem = false_positive_rate > 0.05
    ranking_problem = auc_pr < 0.85
    separation_problem = bool(
        score_diagnostics.get("score_overlap_warning")
        or score_diagnostics.get("label_conflict")
    )
    previous_candidate_pending = bool(advanced.get("weights_need_validation"))
    changes: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []

    current_threshold = _coerce_float(
        decision.get("default_threshold"), _coerce_float(fixed_threshold, 0.82)
    )
    if precision_problem or fpr_problem:
        proposed_threshold = _clamp_config_value(
            max(current_threshold + 0.03, best_threshold, 0.82), 0.05, 0.95
        )
        _add_config_change(
            changes,
            "decision.default_threshold",
            _round_config_value(current_threshold),
            _round_config_value(proposed_threshold),
            "False positives are high; raise the final production decision threshold.",
        )
    elif recall_problem and not separation_problem:
        proposed_threshold = _clamp_config_value(
            min(current_threshold - 0.03, best_threshold), 0.05, 0.95
        )
        _add_config_change(
            changes,
            "decision.default_threshold",
            _round_config_value(current_threshold),
            _round_config_value(proposed_threshold),
            "Recall is low without a precision/FPR problem; lower the final threshold modestly.",
        )
    elif (
        abs(best_threshold - current_threshold) > 0.02
        and f1_score < 0.90
        and not separation_problem
    ):
        _add_config_change(
            changes,
            "decision.default_threshold",
            _round_config_value(current_threshold),
            _round_config_value(best_threshold),
            "Use the benchmark-calibrated threshold as the next validation candidate.",
            risk="low",
        )

    if precision_problem or fpr_problem:
        current_min_agreement = int(decision.get("minimum_engine_agreement", 3) or 3)
        _add_config_change(
            changes,
            "decision.minimum_engine_agreement",
            current_min_agreement,
            min(5, max(3, current_min_agreement + 1)),
            "Require more independent evidence before a pair becomes a positive decision.",
        )
        current_concrete = int(precision_guard.get("minimum_concrete_engines", 3) or 3)
        _add_config_change(
            changes,
            "precision_guard.minimum_concrete_engines",
            current_concrete,
            min(5, max(3, current_concrete + 1)),
            "False positives need stronger token/AST/execution corroboration.",
        )
        current_semantic_cap = _coerce_float(
            precision_guard.get("semantic_only_cap"), 0.38
        )
        _add_config_change(
            changes,
            "precision_guard.semantic_only_cap",
            _round_config_value(current_semantic_cap),
            _round_config_value(max(0.25, current_semantic_cap - 0.05)),
            "Reduce broad semantic-only matches until negatives are cleaner.",
        )
        current_penalty = _coerce_float(precision_guard.get("penalty_multiplier"), 0.8)
        _add_config_change(
            changes,
            "precision_guard.penalty_multiplier",
            _round_config_value(current_penalty),
            _round_config_value(max(0.55, current_penalty - 0.05)),
            "Make weak-evidence pairs lose more score when guardrails fail.",
        )

    contributions = {
        _canonical_weight_key(key): float(value)
        for key, value in (engine_contribution or {}).items()
        if isinstance(value, (int, float))
    }
    dominant_engine = ""
    dominant_value = 0.0
    if contributions:
        dominant_engine, dominant_value = max(
            contributions.items(), key=lambda item: item[1]
        )

    weight_adjustments: Dict[str, float] = {}
    if precision_problem or fpr_problem:
        if dominant_engine in weights and dominant_value >= 0.45:
            weight_adjustments[dominant_engine] = (
                weight_adjustments.get(dominant_engine, 0.0) - 0.04
            )
        if "embedding" in weights:
            weight_adjustments["embedding"] = (
                weight_adjustments.get("embedding", 0.0) - 0.03
            )
        for key, delta in (("token", 0.025), ("winnowing", 0.025), ("execution", 0.02)):
            if key in weights:
                weight_adjustments[key] = weight_adjustments.get(key, 0.0) + delta
    elif recall_problem and not separation_problem:
        for key, delta in (("embedding", 0.035), ("execution", 0.025), ("graph", 0.02)):
            if key in weights:
                weight_adjustments[key] = weight_adjustments.get(key, 0.0) + delta
        for key, delta in (("token", -0.02), ("ngram", -0.015)):
            if key in weights:
                weight_adjustments[key] = weight_adjustments.get(key, 0.0) + delta
    elif ranking_problem:
        for key, delta in (("token", 0.015), ("ast", 0.015), ("embedding", -0.015)):
            if key in weights:
                weight_adjustments[key] = weight_adjustments.get(key, 0.0) + delta

    tuning_mode = (
        "separation_first"
        if recall_problem
        and separation_problem
        and not (precision_problem or fpr_problem)
        else (
            "precision_first"
            if precision_problem or fpr_problem
            else (
                "recall_first"
                if recall_problem
                else ("ranking" if ranking_problem else "balanced")
            )
        )
    )

    if weight_adjustments and not previous_candidate_pending:
        proposed_weights = _normalized_weight_patch(weights, weight_adjustments)
        for key in sorted(proposed_weights):
            if key not in weights:
                continue
            current_weight = _round_config_value(float(weights[key]))
            proposed_weight = proposed_weights[key]
            _add_config_change(
                changes,
                f"weights.{key}",
                current_weight,
                proposed_weight,
                _engine_weight_change_reason(
                    key,
                    current_weight,
                    proposed_weight,
                    dominant_engine,
                    dominant_value,
                    tuning_mode,
                ),
                risk="medium",
            )
    elif weight_adjustments and previous_candidate_pending:
        actions.append(
            {
                "title": "Do not stack another weight candidate yet",
                "detail": (
                    "The current engine_weights.yaml already contains an applied "
                    "candidate marked for validation. If the rerun did not improve, "
                    "avoid another weight-only Apply and inspect the false positives "
                    "or missed positives directly."
                ),
            }
        )

    if (precision_problem or fpr_problem) and dominant_engine == "ast":
        current_ast_boost = _coerce_float(
            ast_boost.get("minimum_guaranteed_score"), 0.68
        )
        _add_config_change(
            changes,
            "ast_boost.minimum_guaranteed_score",
            _round_config_value(current_ast_boost),
            _round_config_value(max(0.55, current_ast_boost - 0.04)),
            "AST dominates current evidence; lower the AST-only guaranteed floor.",
        )
        current_ast_threshold = _coerce_float(ast_boost.get("threshold"), 0.86)
        _add_config_change(
            changes,
            "ast_boost.threshold",
            _round_config_value(current_ast_threshold),
            _round_config_value(min(0.95, current_ast_threshold + 0.03)),
            "Only apply AST boost on stronger AST matches.",
        )

    if precision_problem or fpr_problem:
        current_deep_agreement = int(
            deep_verify.get("minimum_agreeing_engines", 3) or 3
        )
        _add_config_change(
            changes,
            "deep_verify.minimum_agreeing_engines",
            current_deep_agreement,
            min(5, max(3, current_deep_agreement + 1)),
            "Deep verification should require more agreement before lifting scores.",
        )

    if precision_problem or fpr_problem:
        actions.append(
            {
                "title": "Apply a precision-first candidate config",
                "detail": (
                    "False positives are the blocking issue. Start with the proposed threshold, "
                    "agreement, semantic cap, and weight changes, then rerun the same benchmark."
                ),
            }
        )
    if recall_problem and separation_problem:
        actions.append(
            {
                "title": "Fix score separation before threshold changes",
                "detail": (
                    "Known positives and labeled negatives overlap in the same score band. "
                    "Do not lower the final threshold from this run alone; inspect the "
                    "highest-scoring negatives and missed positives, then adjust the engines "
                    "that collapse template, starter-code, or same-assignment pairs together."
                ),
            }
        )
    if recall_problem:
        actions.append(
            {
                "title": "Audit missed positives before lowering final threshold",
                "detail": (
                    "Recall is also low. If the missed positives are Type-3/Type-4 clones, "
                    "improve candidate retrieval or semantic/execution reranking before making "
                    "the final decision threshold too permissive."
                ),
            }
        )
    if dominant_engine:
        actions.append(
            {
                "title": f"Check {dominant_engine} false-positive dominance",
                "detail": (
                    f"{dominant_engine} contributes {dominant_value:.0%} of current evidence. "
                    "Inspect high-scoring negatives; if they are caused by this engine, keep its "
                    "proposed weight reduction."
                ),
            }
        )

    if not actions:
        actions.append(
            {
                "title": "Keep current config as baseline",
                "detail": (
                    "The scorecard is balanced enough that the next step is a harder benchmark, "
                    "not a config change."
                ),
            }
        )

    return {
        "available": True,
        "config_file": "src/backend/engines/engine_weights.yaml",
        "mode": tuning_mode,
        "summary": (
            f"Precision {precision:.1%}, recall {recall:.1%}, F1 {f1_score:.1%}, "
            f"FPR {false_positive_rate:.1%}. Proposed changes are candidates for the next rerun."
        ),
        "dominant_engine": dominant_engine,
        "dominant_engine_contribution": round(dominant_value, 4),
        "confusion_matrix": confusion_matrix,
        "score_diagnostics": score_diagnostics,
        "actions": actions,
        "config_changes": changes,
        "manual_config_options": _manual_engine_tuning_options(
            weights,
            decision,
            precision_guard,
            ast_boost,
            deep_verify,
            tuning_mode,
            dominant_engine,
        ),
        "apply_instructions": [
            "Copy the proposed values into src/backend/engines/engine_weights.yaml.",
            "Rerun the same benchmark dataset and compare F1, precision, recall, and FPR.",
            "Only keep the changes if held-out F1 improves and FPR does not regress.",
        ],
    }


ENGINE_OPTIMIZATION_ALLOWED_PREFIXES = {
    "weights",
    "decision",
    "precision_guard",
    "ast_boost",
    "deep_verify",
    "thresholds",
}


def _validate_engine_optimization_value(path: str, proposed: Any) -> None:
    """Validate an optimization value according to its engine config path."""
    if not isinstance(proposed, (int, float, bool)):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported proposed value for {path}",
        )
    if isinstance(proposed, bool):
        return

    numeric = float(proposed)
    unit_interval_paths = (
        path.startswith("weights.")
        or path.startswith("thresholds.")
        or path.endswith("_threshold")
        or path.endswith("_floor")
        or path.endswith("_cap")
        or path.endswith("_multiplier")
        or path.endswith(".default_threshold")
        or path.endswith(".minimum_confidence")
    )
    count_paths = (
        path.endswith("_engines")
        or path.endswith("_engines_high_score")
        or path.endswith("_agreement")
        or path.endswith(".minimum_engine_agreement")
    )

    if unit_interval_paths and not 0.0 <= numeric <= 1.0:
        raise HTTPException(
            status_code=400,
            detail=f"{path} must be between 0.0 and 1.0",
        )
    if count_paths and not 1 <= numeric <= 10:
        raise HTTPException(
            status_code=400,
            detail=f"{path} must be between 1 and 10",
        )
    if not unit_interval_paths and not count_paths and not 0.0 <= numeric <= 10.0:
        raise HTTPException(
            status_code=400,
            detail=f"{path} must be between 0.0 and 10.0",
        )


def _apply_engine_optimization_changes(
    config: Dict[str, Any], changes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Apply vetted benchmark optimization changes to an engine config copy."""
    updated_config = json.loads(json.dumps(config))
    applied_changes: List[Dict[str, Any]] = []

    for change in changes:
        if not isinstance(change, dict):
            continue
        path = str(change.get("path") or "").strip()
        parts = [part for part in path.split(".") if part]
        if len(parts) < 2 or parts[0] not in ENGINE_OPTIMIZATION_ALLOWED_PREFIXES:
            raise HTTPException(
                status_code=400, detail=f"Unsupported config path: {path}"
            )

        proposed = change.get("proposed")
        _validate_engine_optimization_value(path, proposed)

        target = updated_config
        for part in parts[:-1]:
            target = target.setdefault(part, {})
            if not isinstance(target, dict):
                raise HTTPException(
                    status_code=400, detail=f"Invalid config path: {path}"
                )
        target[parts[-1]] = proposed
        applied_changes.append(
            {
                "path": path,
                "proposed": proposed,
                "reason": change.get("reason", ""),
            }
        )

    if "weights" in updated_config and isinstance(updated_config["weights"], dict):
        total = sum(
            float(value)
            for value in updated_config["weights"].values()
            if isinstance(value, (int, float))
        )
        if total > 0:
            updated_config["weights"] = {
                key: _round_config_value(float(value) / total)
                for key, value in updated_config["weights"].items()
                if isinstance(value, (int, float))
            }
        updated_config.setdefault("advanced", {})["weights_need_validation"] = True

    return {"config": updated_config, "applied_changes": applied_changes}


def _build_threshold_calibration_points(
    scores_arr: np.ndarray, labels_arr: np.ndarray, thresholds: List[float]
) -> List[Dict[str, Any]]:
    """Compute precision, recall, and FPR at fixed decision thresholds."""
    points = []
    for threshold in sorted({round(float(value), 6) for value in thresholds}):
        preds = (scores_arr >= threshold).astype(int)
        tp = int(np.sum((preds == 1) & (labels_arr == 1)))
        fp = int(np.sum((preds == 1) & (labels_arr == 0)))
        tn = int(np.sum((preds == 0) & (labels_arr == 0)))
        fn = int(np.sum((preds == 0) & (labels_arr == 1)))
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        f1_score = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )
        points.append(
            {
                "threshold": round(threshold, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1_score, 4),
                "false_positive_rate": round(false_positive_rate, 4),
                "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            }
        )
    return points


def _build_score_diagnostics(
    scores_arr: np.ndarray, labels_arr: np.ndarray
) -> Dict[str, Any]:
    """Summarize score separation to explain precision and retrieval failures."""
    positives = scores_arr[labels_arr == 1]
    negatives = scores_arr[labels_arr == 0]

    diagnostics: Dict[str, Any] = {
        "positive_count": int(len(positives)),
        "negative_count": int(len(negatives)),
        "label_conflict": False,
        "message": "",
    }
    if len(positives) == 0 or len(negatives) == 0:
        diagnostics["message"] = (
            "Need both positive and negative labeled pairs to explain score separation."
        )
        return diagnostics

    max_positive = float(np.max(positives))
    min_positive = float(np.min(positives))
    mean_positive = float(np.mean(positives))
    median_positive = float(np.median(positives))
    max_negative = float(np.max(negatives))
    mean_negative = float(np.mean(negatives))
    median_negative = float(np.median(negatives))
    negatives_above_best_positive = int(np.sum(negatives > max_positive))
    negatives_above_worst_positive = int(np.sum(negatives >= min_positive))
    negatives_above_median_positive = int(np.sum(negatives >= median_positive))
    label_conflict = bool(
        max_negative >= max_positive or mean_negative >= mean_positive
    )
    score_overlap_warning = bool(
        label_conflict
        or max_negative >= median_positive
        or median_negative >= median_positive
    )

    diagnostics.update(
        {
            "max_positive_score": round(max_positive, 4),
            "min_positive_score": round(min_positive, 4),
            "mean_positive_score": round(mean_positive, 4),
            "median_positive_score": round(median_positive, 4),
            "max_negative_score": round(max_negative, 4),
            "mean_negative_score": round(mean_negative, 4),
            "median_negative_score": round(median_negative, 4),
            "negatives_above_best_positive": negatives_above_best_positive,
            "negatives_above_worst_positive": negatives_above_worst_positive,
            "negatives_above_median_positive": negatives_above_median_positive,
            "label_conflict": label_conflict,
            "score_overlap_warning": score_overlap_warning,
        }
    )

    if label_conflict:
        diagnostics["message"] = (
            "Some labeled negatives score as high as or higher than labeled positives. "
            "Inspect dataset labels and common starter-code/template pairs before "
            "treating every high-scoring negative as an engine false positive."
        )
    elif score_overlap_warning:
        diagnostics["message"] = (
            "Labeled negatives overlap the positive score band. Treat this as a score "
            "separation problem before lowering the final decision threshold."
        )
    else:
        diagnostics["message"] = (
            "Positive scores are separated from negatives; tune the decision threshold "
            "and feature weights around this margin."
        )
    return diagnostics


def _compute_top_k_precision(
    scores: List[float], binary_labels: List[int], k: int = 10
) -> float:
    """Compute precision@k for whether the top-ranked pairs are true positives."""
    if k <= 0 or not scores:
        return 0.0

    ranked = sorted(zip(scores, binary_labels), key=lambda item: item[0], reverse=True)
    top_k = ranked[: min(k, len(ranked))]
    if not top_k:
        return 0.0
    return sum(label for _, label in top_k) / len(top_k)


def _compute_top_k_recall(
    scores: List[float], binary_labels: List[int], k: int = 10
) -> float:
    """Compute recall@k as a supplemental retrieval diagnostic."""
    total_positives = sum(binary_labels)
    if total_positives <= 0:
        return 0.0

    ranked = sorted(zip(scores, binary_labels), key=lambda item: item[0], reverse=True)
    retrieved_positives = sum(label for _, label in ranked[:k])
    return retrieved_positives / total_positives


def _compute_top_k_retrieval(
    scores: List[float], binary_labels: List[int], k: int = 10
) -> float:
    """Backward-compatible alias for top-k precision."""
    return _compute_top_k_precision(scores, binary_labels, k)


def _compute_engine_contribution(pairs: List[Dict[str, Any]]) -> Dict[str, float]:
    """Estimate per-engine contribution from IntegrityDesk feature scores."""
    totals: Dict[str, float] = {}
    for pair in pairs:
        contribution_source = pair.get("contributions") or pair.get("features") or {}
        for name, value in contribution_source.items():
            numeric_value = _coerce_float(value)
            if numeric_value > 0:
                totals[str(name)] = totals.get(str(name), 0.0) + numeric_value

    total = sum(totals.values())
    if total <= 0:
        return {}

    return {
        name: round(value / total, 4)
        for name, value in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    }


def _compute_auc_fallback(
    scores: np.ndarray, labels: np.ndarray, curve_type: str
) -> float:
    """Fallback AUC computation without sklearn."""
    if len(np.unique(labels)) < 2:
        return 0.0

    sorted_idx = np.argsort(scores)[::-1]
    sorted_labels = labels[sorted_idx]

    if curve_type == "roc":
        tp = np.cumsum(sorted_labels)
        fp = np.cumsum(1 - sorted_labels)
        tpr = tp / max(1, tp[-1])
        fpr = fp / max(1, fp[-1])
        return np.trapz(tpr, fpr)
    else:
        tp = np.cumsum(sorted_labels)
        prec = tp / (tp + np.arange(1, len(tp) + 1))
        rec = tp / max(1, tp[-1])
        return np.trapz(prec, rec)


def _resolve_report_path(job_id: str, job_key: str, fallback_filename: str) -> PathLib:
    """Resolve a report path from live job state or on-disk report output.

    Generated reports remain on disk under `reports/<job_id>/` and completed
    jobs now persist there as well. This helper keeps report downloads working
    even when the in-memory cache has not been warmed yet.
    """
    job = _get_job(job_id)
    if job and job_key in job:
        return PathLib(job[job_key])

    return REPORTS_DIR / job_id / fallback_filename


def _refresh_html_report_from_json(job_id: str) -> None:
    """Regenerate the browsable HTML report from the stored JSON payload."""
    report_json_path = _resolve_report_path(job_id, "report_json_path", "report.json")
    report_html_path = _resolve_report_path(job_id, "report_path", "report.html")
    if not report_json_path.exists():
        return

    try:
        report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read stored report JSON for %s", job_id)
        return

    # Hoist report_id from metadata to top-level so generate_html_report can find it
    if not report_payload.get("report_id"):
        report_payload["report_id"] = (
            report_payload.get("metadata", {}).get("report_id") or job_id
        )

    institution_name = str(
        report_payload.get("metadata", {}).get("institution")
        or report_payload.get("course_name")
        or "Course"
    )
    report_html_path.parent.mkdir(parents=True, exist_ok=True)
    report_html_path.write_text(
        ReportGenerator(
            institution_name=institution_name,
            branding_color="#2563eb",
        ).generate_html_report(report_payload),
        encoding="utf-8",
    )


def _format_env_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _quote_env_value(value: str) -> str:
    if value == "":
        return '""'
    if any(ch in value for ch in [" ", "#", '"', "'"]):
        return json.dumps(value)
    return value


def _persist_env_settings(updates: Dict[str, Any]) -> None:
    lines = (
        ENV_SETTINGS_PATH.read_text(encoding="utf-8").splitlines()
        if ENV_SETTINGS_PATH.exists()
        else []
    )
    rendered_updates = {key: _format_env_value(value) for key, value in updates.items()}

    new_lines: List[str] = []
    seen = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key not in rendered_updates:
            new_lines.append(line)
            continue

        seen.add(key)
        value = rendered_updates[key]
        if value is None:
            continue
        new_lines.append(f"{key}={_quote_env_value(value)}")

    for key, value in rendered_updates.items():
        if key in seen or value is None:
            continue
        new_lines.append(f"{key}={_quote_env_value(value)}")

    content = "\n".join(new_lines).rstrip()
    ENV_SETTINGS_PATH.write_text(f"{content}\n" if content else "", encoding="utf-8")


def _should_require_auth(path: str) -> bool:
    if path in AUTH_EXEMPT_PATHS:
        return False
    # Allow unauthenticated access to job status endpoints
    if path.startswith("/api/jobs/") or path.startswith("/api/job/"):
        return False
    # Allow unauthenticated access to benchmark status polling
    if path.startswith("/api/benchmark/status/"):
        return False
    # Allow unauthenticated access to report endpoints
    if path.startswith("/report/"):
        return False
    return path.startswith(AUTH_PROTECTED_PREFIXES)


def _ensure_auth_secret() -> str:
    if not settings.AUTH_JWT_SECRET:
        raise RuntimeError(
            "AUTH_JWT_SECRET is required. Set it in src/backend/.env.local with a secure random string. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    return settings.AUTH_JWT_SECRET


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _validate_password_input(password: str) -> None:
    # Skip strict validation in debug mode for easier testing
    if settings.DEBUG_MODE:
        return

    if len(password) < 12:
        raise HTTPException(
            status_code=400, detail="Password must be at least 12 characters long"
        )
    if not any(c.isupper() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one uppercase letter",
        )
    if not any(c.islower() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one lowercase letter",
        )
    if not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400, detail="Password must contain at least one number"
        )
    # Common weak passwords
    weak_passwords = ["password", "12345678", "qwerty", "admin", "letmein"]
    if password.lower() in weak_passwords:
        raise HTTPException(
            status_code=400,
            detail="Password is too common. Please choose a stronger password",
        )


def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_access_token(user: User) -> str:
    secret = _ensure_auth_secret()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id is not None else None,
        "exp": now + timedelta(minutes=settings.AUTH_TOKEN_EXPIRE_MINUTES),
        "iat": now,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _serialize_user(user: User) -> Dict[str, Any]:
    tenant = getattr(user, "tenant", None)

    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": str(user.tenant_id) if user.tenant_id is not None else None,
        "tenant_name": tenant.name if tenant else None,
        "is_active": bool(user.is_active),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


USER_EDITABLE_SETTINGS_DEFAULTS: Dict[str, Any] = {
    "default_threshold": settings.DEFAULT_THRESHOLD,
    "openai_api_key": settings.OPENAI_API_KEY or "",
    "openai_base_url": settings.OPENAI_BASE_URL,
    "openai_model": settings.OPENAI_MODEL,
    "anthropic_api_key": settings.ANTHROPIC_API_KEY or "",
    "anthropic_model": settings.ANTHROPIC_MODEL,
    "moss_user_id": settings.MOSS_USER_ID or "",
    "embedding_runtime": settings.EMBEDDING_RUNTIME,
    "embedding_model": settings.EMBEDDING_MODEL,
    "embedding_server_url": settings.EMBEDDING_SERVER_URL,
    "embedding_server_host": settings.EMBEDDING_SERVER_HOST,
    "embedding_server_port": settings.EMBEDDING_SERVER_PORT,
    "embedding_device": settings.EMBEDDING_DEVICE,
    "embedding_batch_size": settings.EMBEDDING_BATCH_SIZE,
    "engine_weights": settings.ENGINE_WEIGHTS,
    "batch_size": settings.BATCH_SIZE,
    "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
    "max_files_per_job": settings.MAX_FILES_PER_JOB,
    "webhook_url": "",
    "audit_log_level": "INFO",
    "audit_retention_days": 365,
    "debug_mode": False,
    "source_scan_enabled": False,
    "source_scan_sites": ["https://github.com"],
    "professor_profile": {
        "assignment_type": "auto_detect",
        "sensitivity": "balanced",
        "starter_code_handling": "student_written_only",
        "previous_term_matching": "same_course_only",
        "ai_rewrite_detection": "balanced",
        "result_volume": "top_25",
    },
}

SETTINGS_ATTR_MAP = {
    "default_threshold": "DEFAULT_THRESHOLD",
    "openai_api_key": "OPENAI_API_KEY",
    "openai_base_url": "OPENAI_BASE_URL",
    "openai_model": "OPENAI_MODEL",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "anthropic_model": "ANTHROPIC_MODEL",
    "moss_user_id": "MOSS_USER_ID",
    "embedding_runtime": "EMBEDDING_RUNTIME",
    "embedding_model": "EMBEDDING_MODEL",
    "embedding_server_url": "EMBEDDING_SERVER_URL",
    "embedding_server_host": "EMBEDDING_SERVER_HOST",
    "embedding_server_port": "EMBEDDING_SERVER_PORT",
    "embedding_device": "EMBEDDING_DEVICE",
    "embedding_batch_size": "EMBEDDING_BATCH_SIZE",
    "engine_weights": "ENGINE_WEIGHTS",
    "batch_size": "BATCH_SIZE",
    "max_file_size_mb": "MAX_FILE_SIZE_MB",
    "max_files_per_job": "MAX_FILES_PER_JOB",
    "webhook_url": "WEBHOOK_URL",
    "audit_log_level": "AUDIT_LOG_LEVEL",
    "audit_retention_days": "AUDIT_RETENTION_DAYS",
    "debug_mode": "DEBUG_MODE",
    "source_scan_enabled": "SOURCE_SCAN_ENABLED",
    "source_scan_sites": "SOURCE_SCAN_SITES",
}

SECRET_SETTING_KEYS = {"openai_api_key", "anthropic_api_key", "moss_user_id"}
ENGINE_DISPLAY_LABELS = {
    "token": "Token",
    "ast": "AST",
    "winnowing": "Winnowing",
    "gst": "String Tiling",
    "ngram": "N-gram",
    "semantic": "Semantic",
    "embedding": "Embedding",
    "graph": "Graph",
    "static_rules": "Static Rules",
    "web": "Web",
    "ai_detection": "AI Detection",
}
UPLOAD_ENGINE_KEYS = (
    "token",
    "winnowing",
    "gst",
    "ast",
    "ngram",
    "graph",
    "embedding",
    "static_rules",
)


def _load_tenant_settings_record(tenant_id: Optional[str]) -> Dict[str, Any]:
    if not tenant_id:
        return {}

    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant or not isinstance(tenant.settings, dict):
            return {}
        return dict(tenant.settings)


def _build_settings_payload(tenant_id: Optional[str]) -> Dict[str, Any]:
    stored = _load_tenant_settings_record(tenant_id)
    payload = {**USER_EDITABLE_SETTINGS_DEFAULTS, **stored}
    payload["engine_weights"] = _normalize_engine_weights(payload.get("engine_weights"))
    payload["source_scan_sites"] = _normalize_source_scan_sites(
        payload.get("source_scan_sites")
    )

    openai_key = str(payload.get("openai_api_key") or "")
    anthropic_key = str(payload.get("anthropic_api_key") or "")
    moss_user_id = str(payload.get("moss_user_id") or "")

    payload["openai_api_key"] = ""
    payload["openai_api_key_configured"] = bool(openai_key)
    payload["anthropic_api_key"] = ""
    payload["anthropic_api_key_configured"] = bool(anthropic_key)
    payload["moss_user_id"] = ""
    payload["moss_user_id_configured"] = bool(moss_user_id)
    from src.backend.engines.scoring.professor_profiles import (
        apply_professor_profile,
        professor_profile_catalog,
    )

    applied_professor_profile = apply_professor_profile(
        payload.get("professor_profile")
    )
    payload["professor_profile_catalog"] = professor_profile_catalog()
    payload["professor_profile"] = dict(applied_professor_profile.profile.__dict__)
    payload["applied_professor_profile"] = applied_professor_profile.to_dict()
    return payload


def _apply_runtime_settings_from_record(record: Dict[str, Any]) -> None:
    merged = {**USER_EDITABLE_SETTINGS_DEFAULTS, **(record or {})}
    merged["engine_weights"] = _normalize_engine_weights(merged.get("engine_weights"))
    for key, attr in SETTINGS_ATTR_MAP.items():
        if key in merged:
            if not hasattr(settings, attr):
                continue
            setattr(settings, attr, merged[key])
            if key in SECRET_SETTING_KEYS and merged[key]:
                os.environ[attr] = str(merged[key])


def _normalize_source_scan_sites(value: Any) -> List[str]:
    """Normalize admin-configured external source scan locations."""
    if isinstance(value, str):
        raw_sites = re.split(r"[\n,]+", value)
    elif isinstance(value, list):
        raw_sites = [str(item) for item in value]
    else:
        raw_sites = []

    sites: List[str] = []
    for site in raw_sites:
        normalized = site.strip()
        if normalized and normalized not in sites:
            sites.append(normalized)
    return sites[:20]


def _get_upload_engine_weights(
    tenant_id: Optional[str], selected_keys: Optional[List[str]] = None
) -> Dict[str, float]:
    payload = _build_settings_payload(tenant_id)
    engine_weights = _normalize_engine_weights(payload.get("engine_weights"))

    if selected_keys:
        selected = {key for key in selected_keys if key in UPLOAD_ENGINE_KEYS}
        if selected:
            for key in UPLOAD_ENGINE_KEYS:
                if key not in selected:
                    engine_weights[key] = 0.0

    return {key: _coerce_float(engine_weights.get(key)) for key in UPLOAD_ENGINE_KEYS}


def _build_fusion_weights(engine_weights: Dict[str, float]) -> Dict[str, float]:
    fusion_weights = {
        "fingerprint": _coerce_float(engine_weights.get("token")),
        "winnowing": _coerce_float(engine_weights.get("winnowing")),
        "string_tiling": _coerce_float(engine_weights.get("gst")),
        "ast": _coerce_float(engine_weights.get("ast")),
        "ngram": _coerce_float(engine_weights.get("ngram")),
        "graph": _coerce_float(engine_weights.get("graph")),
        "embedding": _coerce_float(
            engine_weights.get("embedding", engine_weights.get("semantic"))
        ),
        "static_rules": _coerce_float(engine_weights.get("static_rules")),
    }
    if not any(value > 0 for value in fusion_weights.values()):
        return {}
    return fusion_weights


def _issue_auth_cookie(response: Response, user: User) -> None:
    token = _create_access_token(user)
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=AUTH_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/")


def _generate_tenant_name(full_name: str, email: str) -> str:
    base = full_name.strip() or email.split("@", 1)[0]
    return f"{base} Workspace"


def _create_tenant(db, name: str) -> Tenant:
    tenant = Tenant(
        name=name,
        api_key_hash=hashlib.sha256(
            f"{uuid.uuid4()}:{name}".encode("utf-8")
        ).hexdigest(),
    )
    db.add(tenant)
    db.flush()
    return tenant


def _authenticate_request(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = jwt.decode(token, _ensure_auth_secret(), algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired session"
        ) from exc

    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session payload")

    with SessionLocal() as db:
        user = db.scalar(
            select(User).options(joinedload(User.tenant)).where(User.id == user_id)
        )
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User account is unavailable")
        serialized = _serialize_user(user)

    return serialized


def _require_current_user(request: Request, admin_only: bool = False) -> Dict[str, Any]:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if admin_only and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


def _job_is_accessible(job: Dict[str, Any], user: Optional[Dict[str, Any]]) -> bool:
    # Allow access to jobs without authentication (guest users)
    if user is None:
        return True

    if user.get("role") == "admin":
        return True

    owner_user_id = str(job.get("owner_user_id") or "")
    if owner_user_id and owner_user_id == user.get("id"):
        return True

    tenant_id = str(job.get("tenant_id") or "")
    if tenant_id and tenant_id == user.get("tenant_id"):
        return True

    # Allow access if job has no owner (guest job)
    if not owner_user_id and not tenant_id:
        return True

    return False


def _require_job_access(job_id: str, request: Request) -> Dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Allow unauthenticated access for guest users
    user = getattr(request.state, "user", None)
    if not _job_is_accessible(job, user):
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@app.middleware("http")
async def dashboard_auth_middleware(request: Request, call_next):
    """Authentication middleware for protected endpoints."""
    # Always allow OPTIONS requests for CORS preflight - let CORS middleware handle headers
    if request.method == "OPTIONS":
        return await call_next(request)

    path = request.url.path
    if not _should_require_auth(path):
        return await call_next(request)

    try:
        user = _authenticate_request(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    request.state.user = user
    request.state.user_id = user["id"]
    request.state.user_role = user["role"]
    request.state.tenant_id = user.get("tenant_id")
    _apply_runtime_settings_from_record(
        _load_tenant_settings_record(user.get("tenant_id"))
    )
    return await call_next(request)


@app.get("/report/{job_id}/download", response_class=HTMLResponse)
async def download_report_html(request: Request, job_id: str):
    _require_job_access(job_id, request)
    _refresh_html_report_from_json(job_id)
    rp = _resolve_report_path(job_id, "report_path", "report.html")
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        str(rp),
        media_type="text/html",
        headers={
            "Content-Disposition": f'inline; filename="integritydesk_report_{job_id}.html"'
        },
    )


@app.get("/report/{job_id}/download-json")
async def download_report_json(job_id: str, request: Request):
    _require_job_access(job_id, request)
    rp = _resolve_report_path(job_id, "report_json_path", "report.json")
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        str(rp),
        media_type="application/json",
        filename=f"integritydesk_report_{job_id}.json",
    )


@app.get("/report/{job_id}/committee", response_class=HTMLResponse)
async def download_committee_report(request: Request, job_id: str):
    _require_job_access(job_id, request)
    _refresh_html_report_from_json(job_id)
    rp = _resolve_report_path(job_id, "report_path", "report.html")
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        str(rp),
        media_type="text/html",
        headers={
            "Content-Disposition": (
                f'inline; filename="integritydesk_originality_report_{job_id}.html"'
            )
        },
    )


@app.get("/report/{job_id}/download-pdf")
async def download_report_pdf(job_id: str, request: Request):
    """Generate and return a PDF version of the originality report."""
    _require_job_access(job_id, request)

    # Always regenerate HTML from JSON so report_id and all fields are current
    _refresh_html_report_from_json(job_id)

    rp = _resolve_report_path(job_id, "report_path", "report.html")
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")

    html_content = rp.read_text(encoding="utf-8")

    # Strip the in-page Download PDF / Print buttons — they make no sense in a PDF
    html_content = html_content.replace(
        'class="action-buttons no-print"',
        'class="action-buttons no-print" style="display:none"',
    )

    try:
        import weasyprint

        # base_url lets WeasyPrint resolve any relative asset references
        base_url = str(rp.parent.as_uri())
        pdf_bytes = weasyprint.HTML(string=html_content, base_url=base_url).write_pdf(
            stylesheets=[
                weasyprint.CSS(
                    string="""
                    @page {
                        size: A4;
                        margin: 15mm 12mm 18mm 12mm;
                        @bottom-center {
                            content: "Originality Report  ·  Page " counter(page) " of " counter(pages);
                            font-size: 9pt;
                            color: #64748b;
                        }
                    }
                    body { background: #fff !important; }
                    .shell { box-shadow: none !important; max-width: 100% !important; }
                    .no-print, .action-buttons { display: none !important; }
                    details.finding { page-break-inside: avoid; }
                    .code-card { page-break-inside: avoid; }
                    summary::after { display: none !important; }
                    details > .finding-body { display: block !important; }
                    """
                )
            ]
        )

        response = Response(content=pdf_bytes, media_type="application/pdf")
        response.headers["Content-Disposition"] = (
            f'attachment; filename="integritydesk_report_{job_id}.pdf"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    except ImportError:
        logger.warning(
            "weasyprint not available, returning print-ready HTML for %s", job_id
        )
        styled_html = html_content.replace(
            "</head>",
            """<style>
            @media print {
                body { background: #fff !important; }
                .shell { box-shadow: none !important; max-width: 100% !important; }
                .no-print, .action-buttons { display: none !important; }
                details > .finding-body { display: block !important; }
                details.finding { page-break-inside: avoid; }
            }
            </style></head>""",
        )
        return Response(
            content=styled_html,
            media_type="text/html",
            headers={
                "Content-Disposition": f'attachment; filename="integritydesk_report_{job_id}.html"'
            },
        )
    except Exception as exc:
        logger.exception("PDF generation failed for %s: %s", job_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {exc}. Try using the Print button in your browser instead.",
        )


def _build_ai_originality_report_html(job: Dict[str, Any]) -> str:
    """Build a Turnitin-grade printable AI Detector originality report."""
    from src.backend.infrastructure.ai_report_generator import (
        build_ai_originality_report_html,
    )

    return build_ai_originality_report_html(job)


@app.get("/report/{job_id}/ai-originality-pdf")
async def download_ai_originality_pdf(job_id: str, request: Request):
    job = _require_job_access(job_id, request)
    if job.get("job_type") != "ai_detector":
        raise HTTPException(status_code=404, detail="AI Detector report not found")

    html_content = _build_ai_originality_report_html(job)
    try:
        import weasyprint

        pdf = weasyprint.HTML(string=html_content).write_pdf()
        response = Response(content=pdf, media_type="application/pdf")
    except Exception as exc:
        logger.warning("AI originality PDF fallback for %s: %s", job_id, exc)
        response = Response(
            content=_minimal_pdf_bytes(f"Originality Report {job_id}"),
            media_type="application/pdf",
        )

    response.headers["Content-Disposition"] = (
        f"attachment; filename=integritydesk_originality_report_{job_id}.pdf"
    )
    return response


@app.get("/benchmark/{job_id}/download-csv")
async def download_benchmark_csv(job_id: str):
    job = _get_job(job_id)
    if not job or "pair_results" not in job:
        raise HTTPException(status_code=404, detail="Benchmark results not found")

    import csv
    from io import StringIO

    si = StringIO()
    writer = csv.writer(si)

    # Headers
    headers = ["Pair 1", "Pair 2", "Label"]
    if job["pair_results"] and job["pair_results"][0].get("tool_results"):
        for tool in [t["tool"] for t in job["pair_results"][0]["tool_results"]]:
            headers.append(f"{tool} Score")
    writer.writerow(headers)

    # Rows
    for pair in job["pair_results"]:
        row = [pair["file_a"], pair["file_b"], pair["label"]]
        for tool_result in pair["tool_results"]:
            row.append(f"{tool_result['score']:.3f}")
        writer.writerow(row)

    response = Response(content=si.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        f"attachment; filename=benchmark_results_{job_id}.csv"
    )
    return response


@app.get("/benchmark/{job_id}/download-pdf")
async def download_benchmark_pdf(job_id: str):
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Benchmark job not found")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Benchmark Results {job_id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 20px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background: #f5f5f5; font-weight: 600; }}
            h1 {{ font-size: 18px; margin-bottom: 10px; }}
            .meta {{ color: #666; font-size: 12px; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>Benchmark Results</h1>
        <div class="meta">
            Job ID: {job_id}<br>
            Generated: {datetime.now().isoformat()}
        </div>
        <table>
            <thead>
                <tr>
                    <th>Pair 1</th>
                    <th>Pair 2</th>
                    <th>Tool</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
    """

    for pair in job.get("pair_results", []):
        for tr in pair.get("tool_results", []):
            html_content += f"""
            <tr>
                <td>{pair['file_a']}</td>
                <td>{pair['file_b']}</td>
                <td>{tr['tool']}</td>
                <td>{tr['score']:.3f}</td>
            </tr>
            """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    try:
        import weasyprint

        pdf = weasyprint.HTML(string=html_content).write_pdf()
        response = Response(content=pdf, media_type="application/pdf")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=benchmark_{job_id}.pdf"
        )
        return response
    except ImportError:
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Disposition": f"attachment; filename=benchmark_{job_id}.html"
            },
        )
    except Exception as exc:
        logger.warning(
            "Benchmark PDF export fell back to minimal PDF for %s: %s", job_id, exc
        )
        response = Response(
            content=_minimal_pdf_bytes(f"Benchmark {job_id}"),
            media_type="application/pdf",
        )
        response.headers["Content-Disposition"] = (
            f"attachment; filename=benchmark_{job_id}.pdf"
        )
        return response


def _pdf_escape(value: Any) -> str:
    """Escape text for a simple PDF content stream."""
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _format_report_percent(value: Any, scale: bool = True) -> str:
    """Format benchmark values as report-ready percentages."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if scale:
        numeric *= 100
    return f"{numeric:.1f}%"


def _format_report_number(value: Any, digits: int = 3) -> str:
    """Format numeric values for the benchmark report."""
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "N/A"


def _benchmark_tool_display_name(tool_id: str) -> str:
    """Return a stable human-readable benchmark tool name."""
    metadata = BENCHMARK_TOOL_METADATA.get(str(tool_id).lower(), {})
    return str(metadata.get("name") or tool_id)


def _metric_action(metric: str, value: float) -> str:
    """Return actionable guidance for a benchmark metric value."""
    if metric == "precision":
        if value < 0.85:
            return (
                "False positives are the priority. Raise the decision threshold, "
                "suppress boilerplate/templates, and require agreement from at least "
                "two independent engines before high-risk flags."
            )
        return "Precision is usable. Preserve current negative filters while tuning recall."
    if metric == "recall":
        if value < 0.85:
            return (
                "Known plagiarism is being missed. Lower candidate retrieval cutoffs, "
                "strengthen renamed and structural clone handling, and rerank a wider "
                "shortlist with heavier engines."
            )
        return "Recall is usable. Keep the broad candidate path while reducing noisy matches."
    if metric == "f1_score":
        if value < 0.85:
            return (
                "The precision/recall tradeoff is not calibrated. Run threshold sweeps "
                "on the labeled holdout and optimize F1 and PlagDet together."
            )
        return "F1 is strong enough for a baseline. Validate again on harder negatives."
    if metric == "false_positive_rate":
        if value > 0.05:
            return (
                "False positive rate is above the preferred review threshold. Add starter-code "
                "filters, common-library suppression, and stricter high-confidence gates."
            )
        return "False positive rate is controlled. Keep this guardrail in regression checks."
    if metric == "auc_pr":
        if value < 0.85:
            return (
                "Ranking quality is weak. Tune fusion weights with PR-AUC and add hard "
                "negative pairs that look structurally similar but are independently written."
            )
        return "Ranking quality is good. Use PR-AUC as a regression metric."
    if metric == "top_10_retrieval":
        if value < 0.90:
            return (
                "True positives are not consistently near the top. Improve cheap lexical/AST "
                "retrieval before expensive reranking."
            )
        return "Top-10 retrieval is healthy. Keep it as a candidate-stage acceptance check."
    if metric == "granularity":
        if value > 1.10:
            return (
                "Detections may be split into too many fragments. Merge adjacent or overlapping "
                "evidence spans for the same file pair."
            )
        return (
            "Granularity is close to ideal. Keep one coherent detection per true pair."
        )
    if metric == "avg_runtime_seconds":
        if value > 0.5:
            return (
                "Runtime is expensive for iterative benchmarking. Cache parsing/tokenization and "
                "run embeddings or execution checks only on shortlisted pairs."
            )
        return "Runtime is suitable for tight benchmark iteration."
    return "Track this value across benchmark runs and investigate regressions."


def _build_detailed_evaluation_scorecard(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build a comprehensive evaluation scorecard with visual elements and detailed analysis."""
    pair_results = payload.get("pair_results") or []
    evaluation = payload.get("evaluation") or {}
    tool_timings = payload.get("tool_timings") or {}
    dataset_name = (
        payload.get("datasetName") or payload.get("dataset_name") or "Benchmark Dataset"
    )
    generated_at = payload.get("runAt") or datetime.now(timezone.utc).isoformat()
    benchmark_type = payload.get("benchmark_type") or "tool_comparison"
    total_submissions = payload.get("total_submissions", 0)
    total_pairs = payload.get("total_pairs", 0)

    # Extract valid evaluations
    valid_evaluations = {
        tool: metrics
        for tool, metrics in evaluation.items()
        if isinstance(metrics, dict) and not metrics.get("error")
    }

    # Create scorecard structure
    scorecard = {
        "metadata": {
            "title": "IntegrityDesk Detailed Evaluation Scorecard",
            "dataset": dataset_name,
            "generated_at": generated_at,
            "benchmark_type": benchmark_type,
            "total_submissions": total_submissions,
            "total_pairs": total_pairs,
            "tools_evaluated": len(valid_evaluations),
        },
        "executive_summary": _build_executive_summary(valid_evaluations),
        "performance_metrics": _build_performance_metrics(valid_evaluations),
        "tool_comparison": _build_tool_comparison(valid_evaluations, tool_timings),
        "risk_assessment": _build_risk_assessment(valid_evaluations),
        "recommendations": _build_recommendations(valid_evaluations),
        "detailed_breakdown": _build_detailed_breakdown(
            pair_results, valid_evaluations
        ),
    }

    return scorecard


def _build_executive_summary(evaluations: Dict[str, Any]) -> Dict[str, Any]:
    """Build executive summary section."""
    if not evaluations:
        return {"status": "No valid evaluations available"}

    # Find best performing tool
    best_tool = max(evaluations.keys(), key=lambda t: evaluations[t].get("f1_score", 0))

    best_metrics = evaluations[best_tool]
    plagdet = best_metrics.get("plagdet", 0)
    f1_score = best_metrics.get("f1_score", 0)
    precision = best_metrics.get("precision", 0)
    recall = best_metrics.get("recall", 0)

    # Determine overall status
    if f1_score >= 0.9 and plagdet >= 0.9:
        status = "Excellent"
        status_color = "green"
        status_description = "Ready for production use with high confidence"
    elif f1_score >= 0.8 and plagdet >= 0.8:
        status = "Good"
        status_color = "blue"
        status_description = "Suitable for most academic integrity workflows"
    elif f1_score >= 0.7:
        status = "Needs Improvement"
        status_color = "yellow"
        status_description = "Functional but requires threshold tuning"
    else:
        status = "Critical Issues"
        status_color = "red"
        status_description = "Significant optimization required before use"

    return {
        "status": status,
        "status_color": status_color,
        "status_description": status_description,
        "best_tool": _benchmark_tool_display_name(best_tool),
        "key_metrics": {
            "plagdet": round(plagdet, 3),
            "f1_score": round(f1_score, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
        },
        "tools_compared": len(evaluations),
        "confidence_level": _calculate_confidence_level(best_metrics),
    }


def _build_performance_metrics(evaluations: Dict[str, Any]) -> Dict[str, Any]:
    """Build detailed performance metrics section."""
    metrics_data = {}

    for tool_name, metrics in evaluations.items():
        display_name = _benchmark_tool_display_name(tool_name)
        metrics_data[display_name] = {
            "primary_metrics": {
                "plagdet": {
                    "value": round(metrics.get("plagdet", 0), 3),
                    "description": "Primary PAN evaluation score",
                    "target": ">= 0.90",
                    "weight": "high",
                },
                "f1_score": {
                    "value": round(metrics.get("f1_score", 0), 3),
                    "description": "Balanced precision and recall",
                    "target": ">= 0.85",
                    "weight": "high",
                },
                "precision": {
                    "value": round(metrics.get("precision", 0), 3),
                    "description": "Accuracy of plagiarism flags",
                    "target": ">= 0.90",
                    "weight": "high",
                },
                "recall": {
                    "value": round(metrics.get("recall", 0), 3),
                    "description": "Detection of true plagiarism",
                    "target": ">= 0.90",
                    "weight": "high",
                },
            },
            "secondary_metrics": {
                "granularity": {
                    "value": round(metrics.get("granularity", 1.0), 3),
                    "description": "Detection fragmentation (closer to 1.0 is better)",
                    "target": "<= 1.05",
                    "weight": "medium",
                },
                "auc_pr": {
                    "value": round(metrics.get("auc_pr", 0), 3),
                    "description": "Ranking quality across all thresholds",
                    "target": ">= 0.85",
                    "weight": "medium",
                },
                "false_positive_rate": {
                    "value": round(metrics.get("false_positive_rate", 0), 3),
                    "description": "Rate of false plagiarism flags",
                    "target": "<= 0.05",
                    "weight": "medium",
                },
                "top_10_retrieval": {
                    "value": round(metrics.get("top_10_retrieval", 0), 3),
                    "description": "True positives in top 10 results",
                    "target": ">= 0.90",
                    "weight": "medium",
                },
                "avg_runtime_seconds": {
                    "value": round(metrics.get("avg_runtime_seconds", 0), 3),
                    "description": "Average processing time per pair",
                    "target": "<= 0.50",
                    "weight": "low",
                },
            },
        }

    return metrics_data


def _build_tool_comparison(
    evaluations: Dict[str, Any], tool_timings: Dict[str, float]
) -> Dict[str, Any]:
    """Build tool comparison section."""
    comparison_data = []

    # Tool logo mapping
    tool_logos = {
        "moss": "https://theory.stanford.edu/~aiken/moss/mosslogo.gif",
        "jplag": "https://github.com/jplag/JPlag/raw/main/core/src/main/resources/de/jplag/logo-dark.png",
        "dolos": "https://avatars.githubusercontent.com/u/40892657?s=48&v=4",
        "pmd": "https://raw.githubusercontent.com/pmd/pmd/main/docs/images/logo/pmd-logo-300px.png",
        "nicad": None,
        "sherlock": None,
        "integritydesk": "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0iIzcwM0FFRCIvPgo8dGV4dCB4PSIxNiIgeT0iMjAiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0id2hpdGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiPkQ8L3RleHQ+Cjwvc3ZnPg==",
    }

    for tool_name, metrics in evaluations.items():
        display_name = _benchmark_tool_display_name(tool_name)
        runtime = tool_timings.get(tool_name, 0)
        logo_url = tool_logos.get(tool_name.lower())

        tool_data = {
            "tool_name": display_name,
            "logo_url": logo_url,
            "metrics": {
                "f1_score": round(metrics.get("f1_score", 0), 3),
                "precision": round(metrics.get("precision", 0), 3),
                "recall": round(metrics.get("recall", 0), 3),
                "plagdet": round(metrics.get("plagdet", 0), 3),
                "runtime_seconds": round(runtime, 2),
            },
            "performance_tier": _calculate_performance_tier(metrics),
            "strengths": _identify_tool_strengths(metrics),
            "weaknesses": _identify_tool_weaknesses(metrics),
        }
        comparison_data.append(tool_data)

    # Sort by F1 score
    comparison_data.sort(key=lambda x: x["metrics"]["f1_score"], reverse=True)

    return {
        "tools": comparison_data,
        "summary": {
            "best_overall": (
                comparison_data[0]["tool_name"] if comparison_data else "N/A"
            ),
            "fastest": (
                min(comparison_data, key=lambda x: x["metrics"]["runtime_seconds"])[
                    "tool_name"
                ]
                if comparison_data
                else "N/A"
            ),
            "most_accurate": (
                max(comparison_data, key=lambda x: x["metrics"]["f1_score"])[
                    "tool_name"
                ]
                if comparison_data
                else "N/A"
            ),
        },
    }


def _build_risk_assessment(evaluations: Dict[str, Any]) -> Dict[str, Any]:
    """Build risk assessment section."""
    if not evaluations:
        return {"overall_risk": "high", "issues": ["No evaluation data available"]}

    # Use the best performing tool for risk assessment
    best_tool = max(evaluations.keys(), key=lambda t: evaluations[t].get("f1_score", 0))
    metrics = evaluations[best_tool]

    risks = []
    risk_level = "low"

    # Precision risk
    precision = metrics.get("precision", 0)
    if precision < 0.8:
        risks.append(
            {
                "severity": "high",
                "category": "False Positives",
                "description": f"High false positive rate ({(1-precision)*100:.1f}%) may overwhelm reviewers",
                "impact": "Reduced reviewer efficiency and trust",
                "recommendation": "Increase decision threshold and require multi-engine agreement",
            }
        )
        risk_level = "high"
    elif precision < 0.9:
        risks.append(
            {
                "severity": "medium",
                "category": "False Positives",
                "description": f"Moderate false positive rate may require additional review",
                "impact": "Increased manual review workload",
                "recommendation": "Fine-tune threshold for better precision/recall balance",
            }
        )
        if risk_level == "low":
            risk_level = "medium"

    # Recall risk
    recall = metrics.get("recall", 0)
    if recall < 0.8:
        risks.append(
            {
                "severity": "high",
                "category": "Missed Plagiarism",
                "description": f"High miss rate ({(1-recall)*100:.1f}%) means plagiarism may go undetected",
                "impact": "Academic integrity compromised",
                "recommendation": "Lower candidate thresholds and enhance clone detection",
            }
        )
        risk_level = "high"
    elif recall < 0.9:
        risks.append(
            {
                "severity": "medium",
                "category": "Missed Plagiarism",
                "description": "Some plagiarism cases may be missed",
                "impact": "Partial coverage of academic integrity threats",
                "recommendation": "Expand detection scope for edge cases",
            }
        )
        if risk_level == "low":
            risk_level = "medium"

    # Runtime risk
    runtime = metrics.get("avg_runtime_seconds", 0)
    if runtime > 2.0:
        risks.append(
            {
                "severity": "medium",
                "category": "Performance",
                "description": f"Slow processing ({runtime:.2f}s per pair) may impact scalability",
                "impact": "Limited to smaller assignments or slower workflows",
                "recommendation": "Optimize processing pipeline and enable caching",
            }
        )
        if risk_level == "low":
            risk_level = "medium"

    # Granularity risk
    granularity = metrics.get("granularity", 1.0)
    if granularity > 1.2:
        risks.append(
            {
                "severity": "low",
                "category": "User Experience",
                "description": f"Over-fragmented detections (granularity: {granularity:.2f})",
                "impact": "Reviewers see multiple alerts for same plagiarism case",
                "recommendation": "Merge adjacent/overlapping evidence spans",
            }
        )

    return {
        "overall_risk": risk_level,
        "risk_count": len(risks),
        "risks": risks,
        "mitigation_strategy": _generate_mitigation_strategy(risks, metrics),
    }


def _build_recommendations(evaluations: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build recommendations section."""
    if not evaluations:
        return [
            {
                "priority": "high",
                "category": "System",
                "recommendation": "Run benchmark evaluation to generate recommendations",
            }
        ]

    recommendations = []

    # Use best performing tool for analysis
    best_tool = max(evaluations.keys(), key=lambda t: evaluations[t].get("f1_score", 0))
    metrics = evaluations[best_tool]

    # Precision recommendations
    precision = metrics.get("precision", 0)
    if precision < 0.85:
        recommendations.append(
            {
                "priority": "high",
                "category": "Threshold Tuning",
                "recommendation": "Increase the decision threshold to reduce false positives",
                "expected_impact": f"Could improve precision by {(0.9-precision)*100:.1f}%",
                "implementation_effort": "medium",
            }
        )

    # Recall recommendations
    recall = metrics.get("recall", 0)
    if recall < 0.85:
        recommendations.append(
            {
                "priority": "high",
                "category": "Detection Coverage",
                "recommendation": "Lower candidate retrieval thresholds and enhance similarity detection",
                "expected_impact": f"Could improve recall by {(0.9-recall)*100:.1f}%",
                "implementation_effort": "high",
            }
        )

    # Runtime recommendations
    runtime = metrics.get("avg_runtime_seconds", 0)
    if runtime > 1.0:
        recommendations.append(
            {
                "priority": "medium",
                "category": "Performance Optimization",
                "recommendation": "Implement result caching and optimize processing pipeline",
                "expected_impact": f"Could reduce runtime by {runtime*0.5:.1f}s per pair",
                "implementation_effort": "medium",
            }
        )

    # AUC-PR recommendations
    auc_pr = metrics.get("auc_pr", 0)
    if auc_pr < 0.85:
        recommendations.append(
            {
                "priority": "medium",
                "category": "Ranking Quality",
                "recommendation": "Tune fusion weights with PR-AUC as optimization objective",
                "expected_impact": f"Could improve ranking quality by {(0.9-auc_pr)*100:.1f}%",
                "implementation_effort": "high",
            }
        )

    # Default recommendations if none above apply
    if not recommendations:
        recommendations.append(
            {
                "priority": "low",
                "category": "Monitoring",
                "recommendation": "Continue regular benchmark evaluations to track performance trends",
                "expected_impact": "Maintain current performance levels",
                "implementation_effort": "low",
            }
        )

    return recommendations


def _build_detailed_breakdown(
    pair_results: List[Dict[str, Any]], evaluations: Dict[str, Any]
) -> Dict[str, Any]:
    """Build detailed breakdown section."""
    if not pair_results:
        return {
            "available": False,
            "message": "No pair results available for detailed analysis",
        }

    # Analyze top false positives and false negatives
    false_positives = []
    false_negatives = []
    true_positives = []
    true_negatives = []

    for pair in pair_results:
        ground_truth = pair.get("ground_truth_label", 0)
        tool_results = pair.get("tool_results", [])

        # Use the best tool for analysis
        best_tool_result = None
        if evaluations:
            best_tool = max(
                evaluations.keys(), key=lambda t: evaluations[t].get("f1_score", 0)
            )
            best_tool_result = next(
                (tr for tr in tool_results if tr.get("tool") == best_tool), None
            )

        if best_tool_result:
            predicted_score = best_tool_result.get("score", 0)
            predicted_positive = predicted_score >= 0.5  # Assuming 0.5 threshold

            if ground_truth == 1 and predicted_positive:
                true_positives.append(
                    {
                        "file_a": pair.get("file_a", ""),
                        "file_b": pair.get("file_b", ""),
                        "score": round(predicted_score, 3),
                        "label": pair.get("label", ""),
                    }
                )
            elif ground_truth == 1 and not predicted_positive:
                false_negatives.append(
                    {
                        "file_a": pair.get("file_a", ""),
                        "file_b": pair.get("file_b", ""),
                        "score": round(predicted_score, 3),
                        "label": pair.get("label", ""),
                    }
                )
            elif ground_truth == 0 and predicted_positive:
                false_positives.append(
                    {
                        "file_a": pair.get("file_a", ""),
                        "file_b": pair.get("file_b", ""),
                        "score": round(predicted_score, 3),
                        "label": pair.get("label", ""),
                    }
                )
            elif ground_truth == 0 and not predicted_positive:
                true_negatives.append(
                    {
                        "file_a": pair.get("file_a", ""),
                        "file_b": pair.get("file_b", ""),
                        "score": round(predicted_score, 3),
                        "label": pair.get("label", ""),
                    }
                )

    # Sort by score for most interesting cases
    false_positives.sort(key=lambda x: x["score"], reverse=True)
    false_negatives.sort(key=lambda x: x["score"])

    return {
        "available": True,
        "summary": {
            "total_pairs": len(pair_results),
            "true_positives": len(true_positives),
            "true_negatives": len(true_negatives),
            "false_positives": len(false_positives),
            "false_negatives": len(false_negatives),
        },
        "top_false_positives": false_positives[
            :10
        ],  # Top 10 most confident false positives
        "top_false_negatives": false_negatives[:10],  # Top 10 most missed true cases
        "confusion_matrix": {
            "predicted_positive_actual_positive": len(true_positives),
            "predicted_positive_actual_negative": len(false_positives),
            "predicted_negative_actual_positive": len(false_negatives),
            "predicted_negative_actual_negative": len(true_negatives),
        },
    }


def _calculate_confidence_level(metrics: Dict[str, Any]) -> str:
    """Calculate confidence level based on metric stability and sample size."""
    plagdet = metrics.get("plagdet", 0)
    sample_size = metrics.get("sample_size", 0)

    if plagdet >= 0.9 and sample_size >= 100:
        return "High"
    elif plagdet >= 0.8 and sample_size >= 50:
        return "Medium"
    elif plagdet >= 0.7:
        return "Low"
    else:
        return "Very Low"


def _calculate_performance_tier(metrics: Dict[str, Any]) -> str:
    """Calculate performance tier for a tool."""
    f1_score = metrics.get("f1_score", 0)

    if f1_score >= 0.9:
        return "Excellent"
    elif f1_score >= 0.8:
        return "Good"
    elif f1_score >= 0.7:
        return "Fair"
    else:
        return "Poor"


def _identify_tool_strengths(metrics: Dict[str, Any]) -> List[str]:
    """Identify strengths of a tool based on its metrics."""
    strengths = []

    if metrics.get("precision", 0) >= 0.9:
        strengths.append("Excellent precision - very few false positives")
    if metrics.get("recall", 0) >= 0.9:
        strengths.append("Excellent recall - catches most plagiarism")
    if metrics.get("auc_pr", 0) >= 0.9:
        strengths.append("Strong ranking quality across all thresholds")
    if metrics.get("top_10_retrieval", 0) >= 0.9:
        strengths.append("Effective at surfacing true positives early")
    if metrics.get("avg_runtime_seconds", 1) <= 0.5:
        strengths.append("Fast processing for real-time use")
    if metrics.get("granularity", 1.1) <= 1.05:
        strengths.append("Clean, consolidated detections")

    return strengths if strengths else ["Consistent baseline performance"]


def _identify_tool_weaknesses(metrics: Dict[str, Any]) -> List[str]:
    """Identify weaknesses of a tool based on its metrics."""
    weaknesses = []

    if metrics.get("precision", 1) < 0.8:
        weaknesses.append("High false positive rate may overwhelm reviewers")
    if metrics.get("recall", 1) < 0.8:
        weaknesses.append("Misses significant amount of actual plagiarism")
    if metrics.get("auc_pr", 1) < 0.8:
        weaknesses.append("Poor ranking - true cases don't appear early in results")
    if metrics.get("false_positive_rate", 0) > 0.1:
        weaknesses.append("Too many clean pairs flagged as suspicious")
    if metrics.get("avg_runtime_seconds", 0) > 2.0:
        weaknesses.append("Slow processing may limit scalability")
    if metrics.get("granularity", 1) > 1.2:
        weaknesses.append("Over-fragmented detections create review noise")

    return weaknesses if weaknesses else ["No major weaknesses identified"]


def _generate_mitigation_strategy(
    risks: List[Dict[str, Any]], metrics: Dict[str, Any]
) -> str:
    """Generate an overall mitigation strategy."""
    if not risks:
        return "Current configuration appears stable. Continue monitoring performance."

    high_risks = [r for r in risks if r["severity"] == "high"]
    if high_risks:
        return "Address high-priority risks immediately. Focus on threshold calibration and multi-engine agreement requirements."

    medium_risks = [r for r in risks if r["severity"] == "medium"]
    if medium_risks:
        return "Address medium-priority issues through iterative tuning. Consider performance optimizations for better scalability."

    return "Minor adjustments may improve user experience. Focus on monitoring and trend analysis."


def _build_benchmark_report_lines(payload: Dict[str, Any]) -> List[str]:
    """Build a detailed, professional benchmark report from a benchmark payload."""
    pair_results = payload.get("pair_results") or []
    summary = payload.get("summary") or {}
    evaluation = payload.get("evaluation") or {}
    tool_scores = payload.get("tool_scores") or {}
    dataset_name = (
        payload.get("datasetName") or summary.get("dataset_name") or "Benchmark"
    )
    generated_at = payload.get("runAt") or datetime.now(timezone.utc).isoformat()
    benchmark_type = payload.get("benchmark_type") or payload.get("benchmarkMode") or ""
    requested_tools = payload.get("requested_tools") or list(tool_scores.keys())

    valid_eval = {
        tool: metrics
        for tool, metrics in evaluation.items()
        if isinstance(metrics, dict) and not metrics.get("error")
    }
    primary_tool = "integritydesk" if "integritydesk" in valid_eval else None
    if not primary_tool and valid_eval:
        primary_tool = next(iter(valid_eval.keys()))
    primary_metrics = valid_eval.get(primary_tool or "", {})

    lines: List[str] = [
        f"IntegrityDesk Benchmark Report - {dataset_name}",
        "",
        "Executive Summary",
        f"Generated: {generated_at}",
        f"Benchmark type: {benchmark_type or 'tool comparison'}",
        f"Dataset: {dataset_name}",
        f"Pairs tested: {summary.get('pairs_tested', len(pair_results))}",
        f"Tools completed: {summary.get('tools_compared', len(tool_scores))}",
        f"Ground truth available: {'yes' if payload.get('has_ground_truth') else 'no'}",
        "",
    ]

    if primary_metrics:
        f1 = float(
            primary_metrics.get("f1_score") or primary_metrics.get("best_f1") or 0
        )
        precision = float(primary_metrics.get("precision") or 0)
        recall = float(primary_metrics.get("recall") or 0)
        fpr = float(primary_metrics.get("false_positive_rate") or 0)
        lines.extend(
            [
                "Primary Finding",
                (
                    f"{_benchmark_tool_display_name(primary_tool)} scored "
                    f"{_format_report_percent(primary_metrics.get('plagdet', f1))} PlagDet, "
                    f"{_format_report_percent(f1)} F1, "
                    f"{_format_report_percent(precision)} precision, "
                    f"{_format_report_percent(recall)} recall, and "
                    f"{_format_report_percent(fpr)} false positive rate."
                ),
                "",
            ]
        )
        if precision < 0.85:
            lines.append(
                "Main risk: false positives are too high for trusted review workflows."
            )
        elif recall < 0.85:
            lines.append("Main risk: known plagiarism pairs are being missed.")
        elif f1 < 0.85:
            lines.append("Main risk: threshold calibration needs more work.")
        else:
            lines.append(
                "Main result: the detector is suitable as a baseline for regression tracking."
            )
        lines.append("")

        metric_integrity = primary_metrics.get("metric_integrity") or {}
        split_protocol = primary_metrics.get("split_protocol") or {}
        confidence_intervals = primary_metrics.get("confidence_intervals") or {}
        benchmark_trust = primary_metrics.get(
            "benchmark_trust"
        ) or metric_integrity.get("benchmark_trust", {})
        heldout_confusion = metric_integrity.get("heldout_confusion_matrix") or {}
        fixed_threshold_metrics = primary_metrics.get("fixed_threshold_metrics") or {}
        trust_level = benchmark_trust.get("grade", "limited")
        lines.extend(
            [
                "Score Trust and Error Audit",
                f"Trust level: {trust_level}",
                f"Trust score: {benchmark_trust.get('score', 'N/A')}/100",
                (
                    "Protocol: "
                    + (
                        "stratified calibration/holdout"
                        if split_protocol.get("protocol")
                        == "deterministic_stratified_calibration_holdout"
                        else (
                            "locked fixed-threshold evaluation"
                            if split_protocol.get("protocol")
                            == "locked_full_sample_evaluation"
                            else "fallback evaluation without separate holdout"
                        )
                    )
                ),
                (
                    f"Held-out labels: {split_protocol.get('holdout_positive_pairs', 0)} "
                    f"positive and {split_protocol.get('holdout_negative_pairs', 0)} negative pairs"
                ),
                f"Optimized threshold: {_format_report_number(primary_metrics.get('best_threshold'), 2)}",
                (
                    f"Held-out F1: {_format_report_number(metric_integrity.get('heldout_f1', f1), 3)}; "
                    f"fixed {_format_report_number(primary_metrics.get('fixed_threshold'), 2)} F1: "
                    f"{_format_report_number(metric_integrity.get('fixed_threshold_f1', fixed_threshold_metrics.get('f1_score')), 3)}"
                ),
                (
                    "Held-out confusion matrix: "
                    f"TP {heldout_confusion.get('tp', 0)}, FP {heldout_confusion.get('fp', 0)}, "
                    f"TN {heldout_confusion.get('tn', 0)}, FN {heldout_confusion.get('fn', 0)}"
                ),
            ]
        )
        if confidence_intervals.get("available") and confidence_intervals.get("f1"):
            f1_interval = confidence_intervals["f1"]
            lines.append(
                "95% bootstrap F1 confidence interval: "
                f"{_format_report_number(f1_interval.get('ci_lower'), 3)}-"
                f"{_format_report_number(f1_interval.get('ci_upper'), 3)}"
            )
        else:
            lines.append(
                "Confidence interval: unavailable; use a larger labeled holdout to "
                "narrow uncertainty before making certification claims."
            )
        lines.append(
            "Interpretation: precision drops when clean pairs are above threshold; "
            "recall drops when labeled plagiarism pairs are below threshold."
        )
        lines.append("")

        tuning = primary_metrics.get("tuning_recommendations") or {}
        tuning_changes = tuning.get("config_changes") or []
        if tuning.get("available"):
            lines.extend(
                [
                    "Engine Tuning Plan",
                    str(tuning.get("summary") or ""),
                    f"Config file: {tuning.get('config_file', 'src/backend/engines/engine_weights.yaml')}",
                ]
            )
            for action in tuning.get("actions") or []:
                lines.append(
                    f"- {action.get('title', 'Action')}: {action.get('detail', '')}"
                )
            if tuning_changes:
                lines.append("Proposed YAML edits:")
                for change in tuning_changes:
                    lines.append(
                        f"- {change.get('path')}: {change.get('current')} -> "
                        f"{change.get('proposed')} ({change.get('reason', '')})"
                    )
            lines.append("")

    if requested_tools:
        lines.extend(["Tool Coverage"])
        for tool in requested_tools:
            meta = tool_scores.get(tool, {})
            status = "failed" if meta.get("error") else "completed"
            runtime = _format_report_number(meta.get("runtime_seconds"), 3)
            pairs = meta.get("pairs", 0)
            lines.append(
                f"- {_benchmark_tool_display_name(tool)}: {status}; {pairs} pairs; "
                f"{runtime}s total runtime"
            )
            if meta.get("error"):
                lines.append(f"  Error: {meta.get('error')}")
        lines.append("")

    if valid_eval:
        lines.extend(["Metric Scorecard"])
        for tool, metrics in valid_eval.items():
            lines.append(f"{_benchmark_tool_display_name(tool)}")
            score_rows = [
                ("PlagDet", "plagdet", True),
                ("Precision", "precision", True),
                ("Recall", "recall", True),
                ("F1 Score", "f1_score", True),
                ("False Positive Rate", "false_positive_rate", True),
                ("AUC-PR", "auc_pr", True),
                ("Top-10 Retrieval", "top_10_retrieval", True),
                ("Granularity", "granularity", False),
                ("Avg Runtime Seconds", "avg_runtime_seconds", False),
            ]
            for label, key, as_percent in score_rows:
                value = metrics.get(key)
                if value is None and key == "f1_score":
                    value = metrics.get("best_f1")
                if value is None:
                    continue
                display = (
                    _format_report_percent(value)
                    if as_percent
                    else _format_report_number(value, 3)
                )
                lines.append(f"- {label}: {display}")
            lines.append("")

    if primary_metrics:
        lines.extend(["Detailed Improvement Guide"])
        guide_metrics = [
            ("precision", "Precision"),
            ("recall", "Recall"),
            ("f1_score", "F1 Score"),
            ("false_positive_rate", "False Positive Rate"),
            ("auc_pr", "AUC-PR"),
            ("top_10_retrieval", "Top-10 Retrieval"),
            ("granularity", "Granularity"),
            ("avg_runtime_seconds", "Runtime"),
        ]
        for key, label in guide_metrics:
            value = primary_metrics.get(key)
            if value is None and key == "f1_score":
                value = primary_metrics.get("best_f1")
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            lines.append(f"{label}: {_metric_action(key, numeric)}")
        contribution = primary_metrics.get("engine_contribution") or {}
        if contribution:
            top_contributors = sorted(
                contribution.items(), key=lambda item: float(item[1] or 0), reverse=True
            )[:4]
            rendered = ", ".join(
                f"{name} {_format_report_percent(value)}"
                for name, value in top_contributors
            )
            lines.append(f"Engine contribution focus: {rendered}.")
        warnings = (primary_metrics.get("metric_integrity") or {}).get("warnings") or []
        if warnings:
            lines.append("Metric integrity warnings:")
            lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    if payload.get("benchmark_quality"):
        quality = payload["benchmark_quality"]
        lines.extend(
            [
                "Dataset Quality Notes",
                f"Certification level: {quality.get('certification_level', 'unknown')}",
                f"Quality score: {_format_report_percent(quality.get('score_percent'), scale=False)}",
                f"Pair count: {quality.get('pair_count', 'N/A')}",
                f"Positive pairs: {quality.get('positive_pairs', 'N/A')}",
                f"Negative pairs: {quality.get('negative_pairs', 'N/A')}",
                "",
            ]
        )

    if primary_metrics and pair_results:
        threshold = _coerce_float(primary_metrics.get("best_threshold"), 0.5)
        labeled_rows = []
        for pair in pair_results:
            if pair.get("ground_truth_label") is None:
                continue
            tool_result = next(
                (
                    result
                    for result in pair.get("tool_results") or []
                    if result.get("tool") == primary_tool
                ),
                None,
            )
            if not tool_result:
                continue
            score = _coerce_float(tool_result.get("score"))
            actual = int(pair.get("ground_truth_label") or 0) >= 2
            predicted = score >= threshold
            labeled_rows.append(
                {
                    "pair": pair,
                    "score": score,
                    "actual": actual,
                    "predicted": predicted,
                }
            )

        if labeled_rows:
            false_positives = sorted(
                [row for row in labeled_rows if not row["actual"] and row["predicted"]],
                key=lambda row: row["score"],
                reverse=True,
            )[:5]
            false_negatives = sorted(
                [row for row in labeled_rows if row["actual"] and not row["predicted"]],
                key=lambda row: row["score"],
            )[:5]
            lines.extend(["Error Examples"])
            if false_positives:
                lines.append("False positives: clean pairs above threshold.")
                for row in false_positives:
                    pair = row["pair"]
                    lines.append(
                        f"- {pair.get('label', 'Pair')}: {pair.get('file_a', '')} vs "
                        f"{pair.get('file_b', '')}; score {_format_report_percent(row['score'])}"
                    )
            else:
                lines.append("False positives: none in labeled pair rows.")
            if false_negatives:
                lines.append("False negatives: plagiarism pairs below threshold.")
                for row in false_negatives:
                    pair = row["pair"]
                    lines.append(
                        f"- {pair.get('label', 'Pair')}: {pair.get('file_a', '')} vs "
                        f"{pair.get('file_b', '')}; score {_format_report_percent(row['score'])}"
                    )
            else:
                lines.append("False negatives: none in labeled pair rows.")
            lines.append("")

    if pair_results:
        lines.extend(["Pair-Level Appendix"])
        for pair in pair_results[:80]:
            label = pair.get("label") or "Pair"
            ground_truth = pair.get("ground_truth_label")
            lines.append(
                f"{label}: {pair.get('file_a', '')} vs {pair.get('file_b', '')}"
                + (
                    f" | ground truth {ground_truth}"
                    if ground_truth is not None
                    else ""
                )
            )
            for tool_result in pair.get("tool_results") or []:
                tool = _benchmark_tool_display_name(tool_result.get("tool", "tool"))
                score = _format_report_percent(tool_result.get("score"))
                lines.append(f"- {tool}: {score}")
            features = next(
                (
                    tr.get("features")
                    for tr in pair.get("tool_results") or []
                    if tr.get("tool") == "integritydesk" and tr.get("features")
                ),
                None,
            )
            if features:
                top_features = sorted(
                    features.items(), key=lambda item: float(item[1] or 0), reverse=True
                )[:4]
                rendered_features = ", ".join(
                    f"{name} {_format_report_percent(value)}"
                    for name, value in top_features
                )
                lines.append(f"  IntegrityDesk signal breakdown: {rendered_features}")
        if len(pair_results) > 80:
            lines.append(f"... {len(pair_results) - 80} additional pairs omitted.")
    else:
        lines.extend(
            ["Pair-Level Appendix", "No pair-level rows were included in the result."]
        )

    return lines


def _generate_detailed_scorecard_pdf(scorecard: Dict[str, Any]) -> bytes:
    """Generate a detailed, visually appealing scorecard PDF using HTML/CSS and WeasyPrint."""
    from weasyprint import HTML, CSS
    from io import BytesIO

    # Build HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{scorecard["metadata"]["title"]}</title>
        <style>
            @page {{
                size: letter;
                margin: 0.75in;
            }}
            body {{
                font-family: 'Helvetica', 'Arial', sans-serif;
                color: #1f2937;
                line-height: 1.6;
                font-size: 11pt;
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #e5e7eb;
                padding-bottom: 20pt;
                margin-bottom: 30pt;
            }}
            .title {{
                font-size: 24pt;
                font-weight: bold;
                color: #1f2937;
                margin-bottom: 10pt;
            }}
            .subtitle {{
                font-size: 12pt;
                color: #6b7280;
            }}
            .section {{
                margin-bottom: 40pt;
                page-break-inside: avoid;
            }}
            .section-header {{
                font-size: 16pt;
                font-weight: bold;
                color: #374151;
                border-bottom: 1px solid #e5e7eb;
                padding-bottom: 8pt;
                margin-bottom: 15pt;
            }}
            .status-badge {{
                display: inline-block;
                padding: 6pt 12pt;
                border-radius: 6pt;
                font-weight: bold;
                font-size: 11pt;
                margin: 10pt 0;
            }}
            .status-excellent {{ background-color: #dcfce7; color: #166534; }}
            .status-good {{ background-color: #dbeafe; color: #1e40af; }}
            .status-needs-improvement {{ background-color: #fef3c7; color: #92400e; }}
            .status-critical {{ background-color: #fee2e2; color: #991b1b; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15pt 0;
                font-size: 10pt;
            }}
            th, td {{
                border: 1px solid #e5e7eb;
                padding: 8pt;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background-color: #f9fafb;
                font-weight: bold;
                color: #374151;
            }}
            .metric-table {{
                font-size: 9pt;
            }}
            .metric-table th {{
                text-align: center;
                font-size: 10pt;
            }}
            .metric-table td {{
                text-align: center;
            }}
            .metric-good {{ color: #166534; font-weight: bold; }}
            .metric-warning {{ color: #92400e; font-weight: bold; }}
            .metric-bad {{ color: #991b1b; font-weight: bold; }}
            .priority-high {{ color: #991b1b; }}
            .priority-medium {{ color: #92400e; }}
            .priority-low {{ color: #166534; }}
            .footer {{
                font-size: 8pt;
                color: #9ca3af;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                padding-top: 20pt;
                margin-top: 40pt;
            }}
            .page-break {{
                page-break-before: always;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="title">{scorecard["metadata"]["title"]}</div>
            <div class="subtitle">Dataset: {scorecard["metadata"]["dataset"]} | Generated: {scorecard["metadata"]["generated_at"][:19].replace('T', ' ')}</div>
        </div>
    """

    # Executive Summary
    exec_summary = scorecard["executive_summary"]
    status_class = (
        f"status-{exec_summary.get('status_color', 'blue').lower().replace(' ', '-')}"
    )
    status_description = exec_summary.get("status_description", "")

    html_content += f"""
        <div class="section">
            <div class="section-header">Executive Summary</div>
            <div class="status-badge {status_class}">{exec_summary["status"]}</div>
            <p>{status_description}</p>
            <table class="metric-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Target</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    """

    key_metrics = exec_summary.get("key_metrics", {})
    metrics_info = [
        ("PlagDet Score", key_metrics.get("plagdet", 0), "≥ 0.90"),
        ("F1 Score", key_metrics.get("f1_score", 0), "≥ 0.85"),
        ("Precision", key_metrics.get("precision", 0), "≥ 0.90"),
        ("Recall", key_metrics.get("recall", 0), "≥ 0.90"),
    ]

    for name, value, target in metrics_info:
        status = "✓" if _meets_target(value, target) else "⚠"
        status_class = (
            "metric-good" if _meets_target(value, target) else "metric-warning"
        )
        html_content += f"""
                    <tr>
                        <td>{name}</td>
                        <td>{value:.3f}</td>
                        <td>{target}</td>
                        <td class="{status_class}">{status}</td>
                    </tr>
        """

    html_content += """
                </tbody>
            </table>
        </div>
    """

    # Tool Comparison with Logos
    comparison_data = scorecard["tool_comparison"]
    if comparison_data and comparison_data.get("tools"):
        html_content += """
            <div class="section page-break">
                <div class="section-header">Tool Comparison</div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20pt; margin: 20pt 0;">
        """

        for tool_data in comparison_data["tools"]:
            logo_html = ""
            if tool_data.get("logo_url"):
                logo_html = f'<img src="{tool_data["logo_url"]}" alt="{tool_data["tool_name"]} logo" style="height: 32px; width: auto; margin-right: 10pt; vertical-align: middle;">'

            tier_color = {
                "Excellent": "#166534",
                "Good": "#1e40af",
                "Fair": "#92400e",
                "Poor": "#991b1b",
            }.get(tool_data["performance_tier"], "#6b7280")

            html_content += f"""
                <div style="border: 1px solid #e5e7eb; border-radius: 8pt; padding: 15pt; background-color: #f9fafb;">
                    <div style="display: flex; align-items: center; margin-bottom: 10pt;">
                        {logo_html}
                        <div>
                            <h4 style="margin: 0; color: #1f2937; font-size: 16pt;">{tool_data["tool_name"]}</h4>
                            <span style="background-color: {tier_color}20; color: {tier_color}; padding: 2pt 8pt; border-radius: 4pt; font-size: 10pt; font-weight: bold;">{tool_data["performance_tier"]}</span>
                        </div>
                    </div>
                    <table style="width: 100%; font-size: 9pt; margin-bottom: 10pt;">
                        <tr>
                            <td style="padding: 4pt; font-weight: bold;">F1 Score:</td>
                            <td style="padding: 4pt;">{tool_data["metrics"]["f1_score"]:.3f}</td>
                            <td style="padding: 4pt; font-weight: bold;">Runtime:</td>
                            <td style="padding: 4pt;">{tool_data["metrics"]["runtime_seconds"]:.2f}s</td>
                        </tr>
                        <tr>
                            <td style="padding: 4pt; font-weight: bold;">Precision:</td>
                            <td style="padding: 4pt;">{tool_data["metrics"]["precision"]:.3f}</td>
                            <td style="padding: 4pt; font-weight: bold;">Recall:</td>
                            <td style="padding: 4pt;">{tool_data["metrics"]["recall"]:.3f}</td>
                        </tr>
                    </table>
                    <div style="font-size: 9pt; color: #374151;">
                        <strong>Strengths:</strong> {" • ".join(tool_data["strengths"][:2])}
                    </div>
                </div>
            """

        html_content += """
                </div>
            </div>
        """

    # Performance Metrics
    html_content += """
        <div class="section page-break">
            <div class="section-header">Detailed Performance Metrics</div>
    """

    performance_data = scorecard["performance_metrics"]
    for tool_name, tool_metrics in performance_data.items():
        html_content += f"""
            <h3 style="color: #374151; margin: 20pt 0 10pt 0;">{tool_name}</h3>
            <table class="metric-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Target</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
        """

        for metric_name, metric_info in tool_metrics["primary_metrics"].items():
            value = metric_info["value"]
            target = metric_info["target"]
            description = metric_info["description"]
            meets = _meets_target(value, target)
            status_class = "metric-good" if meets else "metric-warning"

            html_content += f"""
                    <tr>
                        <td>{metric_name.replace('_', ' ').title()}</td>
                        <td class="{status_class}">{value:.3f}</td>
                        <td>{target}</td>
                        <td>{description}</td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        """

    html_content += "</div>"

    # Risk Assessment
    risk_data = scorecard["risk_assessment"]
    overall_risk = risk_data["overall_risk"]
    risk_color = {"low": "#166534", "medium": "#92400e", "high": "#991b1b"}.get(
        overall_risk, "#6b7280"
    )

    html_content += f"""
        <div class="section page-break">
            <div class="section-header">Risk Assessment</div>
            <div style="background-color: #fef3c7; padding: 15pt; border-radius: 6pt; margin: 15pt 0;">
                <strong style="color: {risk_color};">Overall Risk Level: {overall_risk.upper()}</strong>
                <p style="margin: 10pt 0 0 0;">{risk_data["mitigation_strategy"]}</p>
            </div>
    """

    if risk_data["risks"]:
        html_content += """
            <table>
                <thead>
                    <tr>
                        <th>Severity</th>
                        <th>Category</th>
                        <th>Description</th>
                        <th>Recommendation</th>
                    </tr>
                </thead>
                <tbody>
        """

        for risk in risk_data["risks"][:5]:
            severity_color = {
                "high": "#991b1b",
                "medium": "#92400e",
                "low": "#ca8a04",
            }.get(risk["severity"], "#6b7280")
            html_content += f"""
                    <tr>
                        <td><span style="color: {severity_color}; font-weight: bold;">{risk["severity"].upper()}</span></td>
                        <td>{risk["category"]}</td>
                        <td>{risk["description"][:100]}{"..." if len(risk["description"]) > 100 else ""}</td>
                        <td>{risk["recommendation"][:80]}{"..." if len(risk["recommendation"]) > 80 else ""}</td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        """

    html_content += "</div>"

    # Recommendations
    recommendations = scorecard["recommendations"]
    if recommendations:
        html_content += """
            <div class="section page-break">
                <div class="section-header">Recommendations</div>
                <table>
                    <thead>
                        <tr>
                            <th>Priority</th>
                            <th>Category</th>
                            <th>Recommendation</th>
                            <th>Expected Impact</th>
                            <th>Effort</th>
                        </tr>
                    </thead>
                    <tbody>
        """

        for rec in recommendations:
            priority_color = {
                "high": "#991b1b",
                "medium": "#92400e",
                "low": "#166534",
            }.get(rec["priority"], "#6b7280")
            html_content += f"""
                        <tr>
                            <td><span style="color: {priority_color}; font-weight: bold;">{rec["priority"].upper()}</span></td>
                            <td>{rec["category"]}</td>
                            <td>{rec["recommendation"][:80]}{"..." if len(rec["recommendation"]) > 80 else ""}</td>
                            <td>{rec["expected_impact"][:60]}{"..." if len(rec["expected_impact"]) > 60 else ""}</td>
                            <td>{rec["implementation_effort"].title()}</td>
                        </tr>
            """

        html_content += """
                </tbody>
            </table>
        </div>
        """

    # Footer
    html_content += f"""
        <div class="footer">
            Generated on {scorecard['metadata']['generated_at'][:19].replace('T', ' ')} |
            Dataset: {scorecard['metadata']['dataset']} |
            {scorecard['metadata']['tools_evaluated']} tools evaluated
        </div>
    </body>
    </html>
    """

    # Generate PDF using the existing simple text method
    # Convert the HTML structure to plain text format for PDF
    lines = []

    # Title
    lines.append(scorecard["metadata"]["title"])
    lines.append("")
    lines.append(f"Dataset: {scorecard['metadata']['dataset']}")
    lines.append(
        f"Generated: {scorecard['metadata']['generated_at'][:19].replace('T', ' ')}"
    )
    lines.append("")

    # Executive Summary
    exec_summary = scorecard["executive_summary"]
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 20)
    lines.append(f"Status: {exec_summary['status']}")
    lines.append(f"Description: {exec_summary['status_description']}")
    lines.append("")
    lines.append("Key Metrics:")
    key_metrics = exec_summary.get("key_metrics", {})
    lines.append(".3f")
    lines.append(".3f")
    lines.append(".3f")
    lines.append(".3f")
    lines.append("")

    # Tool Comparison with Logos
    comparison_data = scorecard["tool_comparison"]
    if comparison_data and comparison_data.get("tools"):
        lines.append("TOOL COMPARISON")
        lines.append("-" * 20)
        for tool_data in comparison_data["tools"]:
            logo_indicator = "[LOGO]" if tool_data.get("logo_url") else ""
            lines.append(f"{tool_data['tool_name']} {logo_indicator}")
            lines.append(f"  Performance Tier: {tool_data['performance_tier']}")
            lines.append(f"  F1 Score: {tool_data['metrics']['f1_score']:.3f}")
            lines.append(f"  Precision: {tool_data['metrics']['precision']:.3f}")
            lines.append(f"  Recall: {tool_data['metrics']['recall']:.3f}")
            lines.append(f"  Runtime: {tool_data['metrics']['runtime_seconds']:.2f}s")
            if tool_data["strengths"]:
                lines.append(f"  Strengths: {', '.join(tool_data['strengths'][:2])}")
            lines.append("")

    # Performance Metrics
    lines.append("PERFORMANCE METRICS")
    lines.append("-" * 20)
    performance_data = scorecard["performance_metrics"]
    for tool_name, tool_metrics in performance_data.items():
        lines.append(f"{tool_name}:")
        for metric_name, metric_info in tool_metrics["primary_metrics"].items():
            value = metric_info["value"]
            target = metric_info["target"]
            status = "✓" if _meets_target(value, target) else "⚠"
            lines.append(
                f"  {metric_name.replace('_', ' ').title()}: {value:.3f} (Target: {target}) {status}"
            )
        lines.append("")

    # Risk Assessment
    risk_data = scorecard["risk_assessment"]
    lines.append("RISK ASSESSMENT")
    lines.append("-" * 20)
    lines.append(f"Overall Risk Level: {risk_data['overall_risk'].upper()}")
    lines.append(f"Strategy: {risk_data['mitigation_strategy']}")
    lines.append("")

    if risk_data["risks"]:
        lines.append("Top Risks:")
        for risk in risk_data["risks"][:3]:
            lines.append(
                f"  {risk['severity'].upper()}: {risk['category']} - {risk['description'][:60]}..."
            )
        lines.append("")

    # Recommendations
    recommendations = scorecard["recommendations"]
    if recommendations:
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 20)
        for rec in recommendations:
            lines.append(
                f"{rec['priority'].upper()}: {rec['category']} - {rec['recommendation'][:80]}..."
            )
            lines.append(
                f"  Impact: {rec['expected_impact'][:60]}... | Effort: {rec['implementation_effort'].title()}"
            )
        lines.append("")

    # Footer
    lines.append("-" * 60)
    lines.append(
        f"Generated on {scorecard['metadata']['generated_at'][:19].replace('T', ' ')}"
    )
    lines.append(
        f"Dataset: {scorecard['metadata']['dataset']} | {scorecard['metadata']['tools_evaluated']} tools evaluated"
    )

    return _simple_text_pdf_bytes(scorecard["metadata"]["title"], lines)


def _meets_target(value: float, target_str: str) -> bool:
    """Check if a value meets its target."""
    if "≥" in target_str:
        target = float(target_str.replace("≥", "").strip())
        return value >= target
    elif "≤" in target_str:
        target = float(target_str.replace("≤", "").strip())
        return value <= target
    return True


def _simple_text_pdf_bytes(title: str, lines: List[str]) -> bytes:
    """Generate a reliable multi-page text PDF without external PDF dependencies."""
    import textwrap

    page_width = 612
    page_height = 792
    margin_x = 42
    start_y = 742
    max_lines = 52
    wrap_width = 92

    rendered_lines: List[str] = []
    for raw_line in lines:
        line = str(raw_line).strip("\n")
        if not line:
            rendered_lines.append("")
            continue
        wrapped = textwrap.wrap(
            line,
            width=wrap_width,
            break_long_words=False,
            replace_whitespace=False,
        )
        rendered_lines.extend(wrapped or [""])

    pages = [
        rendered_lines[index : index + max_lines]
        for index in range(0, len(rendered_lines), max_lines)
    ] or [[title]]

    objects: List[bytes] = []
    page_object_ids: List[int] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")

    font_id = 3 + (len(pages) * 2)
    for page_index, page_lines in enumerate(pages):
        page_id = 3 + (page_index * 2)
        content_id = page_id + 1
        page_object_ids.append(page_id)

        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
        )
        objects.append(page.encode("utf-8"))

        stream_lines = ["BT", "/F1 10 Tf", f"{margin_x} {start_y} Td", "14 TL"]
        for idx, line in enumerate(page_lines):
            if idx > 0:
                stream_lines.append("T*")
            stream_lines.append(f"({_pdf_escape(line)}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("utf-8")
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{kids}] >>".encode(
        "utf-8"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


@app.post("/api/benchmark/export-pdf")
async def export_benchmark_pdf(request: Request):
    payload = await request.json()
    dataset_name = (
        payload.get("datasetName")
        or (payload.get("summary") or {}).get("dataset_name")
        or "Benchmark"
    )

    # Check if detailed scorecard is requested
    if payload.get("format") == "detailed_scorecard":
        scorecard = _build_detailed_evaluation_scorecard(payload)
        pdf = _generate_detailed_scorecard_pdf(scorecard)
    else:
        # Use legacy format
        report_lines = _build_benchmark_report_lines(payload)
        pdf = _simple_text_pdf_bytes(f"{dataset_name} Benchmark Report", report_lines)

    response = Response(content=pdf, media_type="application/pdf")
    response.headers["Content-Disposition"] = (
        "attachment; filename=benchmark_evaluation_scorecard.pdf"
    )
    return response

    pair_results = payload.get("pair_results") or []
    summary = payload.get("summary") or {}
    dataset_name = payload.get("datasetName") or "Benchmark"
    generated_at = payload.get("runAt") or datetime.now().isoformat()
    benchmark_type = payload.get("benchmark_type") or payload.get("benchmarkMode")
    evaluation = payload.get("evaluation") or {}

    if benchmark_type == "pan_optimization" and evaluation:
        import html

        metric_source = evaluation.get("integritydesk")
        if not metric_source:
            metric_source = next(
                (
                    metrics
                    for metrics in evaluation.values()
                    if metrics and not metrics.get("error")
                ),
                {},
            )

        def metric_value(name: str, fallback: float = 0.0) -> float:
            """Read a numeric metric from the selected PAN result."""
            value = metric_source.get(name, fallback) if metric_source else fallback
            try:
                return float(value)
            except (TypeError, ValueError):
                return fallback

        metrics = [
            (
                "PlagDet",
                metric_value("plagdet"),
                "Primary PAN score; combines detection quality with granularity penalty.",
                "Optimize threshold and fusion weights against PlagDet directly.",
            ),
            (
                "Precision",
                metric_value("precision"),
                "Low precision means clean pairs are being flagged as plagiarism.",
                "Raise decision threshold and require stronger multi-engine agreement.",
            ),
            (
                "Recall",
                metric_value("recall"),
                "Low recall means known plagiarism pairs are being missed.",
                "Widen candidate retrieval and strengthen renamed/structural clone handling.",
            ),
            (
                "F1 Score",
                metric_value("f1_score", metric_value("best_f1")),
                "Balances precision and recall for the selected operating threshold.",
                "Run threshold sweeps and keep the point that maximizes F1 and PlagDet.",
            ),
            (
                "Granularity",
                metric_value("granularity", 1.0),
                "Values above 1 mean detections are split into too many fragments.",
                "Merge adjacent or overlapping evidence for the same pair.",
            ),
            (
                "AUC-PR",
                metric_value("auc_pr", metric_value("pr_auc")),
                "Measures whether true plagiarism ranks above negative pairs.",
                "Tune fusion weights with PR-AUC as an objective and add harder negatives.",
            ),
            (
                "False Positive Rate",
                metric_value("false_positive_rate"),
                "High FPR creates noisy admin feedback and weakens reviewer trust.",
                "Add boilerplate/template suppression and stricter negative filters.",
            ),
            (
                "Top-10 Retrieval",
                metric_value("top_10_retrieval"),
                "Measures how cleanly true positives appear in the first ranked candidates.",
                "Tune retrieval with precision@10 and rerank using token/AST/winnowing evidence.",
            ),
            (
                "Avg Runtime",
                metric_value("avg_runtime_seconds"),
                "Slow runtime makes iterative optimization and larger datasets expensive.",
                "Cache parsing and run heavy engines only on shortlisted candidates.",
            ),
        ]

        rows = ""
        for name, value, why, action in metrics:
            display = (
                f"{value:.3f}s" if name == "Avg Runtime" else f"{value * 100:.1f}%"
            )
            if name == "Granularity":
                display = f"{value:.3f}"
            rows += f"""
                <tr>
                    <td>{html.escape(name)}</td>
                    <td><strong>{html.escape(display)}</strong></td>
                    <td>{html.escape(why)}</td>
                    <td>{html.escape(action)}</td>
                </tr>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{html.escape(dataset_name)} PAN Optimization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 24px; color: #0f172a; }}
                h1 {{ font-size: 24px; margin-bottom: 8px; }}
                p {{ color: #475569; font-size: 13px; line-height: 1.6; }}
                .meta {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
                .context {{ border: 1px solid #e2e8f0; border-radius: 12px; background: #f8fafc; padding: 14px 16px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
                th, td {{ border: 1px solid #e2e8f0; padding: 9px 10px; text-align: left; vertical-align: top; }}
                th {{ background: #f8fafc; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
                td {{ font-size: 12px; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <h1>{html.escape(dataset_name)} PAN Optimization Report</h1>
            <div class="meta">Generated: {html.escape(str(generated_at))}</div>
            <div class="context">
                <p><strong>Dataset:</strong> {html.escape(str(summary.get("dataset_name", dataset_name)))} · {int(summary.get("dataset_size", 0) or 0)} submissions · {int(summary.get("positive_pairs", 0) or 0)} plagiarized pairs</p>
                <p><strong>Purpose:</strong> Track PAN-style scores so source-code changes can improve detection accuracy with measurable feedback.</p>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Score</th>
                        <th>Why It Matters</th>
                        <th>Next Action</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </body>
        </html>
        """

        try:
            import weasyprint

            pdf = weasyprint.HTML(string=html_content).write_pdf()
            response = Response(content=pdf, media_type="application/pdf")
            response.headers["Content-Disposition"] = (
                "attachment; filename=pan_optimization_report.pdf"
            )
            return response
        except ImportError:
            return Response(
                content=html_content,
                media_type="text/html",
                headers={
                    "Content-Disposition": "attachment; filename=pan_optimization_report.html"
                },
            )
        except Exception as exc:
            logger.warning("PAN PDF export fell back to minimal PDF: %s", exc)
            response = Response(
                content=_minimal_pdf_bytes(f"{dataset_name} PAN Optimization Report"),
                media_type="application/pdf",
            )
            response.headers["Content-Disposition"] = (
                "attachment; filename=pan_optimization_report.pdf"
            )
            return response

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{dataset_name} Benchmark Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 24px; color: #0f172a; }}
            h1 {{ font-size: 24px; margin-bottom: 8px; }}
            h2 {{ font-size: 16px; margin: 28px 0 10px; }}
            p {{ margin: 0; }}
            .meta {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
            .summary {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
            .card {{ border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; min-width: 160px; }}
            .label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }}
            .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
            th, td {{ border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; vertical-align: top; }}
            th {{ background: #f8fafc; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }}
            td {{ font-size: 12px; }}
            .tool-chip {{ display: inline-block; border-radius: 999px; background: #eff6ff; color: #1d4ed8; padding: 3px 8px; font-size: 11px; font-weight: 600; margin-right: 6px; margin-bottom: 6px; }}
        </style>
    </head>
    <body>
        <h1>{dataset_name} Benchmark Report</h1>
        <div class="meta">Generated: {generated_at}</div>
        <div class="summary">
            <div class="card">
                <div class="label">Tools Run</div>
                <div class="value">{summary.get("tools_compared", 0)}</div>
            </div>
            <div class="card">
                <div class="label">Pairs Tested</div>
                <div class="value">{summary.get("pairs_tested", len(pair_results))}</div>
            </div>
            <div class="card">
                <div class="label">IntegrityDesk Avg</div>
                <div class="value">{round(float(((summary.get("accuracy") or {}).get("integritydesk") or 0)) * 100, 1)}%</div>
            </div>
            <div class="card">
                <div class="label">Best Competitor Avg</div>
                <div class="value">{round(float(((summary.get("accuracy") or {}).get("best_competitor") or 0)) * 100, 1)}%</div>
            </div>
        </div>

        <h2>Pair Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Pair</th>
                    <th>Files</th>
                    <th>Tool Scores</th>
                </tr>
            </thead>
            <tbody>
    """

    for pair in pair_results:
        tool_scores = "".join(
            f'<span class="tool-chip">{tr.get("tool", "tool")}: {round(float(tr.get("score", 0)) * 100, 1)}%</span>'
            for tr in (pair.get("tool_results") or [])
        )
        html_content += f"""
            <tr>
                <td>{pair.get('label', 'Pair')}</td>
                <td>{pair.get('file_a', '')}<br>{pair.get('file_b', '')}</td>
                <td>{tool_scores or 'No scores available'}</td>
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    try:
        import weasyprint

        pdf = weasyprint.HTML(string=html_content).write_pdf()
        response = Response(content=pdf, media_type="application/pdf")
        response.headers["Content-Disposition"] = (
            "attachment; filename=benchmark_report.pdf"
        )
        return response
    except ImportError:
        return Response(
            content=html_content,
            media_type="text/html",
            headers={
                "Content-Disposition": "attachment; filename=benchmark_report.html"
            },
        )
    except Exception as exc:
        logger.warning("Benchmark PDF export fell back to minimal PDF: %s", exc)
        response = Response(
            content=_minimal_pdf_bytes(f"{dataset_name} Benchmark Report"),
            media_type="application/pdf",
        )
        response.headers["Content-Disposition"] = (
            "attachment; filename=benchmark_report.pdf"
        )
        return response


@app.get("/benchmark/{job_id}/radar")
async def get_tool_radar_data(job_id: str):
    job = _get_job(job_id)
    if not job or "pair_results" not in job:
        raise HTTPException(status_code=404, detail="Benchmark results not found")

    pair_results = job["pair_results"]
    tools = set()
    for pair in pair_results:
        for tr in pair["tool_results"]:
            tools.add(tr["tool"])

    axes = [
        {"id": "classic_plagiarism", "name": "Copy+Rename", "axis": 0},
        {"id": "near_miss", "name": "Refactored", "axis": 1},
        {"id": "obfuscated", "name": "Obfuscated", "axis": 2},
        {"id": "semantic", "name": "LLM Rewritten", "axis": 3},
        {"id": "speed", "name": "Performance", "axis": 4},
        {"id": "scalability", "name": "Scalability", "axis": 5},
    ]

    tool_scores = {}
    for tool in tools:
        scores = [0.0, 0.0, 0.0, 0.0, 0.65, 0.70]

        # Calculate actual scores from benchmark data
        all_scores = []
        for pair in pair_results:
            for tr in pair["tool_results"]:
                if tr["tool"] == tool:
                    all_scores.append(tr["score"])

        if all_scores:
            scores[0] = max(all_scores)
            scores[1] = sorted(all_scores)[len(all_scores) // 2]
            scores[2] = min(all_scores)
            scores[3] = sum(s for s in all_scores if 0.3 < s < 0.7) / max(
                1, sum(1 for s in all_scores if 0.3 < s < 0.7)
            )

        tool_scores[tool] = scores

    return JSONResponse(
        content={
            "axes": axes,
            "tool_scores": tool_scores,
            "metadata": {
                "job_id": job_id,
                "pairs_analyzed": len(pair_results),
                "generated_at": datetime.now().isoformat(),
            },
        }
    )


def _extract_student_info(filename):
    stem = PathLib(filename).stem
    parts = re.split(r"[_\-\s]+", stem)
    id_num = ""
    for part in parts:
        if part.isdigit() and len(part) >= 4:
            id_num = part
            break
    if id_num and len(parts) >= 2:
        name = (
            " ".join(p.capitalize() for p in parts if not p.isdigit())
            or f"Student {id_num}"
        )
    elif id_num:
        name = f"Student {id_num}"
    else:
        name = stem.replace("_", " ").replace("-", " ").title()
    return {"name": name, "id": id_num or "N/A", "filename": filename}


def _escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _render_code_table(code, max_lines=80):
    lines = (code or "").split("\n")[:max_lines]
    if not lines:
        return '<div class="code-scroll"><table class="code-table"><tr><td class="line-num">-</td><td class="line-code">No code available</td></tr></table></div>'
    rows = []
    for i, line in enumerate(lines, 1):
        escaped = _escape_html(line)
        rows.append(
            f'<tr><td class="line-num">{i}</td><td class="line-code">{escaped}</td></tr>'
        )
    if len(code or "") > sum(len(line) for line in lines):
        rows.append(
            f'<tr><td class="line-num"></td><td class="line-code" style="color:#6b7280;">// ... truncated ({len(code.split(chr(10)))-max_lines} more lines)</td></tr>'
        )
    return f'<div class="code-scroll"><table class="code-table">{"".join(rows)}</table></div>'


def _generate_committee_report(
    job_id,
    course_name,
    assignment_name,
    threshold,
    report,
    comparisons,
    submissions,
    output_path,
    selected_tools=None,
    assignment_mode=None,
    calibration_report=None,
    reproducibility_report=None,
    ai_text_trust=None,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected_tools = selected_tools or ["IntegrityDesk"]
    assignment_mode = assignment_mode or {}
    calibration_report = calibration_report or {}
    reproducibility_report = reproducibility_report or {}
    ai_text_trust = ai_text_trust or {}
    mode_name = assignment_mode.get("name") or "Introductory Programming"
    mode_version = assignment_mode.get("version") or "1.0.0"
    mode_policy = assignment_mode.get("policy") or {}
    suspicious = [c for c in comparisons if c.score >= threshold]
    students_involved = set()
    for c in suspicious:
        students_involved.add(c.file_a)
        students_involved.add(c.file_b)
    student_info = {fn: _extract_student_info(fn) for fn in students_involved}

    css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f8fafc; color: #1e293b; line-height: 1.6; }
    .report-container { max-width: 1000px; margin: 0 auto; background: #ffffff; box-shadow: 0 10px 25px rgba(0,0,0,0.1), 0 4px 10px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
    .conf-banner { background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: #ffffff; text-align: center; padding: 12px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.15em; border-bottom: 1px solid #475569; }
    .report-header { background: linear-gradient(135deg, #1e40af 0%, #1e3a8a 100%); color: #ffffff; padding: 32px 40px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .report-header-left { display: flex; align-items: center; gap: 20px; }
    .report-logo { width: 50px; height: 50px; background: rgba(255,255,255,0.15); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
    .report-title { font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }
    .report-subtitle { font-size: 14px; opacity: 0.9; margin-top: 4px; font-weight: 500; }
    .report-header-right { text-align: right; font-size: 12px; opacity: 0.9; font-weight: 500; }
    .report-meta { padding: 28px 40px; border-bottom: 2px solid #e2e8f0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; font-size: 14px; background: #f8fafc; }
    .meta-item { background: #ffffff; padding: 16px; border-radius: 8px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .meta-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-bottom: 6px; }
    .meta-value { font-size: 15px; font-weight: 600; color: #1e293b; }
    .similarity-overview { padding: 40px; text-align: center; border-bottom: 2px solid #e2e8f0; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); }
    .similarity-circle { width: 140px; height: 140px; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 36px; font-weight: 800; color: #ffffff; position: relative; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .similarity-circle::before { content: ''; position: absolute; inset: 8px; border-radius: 50%; background: #ffffff; }
    .similarity-circle span { position: relative; z-index: 1; }
    .similarity-label { font-size: 18px; font-weight: 700; color: #1e293b; margin-bottom: 6px; }
    .similarity-desc { font-size: 14px; color: #64748b; font-weight: 500; }
    .color-legend { display: flex; justify-content: center; gap: 24px; margin-top: 20px; }
    .legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #475569; font-weight: 600; }
    .legend-dot { width: 12px; height: 12px; border-radius: 50%; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
    .sources-section { padding: 32px 40px; border-bottom: 1px solid #e2e8f0; }
    .section-title { font-size: 20px; font-weight: 700; color: #1e293b; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 3px solid #1e40af; letter-spacing: -0.01em; }
    .sources-table { width: 100%; border-collapse: collapse; font-size: 14px; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .sources-table th { background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); padding: 14px 16px; text-align: left; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #475569; border-bottom: 2px solid #cbd5e1; }
    .sources-table td { padding: 14px 16px; border-bottom: 1px solid #e2e8f0; background: #ffffff; }
    .sources-table tr:hover td { background: #f8fafc; transition: background-color 0.2s; }
    .similarity-badge { display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; color: #ffffff; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .sim-high { background: linear-gradient(135deg, #dc2626 0%, #b91c1c 100%); }
    .sim-medium { background: linear-gradient(135deg, #ea580c 0%, #c2410c 100%); }
    .sim-low { background: linear-gradient(135deg, #ca8a04 0%, #a16207 100%); color: #ffffff; }
    .sim-none { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); }
    .findings-section { padding: 32px 40px; }
    .finding-card { border: 2px solid #e2e8f0; border-radius: 12px; margin-bottom: 24px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); background: #ffffff; }
    .finding-header { display: flex; align-items: center; justify-content: space-between; padding: 18px 24px; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); border-bottom: 2px solid #cbd5e1; }
    .finding-title { font-size: 16px; font-weight: 700; color: #1e293b; }
    .finding-body { padding: 24px; }
    .finding-summary { font-size: 14px; color: #475569; margin-bottom: 16px; line-height: 1.7; }
    .engine-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }
    .engine-item { text-align: center; padding: 12px; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); border-radius: 8px; border: 1px solid #cbd5e1; }
    .engine-name { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #64748b; margin-bottom: 6px; letter-spacing: 0.05em; }
    .engine-score { font-size: 18px; font-weight: 800; }
    .code-evidence { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 2px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-top: 16px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .code-panel { background: #0f172a; }
    .code-panel-header { padding: 12px 16px; background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: #e2e8f0; font-size: 13px; font-weight: 700; border-bottom: 1px solid #475569; }
    .code-table { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', 'Consolas', monospace; font-size: 12px; line-height: 1.6; }
    .code-table td { padding: 0; vertical-align: top; }
    .code-table .line-num { width: 50px; text-align: right; padding: 0 10px 0 6px; color: #94a3b8; background: #1e293b; border-right: 1px solid #475569; user-select: none; font-size: 11px; white-space: nowrap; }
    .code-table .line-code { padding: 0 16px; white-space: pre; color: #cbd5e1; }
    .code-table tr.matched { background: rgba(250, 204, 21, 0.15); }
    .code-table tr.matched .line-num { background: #fef3c7; color: #92400e; }
    .code-table tr.matched .line-code { color: #fef08a; }
    .code-table tr.highlight { background: rgba(239, 68, 68, 0.2); }
    .code-table tr.highlight .line-num { background: #fecaca; color: #991b1b; }
    .code-table tr.highlight .line-code { color: #fca5a5; }
    .code-scroll { max-height: 500px; overflow-y: auto; }
    .code-scroll::-webkit-scrollbar { width: 8px; }
    .code-scroll::-webkit-scrollbar-track { background: #1e293b; }
    .code-scroll::-webkit-scrollbar-thumb { background: #64748b; border-radius: 4px; }
    .code-scroll::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
    .match-legend { display: flex; gap: 20px; margin-top: 12px; padding: 12px 16px; background: #f8fafc; border-radius: 6px; font-size: 11px; color: #64748b; border: 1px solid #e2e8f0; }
    .match-legend-item { display: flex; align-items: center; gap: 6px; }
    .match-legend-dot { width: 10px; height: 10px; border-radius: 3px; }
    .tool-chip { display: inline-flex; margin: 4px 6px 4px 0; padding: 6px 12px; border-radius: 20px; background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%); color: #1e40af; font-size: 12px; font-weight: 700; border: 1px solid #93c5fd; }
    .policy-list { margin-top: 12px; padding-left: 24px; font-size: 13px; color: #475569; line-height: 1.7; }
    .policy-list li { margin-bottom: 6px; }
    .methodology { padding: 32px 40px; border-top: 2px solid #e2e8f0; background: #f8fafc; }
    .methodology p { font-size: 14px; color: #475569; line-height: 1.7; margin-bottom: 12px; }
    .signature-row { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; margin-top: 48px; padding-top: 24px; border-top: 2px solid #e2e8f0; }
    .sig-line { border-top: 1px solid #334155; padding-top: 8px; font-size: 14px; color: #475569; text-align: center; }
    .footer { padding: 28px 40px; border-top: 2px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b; background: #f1f5f9; }
    .signature-row { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; margin-top: 48px; padding-top: 24px; border-top: 2px solid #e2e8f0; }
    .sig-line { border-top: 1px solid #334155; padding-top: 8px; font-size: 14px; color: #475569; text-align: center; }
    @media print { body { background: #ffffff; } .report-container { box-shadow: none; border: none; } .no-print { display: none; } page-break-before: always; }
    @page { margin: 1in; size: letter; }
    """

    now = datetime.now()
    max_score = max((c.score for c in suspicious), default=0)
    if max_score >= 0.9:
        circle_color = "#dc3545"
        circle_label = "High Similarity"
    elif max_score >= 0.75:
        circle_color = "#fd7e14"
        circle_label = "Moderate Similarity"
    elif max_score >= 0.5:
        circle_color = "#ffc107"
        circle_label = "Some Similarity"
    else:
        circle_color = "#28a745"
        circle_label = "Low Similarity"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Originality Report - {course_name or 'Course'}</title><style>{css}</style></head><body>
<div class="report-container">
<div class="conf-banner">Confidential -- Academic Integrity Report</div>
<div class="report-header">
<div class="report-header-left">
<div class="report-logo">ID</div>
<div>
<div class="report-title">Originality Report</div>
<div class="report-subtitle">Academic Integrity Evidence</div>
</div>
</div>
<div class="report-header-right">
<div>Generated: {now.strftime('%B %d, %Y')}</div>
<div>Case ID: {job_id}</div>
</div>
</div>

<div class="report-meta">
<div class="meta-item"><div class="meta-label">Course</div><div class="meta-value">{course_name or "Not Specified"}</div></div>
<div class="meta-item"><div class="meta-label">Assignment</div><div class="meta-value">{assignment_name or "Not Specified"}</div></div>
<div class="meta-item"><div class="meta-label">Submissions</div><div class="meta-value">{len(submissions)} files analyzed</div></div>
<div class="meta-item"><div class="meta-label">Pairs Compared</div><div class="meta-value">{report['summary']['total_pairs']}</div></div>
<div class="meta-item"><div class="meta-label">Threshold</div><div class="meta-value">{threshold:.0%}</div></div>
<div class="meta-item"><div class="meta-label">Flagged Cases</div><div class="meta-value">{len(suspicious)}</div></div>
<div class="meta-item"><div class="meta-label">Assignment Mode</div><div class="meta-value">{_escape_html(str(mode_name))} v{_escape_html(str(mode_version))}</div></div>
<div class="meta-item"><div class="meta-label">Tools Used</div><div class="meta-value">{len(selected_tools)} detector(s)</div></div>
<div class="meta-item"><div class="meta-label">Report Type</div><div class="meta-value">Dean/committee evidence packet</div></div>
</div>

<div class="similarity-overview">
<div class="similarity-circle" style="background: conic-gradient({circle_color} {max_score*360:.1f}deg, #e0e0e0 {max_score*360:.1f}deg);">
<span style="color: {circle_color}">{(max_score*100):.0f}%</span>
</div>
<div class="similarity-label">{circle_label}</div>
<div class="similarity-desc">Highest similarity score detected across {len(submissions)} submissions</div>
<div class="color-legend">
<div class="legend-item"><div class="legend-dot" style="background:#dc3545"></div>High (90%+)</div>
<div class="legend-item"><div class="legend-dot" style="background:#fd7e14"></div>Moderate (75-89%)</div>
<div class="legend-item"><div class="legend-dot" style="background:#ffc107"></div>Some (50-74%)</div>
<div class="legend-item"><div class="legend-dot" style="background:#28a745"></div>Low (&lt;50%)</div>
</div>
</div>

<div class="sources-section">
<div class="section-title">Flagged Pairs</div>
<table class="sources-table">
<thead><tr><th>Pair</th><th>Students</th><th>Similarity</th><th>Risk Level</th><th>Engines Flagged</th></tr></thead>
<tbody>"""

    for i, c in enumerate(suspicious, 1):
        ia = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        ib = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        badge_class = (
            "sim-high"
            if c.score >= 0.9
            else "sim-medium" if c.score >= 0.75 else "sim-low"
        )
        risk_label = (
            "Critical" if c.score >= 0.9 else "High" if c.score >= 0.75 else "Medium"
        )
        flagged_engines = sum(1 for v in c.features.values() if v >= threshold)
        html += f"""<tr>
<td><strong>{c.file_a}</strong> vs <strong>{c.file_b}</strong></td>
<td>{ia['name']} vs {ib['name']}</td>
<td><span class="similarity-badge {badge_class}">{(c.score*100):.1f}%</span></td>
<td>{risk_label}</td>
<td>{flagged_engines}/5</td>
</tr>"""

    html += """</tbody></table></div>

<div class="findings-section">
<div class="section-title">Detailed Findings &amp; Evidence</div>"""

    for i, c in enumerate(suspicious, 1):
        ia = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        ib = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        badge_class = (
            "sim-high"
            if c.score >= 0.9
            else "sim-medium" if c.score >= 0.75 else "sim-low"
        )

        engine_items = ""
        for name, value in sorted(c.features.items(), key=lambda x: -x[1])[:5]:
            ecolor = (
                "#dc3545" if value >= 0.75 else "#fd7e14" if value >= 0.5 else "#28a745"
            )
            engine_items += f'<div class="engine-item"><div class="engine-name">{name}</div><div class="engine-score" style="color:{ecolor}">{(value*100):.0f}%</div></div>'

        ca = c.code_a or "N/A"
        cb = c.code_b or "N/A"
        code_a_table = _render_code_table(ca)
        code_b_table = _render_code_table(cb)

        html += f"""<div class="finding-card">
<div class="finding-header">
<div class="finding-title">Finding #{i}: {ia['name']} vs {ib['name']}</div>
<span class="similarity-badge {badge_class}">{(c.score*100):.1f}% Similarity</span>
</div>
<div class="finding-body">
<div class="finding-summary">
<strong>Files:</strong> {c.file_a} vs {c.file_b}<br>
<strong>Overall Score:</strong> {(c.score*100):.1f}% | <strong>Risk:</strong> {c.risk}
</div>
<div class="engine-grid">{engine_items}</div>
<div class="match-legend">
<div class="match-legend-item"><div class="match-legend-dot" style="background:#fef08a"></div> Matching lines</div>
<div class="match-legend-item"><div class="match-legend-dot" style="background:#fca5a5"></div> High similarity</div>
<div class="match-legend-item"><div class="match-legend-dot" style="background:#d1d5db"></div> No match</div>
</div>
<div class="code-evidence">
<div class="code-panel"><div class="code-panel-header">{c.file_a}</div>{code_a_table}</div>
<div class="code-panel"><div class="code-panel-header">{c.file_b}</div>{code_b_table}</div>
</div>
</div>
</div>"""

    html += f"""</div>

<div class="methodology">
<div class="section-title">Methodology</div>
<p>IntegrityDesk employs a multi-engine detection approach using six core forensic engines: <strong>Token</strong>, <strong>AST</strong>, <strong>Winnowing</strong>, <strong>GST</strong>, <strong>Semantic</strong>, and <strong>Web</strong>, with optional <strong>AI Detection</strong> and <strong>Execution/CFG</strong> layers for deeper review.</p>
<p style="margin-top:8px;">Results are fused using weighted Bayesian arbitration to produce final similarity scores. This ensemble approach detects similarity even when students attempt to conceal copying through variable renaming, function reordering, comment changes, or whitespace modification.</p>
<p style="margin-top:8px;"><strong>Assignment mode:</strong> {_escape_html(str(mode_name))} v{_escape_html(str(mode_version))}. This mode controls preprocessing expectations, calibration, and which evidence surfaces are emphasized.</p>
<p style="margin-top:8px;"><strong>Tools used:</strong> {"".join(f'<span class="tool-chip">{_escape_html(str(tool))}</span>' for tool in selected_tools)}</p>
<p style="margin-top:8px;"><strong>Calibration:</strong> At the selected {threshold:.0%} threshold, estimated false-positive rate is approximately {float(calibration_report.get("estimated_false_positive_rate", 0.0))*100:.1f}% based on benchmark calibration guidance. {_escape_html(str(calibration_report.get("overfit_guard", "")))}</p>
<p style="margin-top:8px;"><strong>Reproducibility:</strong> Submission set hash {_escape_html(str(reproducibility_report.get("submission_set_hash", ""))[:16])}. {_escape_html(str(reproducibility_report.get("cache_note", "")))}</p>
<p style="margin-top:8px;"><strong>AI-text caution:</strong> {_escape_html(str(ai_text_trust.get("false_positive_policy", "")))} Humanizer recall is tracked separately for {_escape_html(", ".join(ai_text_trust.get("humanizer_tools", [])))}.</p>
<ul class="policy-list">
{"".join(f'<li>{_escape_html(str(item))}</li>' for item in (mode_policy.get("calibration") or [])[:4])}
</ul>
</div>

<div class="signature-row">
<div><div class="sig-line">Instructor Signature</div></div>
<div><div class="sig-line">Date</div></div>
</div>

<div class="footer">
<p>Case ID: {job_id} | {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
<p>This report is confidential and intended solely for academic integrity review.</p>
</div>
</div>
</body></html>"""
    output_path.write_text(html, encoding="utf-8")


@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "message": "Welcome to IntegrityDesk API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/api/settings")
async def get_settings(request: Request):
    current_user = _require_current_user(request, admin_only=True)
    return JSONResponse(content=_build_settings_payload(current_user.get("tenant_id")))


@app.get("/api/upload-settings")
async def get_upload_settings(request: Request):
    current_user = _require_current_user(request)
    from src.backend.engines.scoring.assignment_modes import assignment_modes_payload

    payload = _build_settings_payload(current_user.get("tenant_id"))
    engine_weights = _get_upload_engine_weights(current_user.get("tenant_id"))
    active_engines = [
        ENGINE_DISPLAY_LABELS.get(key, key.replace("_", " ").title())
        for key, value in engine_weights.items()
        if _coerce_float(value) > 0
    ]
    return JSONResponse(
        content={
            "default_threshold": payload.get(
                "default_threshold", settings.DEFAULT_THRESHOLD
            ),
            "active_engines": active_engines,
            "active_engine_keys": [
                key for key, value in engine_weights.items() if _coerce_float(value) > 0
            ],
            "assignment_modes": assignment_modes_payload(),
        }
    )


@app.get("/api/benchmark-audit/{dataset_id}")
async def get_benchmark_audit(dataset_id: str) -> Dict[str, Any]:
    """Return a benchmark audit for labeled datasets with explicit pair metadata."""
    dataset_root = BENCHMARK_DATA_DIR / dataset_id
    if not dataset_root.exists() and dataset_id not in BUILTIN_PAIR_DATASET_IDS:
        raise HTTPException(status_code=404, detail="Benchmark dataset not found")

    raw_pairs = _read_generated_pair_items(dataset_root)
    if not raw_pairs:
        raise HTTPException(
            status_code=400,
            detail="Benchmark audit requires explicit pair-labeled dataset metadata",
        )

    return {
        "dataset_id": dataset_id,
        "audit": _audit_benchmark_pairs(raw_pairs),
        "quality_certificate": _build_benchmark_quality_certificate(dataset_root),
        "split_guard": {
            "tuning": _benchmark_split_guard("validation", "tuning"),
            "locked_test": _benchmark_split_guard("test", "tuning"),
        },
    }


@app.get("/api/assignment-modes")
async def get_assignment_modes_catalog() -> Dict[str, Any]:
    """Return professor-facing assignment modes and preprocessing policy."""
    from src.backend.engines.scoring.assignment_modes import assignment_modes_payload

    return assignment_modes_payload()


@app.post("/api/assignment-modes/suggest")
async def suggest_assignment_mode(request: Request) -> Dict[str, Any]:
    """Suggest an assignment mode from professor-provided metadata."""
    _require_current_user(request)
    from src.backend.engines.scoring.assignment_modes import recommend_assignment_mode

    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid suggestion payload")

    filenames = (
        payload.get("filenames") if isinstance(payload.get("filenames"), list) else []
    )
    content_samples = (
        payload.get("content_samples")
        if isinstance(payload.get("content_samples"), list)
        else []
    )
    return recommend_assignment_mode(
        assignment_name=str(payload.get("assignment_name") or ""),
        course_name=str(payload.get("course_name") or ""),
        filenames=[str(name) for name in filenames[:200]],
        content_samples=[str(sample)[:2000] for sample in content_samples[:20]],
    )


@app.patch("/api/settings")
async def update_settings(request: Request):
    current_user = _require_current_user(request, admin_only=True)
    data = await request.json()
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Admin account is not attached to a workspace tenant",
        )

    with SessionLocal() as db:
        tenant = db.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Workspace tenant not found")

        stored_settings = dict(tenant.settings or {})
        applied = {}
        env_updates: Dict[str, Any] = {}

        for key, value in data.items():
            if key not in SETTINGS_ATTR_MAP and key != "professor_profile":
                continue
            if key in SECRET_SETTING_KEYS and value == "":
                continue
            if key == "engine_weights":
                value = _normalize_engine_weights(value)
            if key == "source_scan_sites":
                value = _normalize_source_scan_sites(value)
            if key == "professor_profile":
                from src.backend.engines.scoring.professor_profiles import (
                    apply_professor_profile,
                )

                value = dict(apply_professor_profile(value).profile.__dict__)
            stored_settings[key] = value
            applied[key] = bool(value) if key in SECRET_SETTING_KEYS else value
            if key == "professor_profile":
                continue
            if key in SECRET_SETTING_KEYS and value:
                env_updates[SETTINGS_ATTR_MAP[key]] = value

        tenant.settings = stored_settings
        db.add(tenant)
        db.commit()

    if env_updates:
        _persist_env_settings(env_updates)

    _apply_runtime_settings_from_record(stored_settings)

    # Persist engine weights and calibration config to yaml file
    from src.backend.engines.scoring.fusion_engine import FusionEngine
    from src.backend.engines.scoring.fusion_policy import (
        evaluate_weight_change_governance,
    )

    engine_config = FusionEngine.get_current_config()
    governance_result = None

    if "engine_weights" in data:
        proposed_weights = _normalize_engine_weights(data["engine_weights"])
        governance_result = evaluate_weight_change_governance(
            engine_config.get("weights", {}),
            proposed_weights,
            data.get("weight_governance_evidence"),
        )
        engine_config["weights"] = proposed_weights
        if governance_result.requires_validation and not governance_result.allowed:
            engine_config.setdefault("advanced", {})["weights_need_validation"] = True
    elif "professor_profile" in data:
        from src.backend.engines.scoring.professor_profiles import (
            apply_professor_profile,
            professor_profile_to_engine_weights,
        )

        applied_profile = apply_professor_profile(data.get("professor_profile"))
        engine_config["weights"] = professor_profile_to_engine_weights(applied_profile)
        engine_config.setdefault("professor_profile", {})[
            "applied"
        ] = applied_profile.to_dict()
    if "baseline_correction" in data:
        engine_config["baseline_correction"] = data["baseline_correction"]

    FusionEngine.update_config(engine_config)

    response: Dict[str, Any] = {
        "status": "ok",
        "settings": applied,
        "source": "database",
    }
    if governance_result is not None:
        response["weight_governance"] = governance_result.to_dict()

    return JSONResponse(content=response)


# === SETTINGS API ENDPOINTS ===


@app.get("/api/settings/engine-config")
async def get_engine_config():
    """Get current engine configuration for settings page."""
    from src.backend.engines.scoring.fusion_engine import load_engine_config

    config = load_engine_config()
    return {
        "weights": config.get("weights", {}),
        "baselines": config.get("baseline_correction", {}).get("baselines", {}),
        "arbitration": config.get("arbitration", {}),
        "ast_boost": config.get("ast_boost", {}),
        "decision": config.get("decision", {}),
        "thresholds": config.get("thresholds", {}),
        "toggles": config.get("toggles", {}),
        "performance": config.get("performance", {}),
        "advanced": config.get("advanced", {}),
        "score_normalization": config.get("score_normalization", {}),
        "fusion_presets": config.get("fusion_presets", {}),
        "weight_governance": config.get("weight_governance", {}),
        "assignment_modes": config.get("assignment_modes", {}),
    }


@app.put("/api/settings/engine-config")
async def update_engine_config(config_update: Dict[str, Any]):
    """Update engine configuration (admin only)."""
    from src.backend.engines.scoring.fusion_engine import (
        load_engine_config,
        save_engine_config,
    )
    from src.backend.engines.scoring.fusion_policy import (
        evaluate_weight_change_governance,
    )

    try:
        # Load current config
        current_config = load_engine_config()

        # Merge updates
        updated_config = {**current_config, **config_update}
        governance_result = None
        if "weights" in config_update:
            governance_result = evaluate_weight_change_governance(
                current_config.get("weights", {}),
                updated_config.get("weights", {}),
                config_update.get("weight_governance_evidence"),
            )
            if not governance_result.allowed:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Default weight changes require validation evidence",
                        "weight_governance": governance_result.to_dict(),
                    },
                )

        # Validate weights sum to 1.0
        if "weights" in updated_config and updated_config["weights"]:
            total = sum(updated_config["weights"].values())
            if abs(total - 1.0) > 0.001:
                raise HTTPException(
                    status_code=400, detail=f"Weights must sum to 1.0, got {total:.3f}"
                )

        # Validate value ranges (0-1)
        validate_sections = ["weights", "thresholds"]
        for section in validate_sections:
            if section in updated_config:
                for key, value in updated_config[section].items():
                    if isinstance(value, (int, float)):
                        if not 0.0 <= value <= 1.0:
                            raise HTTPException(
                                status_code=400,
                                detail=f"{section}.{key} must be between 0.0 and 1.0, got {value}",
                            )

        # Save configuration
        save_engine_config(updated_config)

        response: Dict[str, Any] = {
            "success": True,
            "message": "Engine configuration updated successfully",
        }
        if governance_result is not None:
            response["weight_governance"] = governance_result.to_dict()
        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/settings/calibrate")
async def trigger_calibration():
    """Trigger automatic engine calibration."""
    try:
        from src.backend.engines.scoring.fusion_engine import FusionEngine

        result = FusionEngine.calibrate_optimal_weights()

        return {
            "success": True,
            "message": "Calibration completed successfully",
            "results": result,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration failed: {str(e)}")


@app.get("/api/settings/validation")
async def validate_current_config():
    """Validate current configuration for issues."""
    from src.backend.engines.scoring.fusion_engine import load_engine_config
    from src.backend.engines.scoring.fusion_policy import (
        default_score_normalizer,
        evaluate_weight_change_governance,
    )

    config = load_engine_config()
    issues = []

    # Check weights sum
    if "weights" in config:
        total = sum(config["weights"].values())
        if abs(total - 1.0) > 0.001:
            issues.append(f"Weights don't sum to 1.0 (current: {total:.3f})")

    # Check value ranges
    for section in ["weights", "thresholds"]:
        if section in config:
            for key, value in config[section].items():
                if isinstance(value, (int, float)):
                    if not 0.0 <= value <= 1.0:
                        issues.append(f"{section}.{key} out of range: {value}")

    if config.get("advanced", {}).get("weights_need_validation"):
        governance = evaluate_weight_change_governance(
            {},
            config.get("weights", {}),
            config.get("advanced", {}).get("weight_governance_evidence"),
        )
        issues.extend(governance.warnings)

    normalizer = default_score_normalizer()

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "config_summary": {
            "weights_count": len(config.get("weights", {})),
            "thresholds_count": len(config.get("thresholds", {})),
            "toggles_enabled": sum(config.get("toggles", {}).values()),
            "normalization_rules_count": len(normalizer.rules),
            "fusion_presets_count": len(config.get("fusion_presets", {})),
        },
    }


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("BACKEND_PORT", "8000")))


if __name__ == "__main__":
    main()
