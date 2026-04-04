"""IntegrityDesk Professor Dashboard - Professional web interface for academic integrity analysis."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import tempfile
import zipfile
import shutil
import uuid
import json
import re
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path as PathLib

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader

from src.application.services.batch_detection_service import BatchDetectionService
from src.infrastructure.report_generator import ReportGenerator, ComparisonDetail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IntegrityDesk Professor Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPLATES_DIR = PathLib(__file__).parent / "templates"
REPORTS_DIR = project_root / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = project_root / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# In-memory job store (replace with database in production)
_jobs: Dict[str, Dict[str, Any]] = {}

ALLOWED_EXTENSIONS = {
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.js', '.ts', '.jsx', '.tsx',
    '.go', '.rs', '.rb', '.php', '.cs', '.kt', '.swift', '.scala', '.r', '.m',
    '.sql', '.sh', '.bash', '.zsh', '.ps1', '.lua', '.pl', '.pm', '.ex', '.exs',
    '.dart', '.clj', '.hs', '.ml', '.fs', '.erl', '.vue', '.svelte',
}

CODE_EXTENSIONS = {
    '.py': 'Python', '.java': 'Java', '.c': 'C', '.cpp': 'C++', '.h': 'C/C++ Header',
    '.js': 'JavaScript', '.ts': 'TypeScript', '.go': 'Go', '.rs': 'Rust',
    '.rb': 'Ruby', '.php': 'PHP', '.cs': 'C#', '.kt': 'Kotlin', '.swift': 'Swift',
}


def _extract_student_name(filename: str) -> str:
    """Extract student identifier from filename."""
    name = PathLib(filename).stem
    for sep in ['_', '-', ' ', '.']:
        if sep in name:
            return name.split(sep)[0]
    return name


def _is_code_file(filename: str) -> bool:
    """Check if file is a supported code file."""
    return PathLib(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _extract_zip(zip_path: PathLib, target_dir: PathLib) -> List[str]:
    """Extract zip file and return list of extracted code files."""
    extracted = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.namelist():
            if member.endswith('/'):
                continue
            filename = PathLib(member).name
            if _is_code_file(filename):
                target = target_dir / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, 'wb') as dst:
                    dst.write(src.read())
                extracted.append(str(target))
    return extracted


def _read_files_from_dir(directory: PathLib) -> Dict[str, str]:
    """Read all code files from a directory recursively."""
    submissions = {}
    for ext in ALLOWED_EXTENSIONS:
        for f in directory.rglob(f"*{ext}"):
            try:
                content = f.read_text(encoding='utf-8', errors='ignore')
                if len(content.strip()) > 10:
                    submissions[f.name] = content
            except Exception as e:
                logger.warning(f"Skipping {f.name}: {e}")
    return submissions


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Main professor dashboard page."""
    template = jinja_env.get_template("professor_dashboard.html")
    html = template.render(
        request=request,
        jobs=sorted(_jobs.values(), key=lambda x: x.get("created_at", ""), reverse=True),
    )
    return HTMLResponse(content=html)


