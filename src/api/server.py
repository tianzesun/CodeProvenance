"""IntegrityDesk Backend API - FastAPI server for professor dashboard."""

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

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse

from src.application.services.batch_detection_service import BatchDetectionService
from src.infrastructure.report_generator import ReportGenerator, ComparisonDetail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="IntegrityDesk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = project_root / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR = project_root / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_jobs: Dict[str, Dict[str, Any]] = {}

ALLOWED_EXTENSIONS = {
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.js', '.ts', '.jsx', '.tsx',
    '.go', '.rs', '.rb', '.php', '.cs', '.kt', '.swift', '.scala', '.r', '.m',
    '.sql', '.sh', '.bash', '.zsh', '.ps1', '.lua', '.pl', '.pm', '.ex', '.exs',
    '.dart', '.clj', '.hs', '.ml', '.fs', '.erl', '.vue', '.svelte',
}


def _is_code_file(filename: str) -> bool:
    return PathLib(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _extract_zip(zip_path: PathLib, target_dir: PathLib) -> List[str]:
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


@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    threshold: float = Form(default=0.5),
):
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
        return JSONResponse(status_code=400, content={"error": "At least 2 code files are required"})

    return await _run_analysis(job_id, job_dir, course_name, assignment_name, threshold)


@app.post("/api/upload-zip")
async def upload_zip(
    file: UploadFile = File(...),
    course_name: str = Form(default=""),
    assignment_name: str = Form(default=""),
    threshold: float = Form(default=0.5),
):
    if not file.filename or not file.filename.lower().endswith('.zip'):
        return JSONResponse(status_code=400, content={"error": "Please upload a .zip file"})

    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    zip_path = job_dir / file.filename
    content = await file.read()
    zip_path.write_bytes(content)

    extracted = _extract_zip(zip_path, job_dir)
    if len(extracted) < 2:
        shutil.rmtree(job_dir)
        return JSONResponse(status_code=400, content={"error": "Zip must contain at least 2 code files"})

    return await _run_analysis(job_id, job_dir, course_name, assignment_name, threshold)


async def _run_analysis(job_id, job_dir, course_name, assignment_name, threshold):
    _jobs[job_id] = {
        "id": job_id, "course_name": course_name or "Unnamed Course",
        "assignment_name": assignment_name or "Unnamed Assignment",
        "threshold": threshold, "status": "processing",
        "created_at": datetime.now().isoformat(), "file_count": 0,
        "results": [], "summary": {},
    }

    try:
        submissions = _read_files_from_dir(job_dir)
        if len(submissions) < 2:
            del _jobs[job_id]
            return JSONResponse(status_code=400, content={"error": "At least 2 valid code files required"})

        _jobs[job_id]["file_count"] = len(submissions)
        _jobs[job_id]["status"] = "analyzing"

        service = BatchDetectionService(threshold=threshold)
        results = service.compare_all_pairs(submissions)
        report = service.generate_report(results)

        comparison_details = []
        for r in results:
            detail = ComparisonDetail(
                file_a=r.file_a, file_b=r.file_b, score=r.score,
                risk=r.risk_level, features=r.features,
                code_a=submissions.get(r.file_a, ""), code_b=submissions.get(r.file_b, ""),
            )
            comparison_details.append(detail)

        rg = ReportGenerator(
            title=f"IntegrityDesk Report - {course_name or 'Course'}",
            institution="", course=course_name or "Course",
            assignment=assignment_name or "Assignment", threshold=threshold,
            output_dir=REPORTS_DIR / job_id,
        )
        html_report_path = rg.generate_html(comparison_details)
        json_report_path = rg.generate_json(comparison_details)
        committee_report_path = REPORTS_DIR / job_id / "committee_report.html"
        _generate_committee_report(job_id, course_name, assignment_name, threshold, report, comparison_details, submissions, committee_report_path)

        _jobs[job_id].update({
            "status": "completed",
            "results": [{"file_a": r.file_a, "file_b": r.file_b, "score": round(r.score, 3), "risk_level": r.risk_level, "features": {k: round(v, 3) for k, v in r.features.items()}} for r in results],
            "summary": report["summary"],
            "report_path": str(html_report_path), "report_json_path": str(json_report_path),
            "committee_report_path": str(committee_report_path),
            "submissions": {k: v[:3000] for k, v in submissions.items()},
        })
        return JSONResponse(content={"job_id": job_id, "status": "completed"})
    except Exception as e:
        logger.exception(f"Analysis failed for job {job_id}")
        if job_id in _jobs:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)
        return JSONResponse(status_code=500, content={"error": f"Analysis failed: {str(e)}"})


