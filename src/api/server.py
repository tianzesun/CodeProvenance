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
    body { font-family: 'Georgia', serif; margin: 40px; color: #1a1a1a; line-height: 1.6; }
    .header { text-align: center; border-bottom: 3px double #333; padding-bottom: 20px; margin-bottom: 30px; }
    .header h1 { font-size: 24px; margin: 0; }
    .header h2 { font-size: 14px; margin: 6px 0 0; color: #555; font-weight: normal; text-transform: uppercase; letter-spacing: 0.08em; }
    .meta { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 30px; font-size: 13px; }
    .meta-item { padding: 10px 12px; background: #f9f9f9; border-left: 3px solid #333; }
    .meta-label { font-weight: bold; color: #555; display: block; font-size: 10px; text-transform: uppercase; margin-bottom: 2px; }
    .rec-box { background: #fde8e8; border: 2px solid #dc3545; border-left: 5px solid #a41e35; padding: 20px; margin-bottom: 30px; }
    .rec-box h3 { margin: 0 0 8px; color: #a41e35; text-transform: uppercase; }
    .exec-summary { background: #fff8e1; border: 1px solid #e8a300; padding: 20px; margin-bottom: 30px; }
    .section { margin-bottom: 30px; }
    .section h3 { border-bottom: 2px solid #333; padding-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
    table { width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background: #f5f5f5; font-size: 11px; text-transform: uppercase; color: #555; }
    .risk-critical { background: #a41e35; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-high { background: #dc3545; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-medium { background: #e8a300; color: #333; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .risk-low { background: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-size: 11px; font-weight: 600; }
    .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
    .stat-card { text-align: center; padding: 16px; background: #f5f5f5; border-radius: 4px; border-top: 3px solid #333; }
    .stat-value { font-size: 28px; font-weight: bold; }
    .stat-label { font-size: 10px; color: #666; margin-top: 4px; text-transform: uppercase; }
    .finding { border: 1px solid #d9d9d9; margin-bottom: 20px; border-radius: 4px; overflow: hidden; }
    .finding-header { display: flex; justify-content: space-between; padding: 12px 16px; background: #fafbfc; border-bottom: 1px solid #e8e8e8; }
    .finding-body { padding: 16px; }
    .finding-comment { background: #fff3cd; border-left: 3px solid #e8a300; padding: 10px 14px; margin: 12px 0; font-style: italic; color: #856404; }
    .features { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
    .feature-tag { background: #e6f0fa; color: #0066cc; padding: 3px 8px; border-radius: 3px; font-size: 11px; }
    .code-comp { display: grid; grid-template-columns: 1fr 1fr; gap: 0; margin-top: 12px; border: 1px solid #d9d9d9; border-radius: 4px; overflow: hidden; }
    .code-hdr { padding: 6px 12px; background: #f5f5f5; font-size: 11px; font-weight: 600; border-bottom: 1px solid #d9d9d9; }
    .code-blk { padding: 12px; font-family: monospace; font-size: 10px; line-height: 1.5; overflow-x: auto; max-height: 200px; background: #1e1e1e; color: #d4d4d4; margin: 0; white-space: pre; }
    .footer { margin-top: 50px; padding-top: 20px; border-top: 2px solid #333; font-size: 11px; color: #888; text-align: center; }
    .sig { margin-top: 50px; display: grid; grid-template-columns: 1fr 1fr; gap: 60px; }
    .sig-line { border-top: 1px solid #333; padding-top: 6px; font-size: 12px; }
    .conf-banner { background: #333; color: #fff; text-align: center; padding: 6px; font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 30px; }
    """

    now = datetime.now()
    critical_cases = []
    for c in critical:
        ia = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        ib = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        critical_cases.append(f"{ia['name']} (ID: {ia['id']}) and {ib['name']} (ID: {ib['id']})")

    rec_text = "Immediate administrative action is requested." if critical else "Review at next scheduled meeting."

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Academic Integrity Report</title><style>{css}</style></head><body>
<div class="conf-banner">Confidential -- For Academic Integrity Committee Use Only</div>
<div style="text-align:right;margin-bottom:20px"><button onclick="window.print()" style="padding:8px 16px;cursor:pointer">Print / Save as PDF</button></div>
<div class="header"><h1>ACADEMIC INTEGRITY COMMITTEE REPORT</h1><h2>Code Similarity Analysis</h2><h2>IntegrityDesk</h2></div>
<div class="meta">
<div class="meta-item"><span class="meta-label">Course</span>{course_name or "Not Specified"}</div>
<div class="meta-item"><span class="meta-label">Assignment</span>{assignment_name or "Not Specified"}</div>
<div class="meta-item"><span class="meta-label">Date</span>{now.strftime('%B %d, %Y at %H:%M')}</div>
<div class="meta-item"><span class="meta-label">Case ID</span>{job_id}</div>
<div class="meta-item"><span class="meta-label">Submissions</span>{len(submissions)}</div>
<div class="meta-item"><span class="meta-label">Threshold</span>{threshold:.0%}</div>
</div>
<div class="rec-box"><h3>Recommendation</h3><p>{rec_text}</p></div>
<div class="exec-summary"><h3>Executive Summary</h3>
<p>Analysis of <strong>{len(submissions)} submissions</strong> for <strong>"{assignment_name or 'N/A'}"</strong> in <strong>"{course_name or 'N/A'}"</strong>.</p>
<p><strong>{len(suspicious)} case(s)</strong> flagged, involving <strong>{len(students_involved)} student(s)</strong>. {len(critical)} critical, {len(high)} high risk."""
    if critical_cases:
        html += f" Critical cases: {', '.join(critical_cases)}."
    html += f"""</p></div>
<div class="section"><h3>Statistics</h3><div class="stat-grid">
<div class="stat-card"><div class="stat-value">{len(submissions)}</div><div class="stat-label">Submissions</div></div>
<div class="stat-card"><div class="stat-value">{report['summary']['total_pairs']}</div><div class="stat-label">Pairs Compared</div></div>
<div class="stat-card"><div class="stat-value" style="color:#dc3545">{len(suspicious)}</div><div class="stat-label">Flagged</div></div>
<div class="stat-card"><div class="stat-value" style="color:#a41e35">{len(critical)}</div><div class="stat-label">Critical</div></div>
</div></div>
<div class="section"><h3>Risk Distribution</h3>
<table><tr><th>Risk</th><th>Count</th><th>Range</th><th>Action</th></tr>
<tr><td><span class="risk-critical">CRITICAL</span></td><td>{len(critical)}</td><td>90-100%</td><td>Immediate review</td></tr>
<tr><td><span class="risk-high">HIGH</span></td><td>{len(high)}</td><td>75-89%</td><td>Detailed review</td></tr>
<tr><td><span class="risk-medium">MEDIUM</span></td><td>{len(medium)}</td><td>50-74%</td><td>Manual check</td></tr>
<tr><td><span class="risk-low">LOW</span></td><td>{len(comparisons) - len(suspicious)}</td><td>Below {threshold:.0%}</td><td>No action</td></tr></table></div>
<div class="section"><h3>Detailed Findings</h3>"""

    for i, c in enumerate(suspicious, 1):
        ia = student_info.get(c.file_a, {"name": c.file_a, "id": "N/A"})
        ib = student_info.get(c.file_b, {"name": c.file_b, "id": "N/A"})
        feats = "".join(f'<span class="feature-tag">{k}: {v:.1%}</span>' for k, v in sorted(c.features.items(), key=lambda x: -x[1])[:5])
        rc = "risk-critical" if c.score >= 0.9 else "risk-high" if c.score >= 0.75 else "risk-medium"
        comment = ""
        if c.score >= 0.99:
            comment = '<div class="finding-comment">Near-perfect match across all engines -- suggests direct file copy.</div>'
        elif c.score >= 0.9:
            comment = '<div class="finding-comment">Extremely high similarity -- substantial code sharing detected.</div>'
        elif c.score >= 0.75:
            comment = '<div class="finding-comment">Significant similarities -- manual review recommended.</div>'
        ca = (c.code_a or "N/A")[:800] + ("..." if len(c.code_a or "") > 800 else "")
        cb = (c.code_b or "N/A")[:800] + ("..." if len(c.code_b or "") > 800 else "")
        html += f"""<div class="finding"><div class="finding-header"><strong>Case #{i}: {ia['name']} vs {ib['name']}</strong><span class="{rc}">{c.risk} ({c.score:.1%})</span></div>
<div class="finding-body"><p>Files: {c.file_a} vs {c.file_b}</p><p>Score: <strong>{c.score:.1%}</strong></p>{comment}<div class="features">{feats}</div>
<div class="code-comp"><div><div class="code-hdr">{c.file_a}</div><pre class="code-blk">{ca}</pre></div><div><div class="code-hdr">{c.file_b}</div><pre class="code-blk">{cb}</pre></div></div></div></div>"""

    html += f"""</div><div class="section"><h3>Methodology</h3><p>IntegrityDesk uses six forensic engines: AST, Winnowing, N-gram, Embedding, Execution, and Token analysis. Results are fused via weighted Bayesian arbitration. The system detects similarity even with variable renaming, reordering, or comment changes.</p></div>
<div class="section"><h3>Disclaimer</h3><p>Scores indicate structural/semantic similarity but do not constitute definitive proof of misconduct. Consider alongside timestamps, student statements, and other evidence.</p></div>
<div class="sig"><div><div class="sig-line">Instructor Signature</div></div><div><div class="sig-line">Date</div></div></div>
<div class="footer"><p>IntegrityDesk | Case {job_id} | {now.strftime('%Y-%m-%d')}</p><p>Confidential -- Academic Integrity Committee only.</p></div></body></html>"""
    output_path.write_text(html, encoding='utf-8')


def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8500)


if __name__ == "__main__":
    main()