@app.get("/job/{job_id}", response_class=HTMLResponse)
async def job_results(request: Request, job_id: str):
    """View results for a specific job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    template = jinja_env.get_template("job_results.html")
    html = template.render(request=request, job=job)
    return HTMLResponse(content=html)


@app.get("/report/{job_id}/download", response_class=HTMLResponse)
async def download_report_html(request: Request, job_id: str):
    """Download HTML report."""
    job = _jobs.get(job_id)
    if not job or "report_path" not in job:
        raise HTTPException(status_code=404, detail="Report not available")
    report_path = PathLib(job["report_path"])
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        str(report_path),
        media_type="text/html",
        filename=f"integritydesk_report_{job_id}.html"
    )


@app.get("/report/{job_id}/download-json")
async def download_report_json(job_id: str):
    """Download JSON report."""
    job = _jobs.get(job_id)
    if not job or "report_json_path" not in job:
        raise HTTPException(status_code=404, detail="Report not available")
    report_path = PathLib(job["report_json_path"])
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(
        str(report_path),
        media_type="application/json",
        filename=f"integritydesk_report_{job_id}.json"
    )


@app.get("/report/{job_id}/committee", response_class=HTMLResponse)
async def download_committee_report(request: Request, job_id: str):
    """Download committee-ready report."""
    job = _jobs.get(job_id)
    if not job or "committee_report_path" not in job:
        raise HTTPException(status_code=404, detail="Committee report not available")
    report_path = PathLib(job["committee_report_path"])
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Committee report file not found")
    return FileResponse(
        str(report_path),
        media_type="text/html",
        filename=f"integritydesk_committee_report_{job_id}.html"
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    threshold: float = Form(default=0.5),
):
    """Upload individual student assignment files for analysis."""
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        if f.filename and _is_code_file(f.filename):
            target = job_dir / f.filename
            content = await f.read()
            target.write_bytes(content)
            saved_files.append(f.filename)

    if len(saved_files) < 2:
        return JSONResponse(
            status_code=400,
            content={"error": "At least 2 code files are required for comparison"}
        )

    return await _run_analysis(job_id, job_dir, course_name, assignment_name, threshold)


@app.post("/api/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    threshold: float = Form(default=0.5),
):
    """Upload a zip file containing an entire class's assignments."""
    if not file.filename or not file.filename.lower().endswith('.zip'):
        return JSONResponse(
            status_code=400,
            content={"error": "Please upload a .zip file"}
        )

    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    zip_path = job_dir / file.filename
    content = await file.read()
    zip_path.write_bytes(content)

    extracted = _extract_zip(zip_path, job_dir)
    if len(extracted) < 2:
        shutil.rmtree(job_dir)
        return JSONResponse(
            status_code=400,
            content={"error": "Zip file must contain at least 2 code files"}
        )

    return await _run_analysis(job_id, job_dir, course_name, assignment_name, threshold)


async def _run_analysis(
    job_id: str,
    job_dir: PathLib,
    course_name: str,
    assignment_name: str,
    threshold: float,
):
    """Run the full analysis pipeline."""
    _jobs[job_id] = {
        "id": job_id,
        "course_name": course_name or "Unnamed Course",
        "assignment_name": assignment_name or "Unnamed Assignment",
        "threshold": threshold,
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "file_count": 0,
        "results": [],
        "summary": {},
    }

    try:
        submissions = _read_files_from_dir(job_dir)
        if len(submissions) < 2:
            del _jobs[job_id]
            return JSONResponse(
                status_code=400,
                content={"error": "At least 2 valid code files required"}
            )

        _jobs[job_id]["file_count"] = len(submissions)
        _jobs[job_id]["status"] = "analyzing"

        service = BatchDetectionService(threshold=threshold)
        results = service.compare_all_pairs(submissions)
        report = service.generate_report(results)

        comparison_details = []
        for r in results:
            detail = ComparisonDetail(
                file_a=r.file_a,
                file_b=r.file_b,
                score=r.score,
                risk=r.risk_level,
                features=r.features,
                code_a=submissions.get(r.file_a, ""),
                code_b=submissions.get(r.file_b, ""),
            )
            comparison_details.append(detail)

        rg = ReportGenerator(
            title=f"IntegrityDesk Report - {course_name or 'Course'}",
            institution="",
            course=course_name or "Course",
            assignment=assignment_name or "Assignment",
            threshold=threshold,
            output_dir=REPORTS_DIR / job_id,
        )
        html_report_path = rg.generate_html(comparison_details)
        json_report_path = rg.generate_json(comparison_details)

        committee_report_path = REPORTS_DIR / job_id / "committee_report.html"
        _generate_committee_report(
            job_id, course_name, assignment_name, threshold,
            report, comparison_details, submissions, committee_report_path
        )

        _jobs[job_id].update({
            "status": "completed",
            "results": [
                {
                    "file_a": r.file_a,
                    "file_b": r.file_b,
                    "score": round(r.score, 3),
                    "risk_level": r.risk_level,
                    "features": {k: round(v, 3) for k, v in r.features.items()},
                }
                for r in results
            ],
            "summary": report["summary"],
            "report_path": str(html_report_path),
            "report_json_path": str(json_report_path),
            "committee_report_path": str(committee_report_path),
            "submissions": {k: v[:3000] for k, v in submissions.items()},
        })

        return JSONResponse(content={"job_id": job_id, "status": "completed"})

    except Exception as e:
        logger.exception(f"Analysis failed for job {job_id}")
        if job_id in _jobs:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Analysis failed: {str(e)}"}
        )


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and results."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job)


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs."""
    jobs_list = sorted(_jobs.values(), key=lambda x: x.get("created_at", ""), reverse=True)
    return JSONResponse(content={"jobs": jobs_list})


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files."""
    job = _jobs.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = UPLOADS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    return JSONResponse(content={"status": "deleted"})