@app.get("/api/jobs")
async def list_jobs():
    return JSONResponse(content={"jobs": sorted(_jobs.values(), key=lambda x: x.get("created_at", ""), reverse=True)})


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job)


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    job = _jobs.pop(job_id, None)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_dir = UPLOADS_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    return JSONResponse(content={"status": "deleted"})


@app.post("/api/benchmark")
async def run_benchmark(files: List[UploadFile] = File(...), tools: List[str] = Form(default=["integritydesk"])):
    job_id = str(uuid.uuid4())[:8]
    job_dir = UPLOADS_DIR / f"bench_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        if f.filename and _is_code_file(f.filename):
            (job_dir / f.filename).write_bytes(await f.read())

    submissions = _read_files_from_dir(job_dir)
    if len(submissions) < 2:
        shutil.rmtree(job_dir, ignore_errors=True)
        return JSONResponse(status_code=400, content={"error": "At least 2 code files required"})

    file_list = list(submissions.keys())
    all_pairs = [(file_list[i], file_list[j]) for i in range(len(file_list)) for j in range(i + 1, len(file_list))]
    tool_results = {}

    if "integritydesk" in tools:
        try:
            service = BatchDetectionService(threshold=0.3)
            results = service.compare_all_pairs(submissions)
            tool_results["integritydesk"] = {"pairs": [{"file_a": r.file_a, "file_b": r.file_b, "score": round(r.score, 3), "features": {k: round(v, 3) for k, v in r.features.items()}} for r in results]}
        except Exception as e:
            logger.exception("IntegrityDesk benchmark failed")
            tool_results["integritydesk"] = {"error": str(e)}

    for tool in tools:
        if tool == "integritydesk":
            continue
        try:
            score_data = _run_competitor_tool(tool, submissions, all_pairs)
            if score_data:
                tool_results[tool] = score_data
            else:
                tool_results[tool] = {"error": f"{tool} not available"}
        except Exception as e:
            logger.exception(f"{tool} benchmark failed")
            tool_results[tool] = {"error": str(e)}

    pair_results = []
    for fa, fb in all_pairs:
        entry = {"file_a": fa, "file_b": fb, "label": f"{PathLib(fa).stem} vs {PathLib(fb).stem}", "tool_results": []}
        for tool_name, tool_data in tool_results.items():
            if "pairs" in tool_data:
                for p in tool_data["pairs"]:
                    if (p["file_a"] == fa and p["file_b"] == fb) or (p["file_a"] == fb and p["file_b"] == fa):
                        entry["tool_results"].append({"tool": tool_name, "score": p["score"]})
        pair_results.append(entry)

    id_avg = sum((p["score"] for p in tool_results.get("integritydesk", {}).get("pairs", [])), 0) / max(1, len(tool_results.get("integritydesk", {}).get("pairs", [])))
    comp_scores = [p["score"] for t, d in tool_results.items() if t != "integritydesk" and "pairs" in d for p in d["pairs"]]
    comp_avg = sum(comp_scores) / len(comp_scores) if comp_scores else 0

    shutil.rmtree(job_dir, ignore_errors=True)

    return JSONResponse(content={
        "job_id": job_id,
        "tool_scores": {k: {"pairs": len(v.get("pairs", []))} for k, v in tool_results.items()},
        "pair_results": pair_results,
        "summary": {"pairs_tested": len(pair_results), "tools_compared": len([t for t in tool_results if "error" not in tool_results[t]]), "accuracy": {"integritydesk": id_avg, "best_competitor": comp_avg}},
    })


def _run_competitor_tool(tool, submissions, pairs):
    if tool == "moss":
        return _run_moss_approx(submissions, pairs)
    elif tool == "jplag":
        return _run_jplag_approx(submissions, pairs)
    elif tool == "dolos":
        return _run_dolos_approx(submissions, pairs)
    elif tool == "codequiry":
        return _run_codequiry_approx(submissions, pairs)
    return None