@app.post("/api/benchmark")
async def run_benchmark(
    files: List[UploadFile] = File(...),
    tools: List[str] = Form(default=["integritydesk"]),
):
    """Run benchmark comparison across multiple detection tools."""
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        if f.filename and _is_code_file(f.filename):
            target = job_dir / f.filename
            content = await f.read()
            target.write_bytes(content)
            saved_files.append(f.filename)

    if len(saved_files) < 2:
        return JSONResponse(
            status_code=400,
            content={"error": "At least 2 code files required"}
        )

    submissions = _read_files_from_dir(job_dir)
    tool_results = {}

    if "integritydesk" in tools:
        try:
            service = BatchDetectionService(threshold=0.3)
            results = service.compare_all_pairs(submissions)
            tool_results["integritydesk"] = {
                "pairs": [
                    {
                        "file_a": r.file_a,
                        "file_b": r.file_b,
                        "score": round(r.score, 3),
                        "risk_level": r.risk_level,
                    }
                    for r in results
                ],
                "pair_count": len(results),
            }
        except Exception as e:
            logger.exception("IntegrityDesk benchmark failed")
            tool_results["integritydesk"] = {"error": str(e)}

    for tool in tools:
        if tool == "integritydesk":
            continue
        try:
            if tool == "moss":
                score = _run_moss_benchmark(submissions)
            elif tool == "jplag":
                score = _run_jplag_benchmark(submissions)
            elif tool == "dolos":
                score = _run_dolos_benchmark(submissions)
            elif tool == "codequiry":
                score = _run_codequiry_benchmark(submissions)
            else:
                score = None

            if score is not None:
                tool_results[tool] = {
                    "pairs": score.get("pairs", []),
                    "pair_count": len(score.get("pairs", [])),
                }
            else:
                tool_results[tool] = {"error": f"{tool} not available"}
        except Exception as e:
            logger.exception(f"{tool} benchmark failed")
            tool_results[tool] = {"error": str(e)}

    pair_results = []
    all_pairs = set()
    for tool_name, tool_data in tool_results.items():
        if "pairs" in tool_data:
            for p in tool_data["pairs"]:
                pair_key = tuple(sorted([p["file_a"], p["file_b"]]))
                all_pairs.add(pair_key)

    for pair_key in all_pairs:
        pair_entry = {
            "file_a": pair_key[0],
            "file_b": pair_key[1],
            "label": f"{PathLib(pair_key[0]).stem} vs {PathLib(pair_key[1]).stem}",
            "tool_results": [],
        }
        for tool_name, tool_data in tool_results.items():
            if "pairs" in tool_data:
                for p in tool_data["pairs"]:
                    if tuple(sorted([p["file_a"], p["file_b"]])) == pair_key:
                        pair_entry["tool_results"].append({
                            "tool": tool_name,
                            "score": p["score"],
                        })
        pair_results.append(pair_entry)

    integritydesk_accuracy = 0.0
    best_competitor_accuracy = 0.0

    return JSONResponse(content={
        "job_id": job_id,
        "tool_scores": {k: {"pairs": v.get("pair_count", 0)} for k, v in tool_results.items()},
        "pair_results": pair_results,
        "summary": {
            "pairs_tested": len(pair_results),
            "tools_compared": len([t for t in tool_results if "error" not in tool_results[t]]),
            "accuracy": {
                "integritydesk": integritydesk_accuracy,
                "best_competitor": best_competitor_accuracy,
            },
        },
    })


def _run_moss_benchmark(submissions: Dict[str, str]) -> Optional[Dict]:
    """Run MOSS-style comparison using ngram + winnowing as proxy."""
    try:
        from src.engines.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor()
        files = list(submissions.keys())
        pairs = []
        for i, fa in enumerate(files):
            for fb in files[i+1:]:
                fv = extractor.extract(submissions[fa], submissions[fb])
                score = max(fv.ngram or 0, fv.winnowing or 0)
                pairs.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": pairs}
    except Exception:
        return None