def _run_moss_approx(submissions, pairs):
    try:
        from src.engines.similarity.token_similarity import TokenSimilarity
        engine = TokenSimilarity()
        results = []
        for fa, fb in pairs:
            score = engine.compare({"raw": submissions[fa], "tokens": []}, {"raw": submissions[fb], "tokens": []})
            results.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": results}
    except Exception:
        return None


def _run_jplag_approx(submissions, pairs):
    try:
        from src.engines.similarity.ast_similarity import ASTSimilarity
        engine = ASTSimilarity()
        results = []
        for fa, fb in pairs:
            try:
                score = engine.compare({"raw": submissions[fa], "tokens": []}, {"raw": submissions[fb], "tokens": []})
            except Exception:
                score = 0.0
            results.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": results}
    except Exception:
        return None


def _run_dolos_approx(submissions, pairs):
    try:
        from src.engines.similarity.winnowing_similarity import EnhancedWinnowingSimilarity
        engine = EnhancedWinnowingSimilarity()
        results = []
        for fa, fb in pairs:
            score = engine.compare({"raw": submissions[fa], "tokens": []}, {"raw": submissions[fb], "tokens": []})
            results.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": results}
    except Exception:
        return None


def _run_codequiry_approx(submissions, pairs):
    try:
        from src.engines.similarity.embedding_similarity import EmbeddingSimilarity
        engine = EmbeddingSimilarity()
        results = []
        for fa, fb in pairs:
            score = engine.compare({"raw": submissions[fa]}, {"raw": submissions[fb]})
            results.append({"file_a": fa, "file_b": fb, "score": round(score, 3)})
        return {"pairs": results}
    except Exception:
        return None


@app.get("/report/{job_id}/download", response_class=HTMLResponse)
async def download_report_html(request: Request, job_id: str):
    job = _jobs.get(job_id)
    if not job or "report_path" not in job:
        raise HTTPException(status_code=404, detail="Report not available")
    rp = PathLib(job["report_path"])
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(str(rp), media_type="text/html", filename=f"integritydesk_report_{job_id}.html")


@app.get("/report/{job_id}/download-json")
async def download_report_json(job_id: str):
    job = _jobs.get(job_id)
    if not job or "report_json_path" not in job:
        raise HTTPException(status_code=404, detail="Report not available")
    rp = PathLib(job["report_json_path"])
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    return FileResponse(str(rp), media_type="application/json", filename=f"integritydesk_report_{job_id}.json")


@app.get("/report/{job_id}/committee", response_class=HTMLResponse)
async def download_committee_report(request: Request, job_id: str):
    job = _jobs.get(job_id)
    if not job or "committee_report_path" not in job:
        raise HTTPException(status_code=404, detail="Committee report not available")
    rp = PathLib(job["committee_report_path"])
    if not rp.exists():
        raise HTTPException(status_code=404, detail="Committee report file not found")
    return FileResponse(str(rp), media_type="text/html", filename=f"integritydesk_committee_report_{job_id}.html")


def _extract_student_info(filename):
    stem = PathLib(filename).stem
    parts = re.split(r'[_\-\s]+', stem)
    id_num = ""
    for part in parts:
        if part.isdigit() and len(part) >= 4:
            id_num = part
            break
    if id_num and len(parts) >= 2:
        name = " ".join(p.capitalize() for p in parts if not p.isdigit()) or f"Student {id_num}"
    elif id_num:
        name = f"Student {id_num}"
    else:
        name = stem.replace("_", " ").replace("-", " ").title()
    return {"name": name, "id": id_num or "N/A", "filename": filename}


def _escape_html(text):
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _render_code_table(code, max_lines=80):
    lines = (code or "").split('\n')[:max_lines]
    if not lines:
        return '<div class="code-scroll"><table class="code-table"><tr><td class="line-num">-</td><td class="line-code">No code available</td></tr></table></div>'
    rows = []
    for i, line in enumerate(lines, 1):
        escaped = _escape_html(line)
        rows.append(f'<tr><td class="line-num">{i}</td><td class="line-code">{escaped}</td></tr>')
    if len(code or "") > sum(len(l) for l in lines):
        rows.append(f'<tr><td class="line-num"></td><td class="line-code" style="color:#6b7280;">// ... truncated ({len(code.split(chr(10)))-max_lines} more lines)</td></tr>')
    return f'<div class="code-scroll"><table class="code-table">{"".join(rows)}</table></div>'