def _run_jplag_benchmark(submissions: Dict[str, str]) -> Optional[Dict]:
    """Run JPlag-style comparison using AST similarity as proxy."""
    try:
        from src.engines.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor()
        files = list(submissions.keys())
        pairs = []
        for i, fa in enumerate(files):
            for fb in files[i+1:]:
                fv = extractor.extract(submissions[fa], submissions[fb])
                score = fv.ast or 0
                pairs.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": pairs}
    except Exception:
        return None


def _run_dolos_benchmark(submissions: Dict[str, str]) -> Optional[Dict]:
    """Run Dolos-style comparison using winnowing as proxy."""
    try:
        from src.engines.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor()
        files = list(submissions.keys())
        pairs = []
        for i, fa in enumerate(files):
            for fb in files[i+1:]:
                fv = extractor.extract(submissions[fa], submissions[fb])
                score = fv.winnowing or 0
                pairs.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": pairs}
    except Exception:
        return None


def _run_codequiry_benchmark(submissions: Dict[str, str]) -> Optional[Dict]:
    """Run Codequiry-style comparison using embedding as proxy."""
    try:
        from src.engines.features.feature_extractor import FeatureExtractor
        extractor = FeatureExtractor()
        files = list(submissions.keys())
        pairs = []
        for i, fa in enumerate(files):
            for fb in files[i+1:]:
                fv = extractor.extract(submissions[fa], submissions[fb])
                score = fv.embedding or 0
                pairs.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": pairs}
    except Exception:
        return None


def _extract_student_info(filename: str) -> Dict[str, str]:
    """Extract student name and ID from filename."""
    stem = PathLib(filename).stem
    parts = re.split(r'[_\-\s]+', stem)

    id_num = ""
    name = stem

    for part in parts:
        if part.isdigit() and len(part) >= 4:
            id_num = part
            break

    if id_num and len(parts) >= 2:
        name_parts = [p.capitalize() for p in parts if not p.isdigit()]
        name = " ".join(name_parts) if name_parts else f"Student {id_num}"
    elif id_num:
        name = f"Student {id_num}"
    else:
        name = stem.replace("_", " ").replace("-", " ").title()

    return {"name": name, "id": id_num or "N/A", "filename": filename}


def _generate_committee_report(
    job_id: str,
    course_name: str,
    assignment_name: str,
    threshold: float,
    report: Dict[str, Any],
    comparisons: List[ComparisonDetail],
    submissions: Dict[str, str],
    output_path: PathLib,
):
    """Generate a formal committee-ready report for administrative adjudication."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    suspicious = [c for c in comparisons if c.score >= threshold]
    critical = [c for c in comparisons if c.score >= 0.9]
    high = [c for c in comparisons if 0.75 <= c.score < 0.9]
    medium = [c for c in comparisons if 0.5 <= c.score < 0.75]

    students_involved = set()
    for c in suspicious:
        students_involved.add(c.file_a)
        students_involved.add(c.file_b)

    student_info = {fn: _extract_student_info(fn) for fn in students_involved}

    css = """
    body { font-family: 'Georgia', 'Times New Roman', serif; margin: 40px; color: #1a1a1a; line-height: 1.6; }
    .header { text-align: center; border-bottom: 3px double #333; padding-bottom: 20px; margin-bottom: 30px; }
    .header h1 { font-size: 24px; margin: 0; color: #1a1a1a; letter-spacing: 0.02em; }
    .header h2 { font-size: 14px; margin: 6px 0 0; color: #555; font-weight: normal; text-transform: uppercase; letter-spacing: 0.08em; }
    .meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 30px; font-size: 13px; }
    .meta-item { padding: 10px 12px; background: #f9f9f9; border-left: 3px solid #333; }
    .meta-label { font-weight: bold; color: #555; display: block; font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px; }
    .meta-value { font-size: 14px; color: #1a1a1a; }
    .recommendation-box { background: #fde8e8; border: 2px solid #dc3545; border-left: 5px solid #a41e35; padding: 20px; margin-bottom: 30px; border-radius: 4px; }
    .recommendation-box h3 { margin: 0 0 8px; color: #a41e35; font-size: 16px; text-transform: uppercase; letter-spacing: 0.05em; }
    .recommendation-box p { margin: 0; color: #6b1a2a; font-size: 14px; }
    .executive-summary { background: #fff8e1; border: 1px solid #e8a300; padding: 20px; margin-bottom: 30px; border-radius: 4px; }
    .executive-summary h3 { margin-top: 0; color: #856404; font-size: 15px; }
    .section { margin-bottom: 30px; }
    .section h3 { border-bottom: 2px solid #333; padding-bottom: 8px; color: #1a1a1a; font-size: 16px; text-transform: uppercase; letter-spacing: 0.05em; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #f5f5f5; font-weight: bold; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; color: #555; }
    .risk-critical { background: #a41e35; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-high { background: #dc3545; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-medium { background: #e8a300; color: #333; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-low { background: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
    .stat-card { text-align: center; padding: 16px; background: #f5f5f5; border-radius: 4px; border-top: 3px solid #333; }
    .stat-value { font-size: 28px; font-weight: bold; color: #1a1a1a; }
    .stat-label { font-size: 10px; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
    .finding { border: 1px solid #d9d9d9; padding: 0; margin-bottom: 20px; border-radius: 4px; overflow: hidden; }
    .finding-header { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: #fafbfc; border-bottom: 1px solid #e8e8e8; }
    .finding-header strong { font-size: 14px; }
    .finding-body { padding: 16px; }
    .finding-comment { background: #fff3cd; border-left: 3px solid #e8a300; padding: 10px 14px; margin: 12px 0; font-size: 13px; color: #856404; font-style: italic; }
    .features { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .feature-tag { background: #e6f0fa; color: #0066cc; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 500; }
    .code-comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin-top: 12px; border: 1px solid #d9d9d9; border-radius: 4px; overflow: hidden; }
    .code-panel-header { padding: 6px 12px; background: #f5f5f5; font-size: 11px; font-weight: 600; border-bottom: 1px solid #d9d9d9; color: #333; }
    .code-block { padding: 12px; font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; font-size: 10px; line-height: 1.5; overflow-x: auto; max-height: 200px; background: #1e1e1e; color: #d4d4d4; margin: 0; white-space: pre; }
    .timeline-table { margin-top: 10px; }
    .timeline-table td { font-size: 12px; }
    .footer { margin-top: 50px; padding-top: 20px; border-top: 2px solid #333; font-size: 11px; color: #888; text-align: center; }
    .signature { margin-top: 50px; display: grid; grid-template-columns: 1fr 1fr; gap: 60px; }
    .signature-line { border-top: 1px solid #333; padding-top: 6px; font-size: 12px; color: #333; }
    .confidential-banner { background: #333; color: #fff; text-align: center; padding: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 30px; }
    @media print { body { margin: 20px; } .no-print { display: none; } .code-block { max-height: 150px; } }
    """

    now = datetime.now()
    report_date = now.strftime('%B %d, %Y at %H:%M')
    report_date_short = now.strftime('%Y-%m-%d')

    critical_cases_text = []
    for c in critical:
        info_a = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        info_b = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        critical_cases_text.append(f"{info_a['name']} (ID: {info_a['id']}) and {info_b['name']} (ID: {info_b['id']})")

    recommendation_text = "Immediate administrative action is requested as the findings suggest a direct breach of the University Code of Conduct." if critical else "The committee should review the flagged cases at its next scheduled meeting."

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Academic Integrity Report - {course_name or 'Course'}</title>
<style>{css}</style>
</head>
<body>

<div class="confidential-banner">Confidential -- For Academic Integrity Committee Use Only</div>

<div class="no-print" style="text-align: right; margin-bottom: 20px;">
<button onclick="window.print()" style="padding: 8px 16px; cursor: pointer; font-family: inherit; font-size: 12px;">Print / Save as PDF</button>
</div>

<div class="header">
<h1>ACADEMIC INTEGRITY COMMITTEE REPORT</h1>
<h2>Code Similarity Analysis &amp; Cases for Adjudication</h2>
<h2>IntegrityDesk Automated Detection System</h2>
</div>

<div class="meta">
<div class="meta-item"><span class="meta-label">Course</span><span class="meta-value">{course_name or "Not Specified"}</span></div>
<div class="meta-item"><span class="meta-label">Assignment</span><span class="meta-value">{assignment_name or "Not Specified"}</span></div>
<div class="meta-item"><span class="meta-label">Report Date</span><span class="meta-value">{report_date}</span></div>
<div class="meta-item"><span class="meta-label">Case ID</span><span class="meta-value">{job_id}</span></div>
<div class="meta-item"><span class="meta-label">Submissions Analyzed</span><span class="meta-value">{len(submissions)}</span></div>
<div class="meta-item"><span class="meta-label">Similarity Threshold</span><span class="meta-value">{threshold:.0%}</span></div>
</div>

<div class="recommendation-box">
<h3>Recommendation for Adjudication</h3>
<p>{recommendation_text}</p>
</div>

<div class="executive-summary">
<h3>Executive Summary</h3>
<p>This report details the findings of an automated code similarity analysis conducted on
<strong>{len(submissions)} student submissions</strong> for the assignment
<strong>"{assignment_name or 'Not Specified'}"</strong> in the course
<strong>"{course_name or 'Not Specified'}"</strong>.</p>
<p>The analysis identified <strong>{len(suspicious)} case(s) for adjudication</strong> exceeding the
similarity threshold of {threshold:.0%}, involving <strong>{len(students_involved)} student(s)</strong>.
Of these, <strong>{len(critical)} case(s)</strong> are classified as CRITICAL risk and
<strong>{len(high)} case(s)</strong> as HIGH risk."""

    if critical:
        html += f""" The critical cases involve: {', '.join(critical_cases_text)}."""

    html += """</p>
</div>

<div class="section">
<h3>Statistical Overview</h3>
<div class="stat-grid">
<div class="stat-card"><div class="stat-value">{0}</div><div class="stat-label">Submissions</div></div>
<div class="stat-card"><div class="stat-value">{1}</div><div class="stat-label">Pairs Compared</div></div>
<div class="stat-card" style="border-top-color: #dc3545;"><div class="stat-value" style="color: #dc3545;">{2}</div><div class="stat-label">Cases for Adjudication</div></div>
<div class="stat-card" style="border-top-color: #a41e35;"><div class="stat-value" style="color: #a41e35;">{3}</div><div class="stat-label">Critical Risk</div></div>
</div>
</div>

<div class="section">
<h3>Risk Distribution</h3>
<table>
<tr><th>Risk Level</th><th>Count</th><th>Score Range</th><th>Recommended Action</th></tr>
<tr><td><span class="risk-critical">CRITICAL</span></td><td>{4}</td><td>90% - 100%</td><td>Immediate review required</td></tr>
<tr><td><span class="risk-high">HIGH</span></td><td>{5}</td><td>75% - 89%</td><td>Detailed review recommended</td></tr>
<tr><td><span class="risk-medium">MEDIUM</span></td><td>{6}</td><td>50% - 74%</td><td>Manual check advised</td></tr>
<tr><td><span class="risk-low">LOW</span></td><td>{7}</td><td>Below {8}</td><td>No action needed</td></tr>
</table>
</div>

<div class="section">
<h3>Detailed Findings</h3>
""".format(
        len(submissions),
        report['summary']['total_pairs'],
        len(suspicious),
        len(critical),
        len(critical),
        len(high),
        len(medium),
        len(comparisons) - len(suspicious),
        f"{threshold:.0%}",
    )

    for i, c in enumerate(suspicious, 1):
        info_a = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        info_b = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})

        features_str = "".join(
            f'<span class="feature-tag">{k}: {v:.1%}</span>'
            for k, v in sorted(c.features.items(), key=lambda x: -x[1])[:5]
        )
        risk_class = "risk-critical" if c.score >= 0.9 else "risk-high" if c.score >= 0.75 else "risk-medium"
        risk_label = c.risk

        comment = ""
        if c.score >= 0.99:
            comment = '<div class="finding-comment">The near-perfect match across all active forensic engines indicates that these submissions are functionally identical, suggesting a direct file copy or submission of the same source.</div>'
        elif c.score >= 0.9:
            comment = '<div class="finding-comment">The extremely high similarity score across multiple independent engines strongly suggests substantial code sharing between these submissions.</div>'
        elif c.score >= 0.75:
            comment = '<div class="finding-comment">Significant structural and semantic similarities detected. Manual review of the source code is recommended to determine the nature of the overlap.</div>'

        code_snippet_a = c.code_a[:800] if c.code_a else "Source not available"
        code_snippet_b = c.code_b[:800] if c.code_b else "Source not available"
        if len(c.code_a or "") > 800:
            code_snippet_a += "\n... [truncated]"
        if len(c.code_b or "") > 800:
            code_snippet_b += "\n... [truncated]"

        html += f"""
<div class="finding">
<div class="finding-header">
<strong>Case #{i}: {info_a['name']} (ID: {info_a['id']}) vs {info_b['name']} (ID: {info_b['id']})</strong>
<span class="{risk_class}">{risk_label} ({c.score:.1%})</span>
</div>
<div class="finding-body">
<p><strong>Files:</strong> {c.file_a} vs {c.file_b}</p>
<p>Overall similarity score of <strong>{c.score:.1%}</strong> detected between the two submissions.</p>
{comment}
<div class="features">{features_str}</div>

<div class="code-comparison">
<div>
<div class="code-panel-header">Source: {c.file_a}</div>
<pre class="code-block">{code_snippet_a}</pre>
</div>
<div>
<div class="code-panel-header">Source: {c.file_b}</div>
<pre class="code-block">{code_snippet_b}</pre>
</div>
</div>
</div>
</div>
"""

    html += """
</div>

<div class="section">
<h3>Submission Timeline</h3>
<p>The following table shows the file modification timestamps for submissions involved in flagged cases.
Timing discrepancies may provide additional context for the committee's review.</p>
<table>
<tr><th>Student</th><th>File</th><th>Timestamp</th></tr>
"""

    timeline_entries = set()
    for c in suspicious:
        timeline_entries.add(c.file_a)
        timeline_entries.add(c.file_b)

    for fn in sorted(timeline_entries):
        info = student_info.get(fn, {"name": fn, "id": "N/A"})
        fpath = PathLib(fn)
        timestamp = "N/A"
        try:
            if fpath.exists():
                mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
                timestamp = mtime.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            pass
        html += f'<tr><td>{info["name"]} (ID: {info["id"]})</td><td>{fn}</td><td>{timestamp}</td></tr>\n'

    html += f"""
</table>
</div>

<div class="section">
<h3>Methodology</h3>
<p>This analysis was conducted using <strong>IntegrityDesk</strong>, a multi-engine code similarity
detection system employing six independent forensic engines:</p>
<ul>
<li><strong>AST Engine:</strong> Abstract Syntax Tree structural comparison -- detects similarity even when variable names, comments, or code ordering have been changed.</li>
<li><strong>Winnowing Engine:</strong> K-gram fingerprinting for copy-paste detection -- resilient to whitespace and formatting changes.</li>
<li><strong>N-gram Engine:</strong> Character and token sequence matching -- identifies shared code patterns at the lexical level.</li>
<li><strong>Embedding Engine:</strong> Semantic similarity via code embeddings -- detects functionally equivalent code with different implementations.</li>
<li><strong>Execution Engine:</strong> Runtime output comparison -- verifies behavioral equivalence.</li>
<li><strong>Token Engine:</strong> Token frequency and TF-IDF analysis -- statistical profiling of code style.</li>
</ul>
<p><strong>Resilience to Obfuscation:</strong> This ensemble approach is specifically designed to detect
similarity even when students attempt to conceal copying through common obfuscation techniques,
including renaming variables, reordering functions, altering comments, or modifying whitespace.
A high score across multiple independent engines provides strong evidence that the similarity
is structural and intentional rather than coincidental.</p>
<p>Results are fused using a <strong>weighted Bayesian arbitration</strong> model that produces
the final similarity scores presented in this report. Only engines that successfully executed
are included in the fusion calculation.</p>
</div>

<div class="section">
<h3>Disclaimer</h3>
<p>This report is generated by an automated analysis system and is intended to assist the Academic
Integrity Committee in its investigation. The similarity scores indicate structural and semantic
similarities between code submissions but do not constitute definitive proof of academic misconduct.
The committee should consider these findings alongside other evidence, including but not limited to:
submission timestamps, student statements, exam conditions, and historical patterns.</p>
<p>All similarity detections include a feature breakdown and source code excerpts to enable
transparent review of which specific aspects of the code triggered the similarity flags.</p>
</div>

<div class="signature">
<div>
<div class="signature-line">Instructor Signature</div>
</div>
<div>
<div class="signature-line">Date</div>
</div>
</div>

<div class="footer">
<p>Generated by IntegrityDesk | Case ID: {job_id} | {report_date_short}</p>
<p>This document is confidential and intended solely for the Academic Integrity Committee.</p>
</div>

</body>
</html>
"""
    output_path.write_text(html, encoding='utf-8')


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)


if __name__ == "__main__":
    main()