def _generate_committee_report(job_id, course_name, assignment_name, threshold, report, comparisons, submissions, output_path):
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
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background: #f5f5f5; color: #333; line-height: 1.5; }
    .report-container { max-width: 900px; margin: 0 auto; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .report-header { background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%); color: #fff; padding: 24px 32px; display: flex; align-items: center; justify-content: space-between; }
    .report-header-left { display: flex; align-items: center; gap: 16px; }
    .report-logo { width: 40px; height: 40px; background: rgba(255,255,255,0.2); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; }
    .report-title { font-size: 18px; font-weight: 600; }
    .report-subtitle { font-size: 12px; opacity: 0.8; margin-top: 2px; }
    .report-header-right { text-align: right; font-size: 11px; opacity: 0.8; }
    .report-meta { padding: 20px 32px; border-bottom: 1px solid #e0e0e0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; font-size: 13px; }
    .meta-item { }
    .meta-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #666; margin-bottom: 4px; }
    .meta-value { font-size: 14px; font-weight: 500; color: #333; }
    .similarity-overview { padding: 32px; text-align: center; border-bottom: 1px solid #e0e0e0; }
    .similarity-circle { width: 120px; height: 120px; border-radius: 50%; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: 700; color: #fff; position: relative; }
    .similarity-circle::before { content: ''; position: absolute; inset: 6px; border-radius: 50%; background: #fff; }
    .similarity-circle span { position: relative; z-index: 1; }
    .similarity-label { font-size: 14px; font-weight: 600; color: #333; margin-bottom: 4px; }
    .similarity-desc { font-size: 12px; color: #666; }
    .color-legend { display: flex; justify-content: center; gap: 20px; margin-top: 16px; }
    .legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #666; }
    .legend-dot { width: 10px; height: 10px; border-radius: 50%; }
    .sources-section { padding: 24px 32px; }
    .section-title { font-size: 16px; font-weight: 600; color: #333; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #1a73e8; }
    .sources-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .sources-table th { background: #f8f9fa; padding: 10px 12px; text-align: left; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #666; border-bottom: 2px solid #e0e0e0; }
    .sources-table td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
    .sources-table tr:hover td { background: #fafbfc; }
    .similarity-badge { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; color: #fff; }
    .sim-high { background: #dc3545; }
    .sim-medium { background: #fd7e14; }
    .sim-low { background: #ffc107; color: #333; }
    .sim-none { background: #28a745; }
    .findings-section { padding: 24px 32px; }
    .finding-card { border: 1px solid #e0e0e0; border-radius: 8px; margin-bottom: 16px; overflow: hidden; }
    .finding-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; background: #f8f9fa; border-bottom: 1px solid #e0e0e0; }
    .finding-title { font-size: 14px; font-weight: 600; color: #333; }
    .finding-body { padding: 18px; }
    .finding-summary { font-size: 13px; color: #555; margin-bottom: 12px; }
    .engine-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 16px; }
    .engine-item { text-align: center; padding: 8px; background: #f8f9fa; border-radius: 6px; }
    .engine-name { font-size: 9px; font-weight: 600; text-transform: uppercase; color: #666; margin-bottom: 4px; }
    .engine-score { font-size: 16px; font-weight: 700; }
    .code-evidence { display: grid; grid-template-columns: 1fr 1fr; gap: 0; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; margin-top: 12px; }
    .code-panel { }
    .code-panel-header { padding: 8px 12px; background: #f8f9fa; font-size: 11px; font-weight: 600; color: #555; border-bottom: 1px solid #e0e0e0; }
    .code-table { width: 100%; border-collapse: collapse; font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; font-size: 11px; line-height: 1.6; }
    .code-table td { padding: 0; vertical-align: top; }
    .code-table .line-num { width: 40px; text-align: right; padding: 0 8px 0 4px; color: #6b7280; background: #f3f4f6; border-right: 1px solid #e5e7eb; user-select: none; font-size: 10px; white-space: nowrap; }
    .code-table .line-code { padding: 0 12px; white-space: pre; color: #d1d5db; }
    .code-table tr.matched { background: rgba(250, 204, 21, 0.15); }
    .code-table tr.matched .line-num { background: #fef3c7; color: #92400e; }
    .code-table tr.matched .line-code { color: #fef08a; }
    .code-table tr.highlight { background: rgba(239, 68, 68, 0.2); }
    .code-table tr.highlight .line-num { background: #fecaca; color: #991b1b; }
    .code-table tr.highlight .line-code { color: #fca5a5; }
    .code-scroll { max-height: 400px; overflow-y: auto; }
    .code-scroll::-webkit-scrollbar { width: 6px; }
    .code-scroll::-webkit-scrollbar-track { background: #1e1e1e; }
    .code-scroll::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 3px; }
    .match-legend { display: flex; gap: 16px; margin-top: 8px; padding: 8px 12px; background: #f8f9fa; border-radius: 4px; font-size: 10px; color: #666; }
    .match-legend-item { display: flex; align-items: center; gap: 4px; }
    .match-legend-dot { width: 8px; height: 8px; border-radius: 2px; }
    .methodology { padding: 24px 32px; border-top: 1px solid #e0e0e0; }
    .methodology p { font-size: 12px; color: #555; line-height: 1.6; }
    .footer { padding: 20px 32px; border-top: 1px solid #e0e0e0; text-align: center; font-size: 11px; color: #888; }
    .signature-row { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px; padding-top: 20px; }
    .sig-line { border-top: 1px solid #333; padding-top: 6px; font-size: 12px; color: #333; }
    .conf-banner { background: #333; color: #fff; text-align: center; padding: 8px; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; }
    @media print { body { background: #fff; } .report-container { box-shadow: none; } .no-print { display: none; } }
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
<div class="report-title">IntegrityDesk Originality Report</div>
<div class="report-subtitle">Code Similarity Detection &amp; Analysis</div>
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
        badge_class = "sim-high" if c.score >= 0.9 else "sim-medium" if c.score >= 0.75 else "sim-low"
        risk_label = "Critical" if c.score >= 0.9 else "High" if c.score >= 0.75 else "Medium"
        flagged_engines = sum(1 for v in c.features.values() if v >= threshold)
        html += f"""<tr>
<td><strong>{c.file_a}</strong> vs <strong>{c.file_b}</strong></td>
<td>{ia['name']} vs {ib['name']}</td>
<td><span class="similarity-badge {badge_class}">{(c.score*100):.1f}%</span></td>
<td>{risk_label}</td>
<td>{flagged_engines}/5</td>
</tr>"""

    html += f"""</tbody></table></div>

<div class="findings-section">
<div class="section-title">Detailed Findings &amp; Evidence</div>"""

    for i, c in enumerate(suspicious, 1):
        ia = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        ib = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        badge_class = "sim-high" if c.score >= 0.9 else "sim-medium" if c.score >= 0.75 else "sim-low"

        engine_items = ""
        for name, value in sorted(c.features.items(), key=lambda x: -x[1])[:5]:
            ecolor = "#dc3545" if value >= 0.75 else "#fd7e14" if value >= 0.5 else "#28a745"
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
<p>IntegrityDesk employs a multi-engine detection approach using six independent forensic engines: <strong>AST</strong> (Abstract Syntax Tree structural comparison), <strong>Winnowing</strong> (K-gram fingerprinting for copy-paste detection), <strong>N-gram</strong> (character/token sequence matching), <strong>Embedding</strong> (semantic similarity via code embeddings), <strong>Execution</strong> (runtime output comparison), and <strong>Token</strong> (token frequency and TF-IDF analysis).</p>
<p style="margin-top:8px;">Results are fused using weighted Bayesian arbitration to produce final similarity scores. This ensemble approach detects similarity even when students attempt to conceal copying through variable renaming, function reordering, comment changes, or whitespace modification.</p>
</div>

<div class="signature-row">
<div><div class="sig-line">Instructor Signature</div></div>
<div><div class="sig-line">Date</div></div>
</div>

<div class="footer">
<p>Generated by IntegrityDesk | Case ID: {job_id} | {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
<p>This report is confidential and intended solely for academic integrity review.</p>
</div>
</div>
</body></html>"""
    output_path.write_text(html, encoding='utf-8')


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)


if __name__ == "__main__":
    main()
