"""Simple Web GUI for plagiarism detection review.

Run: uvicorn src.web_gui:app --reload
"""
from typing import Dict, List, Any
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pydantic import BaseModel

UPLOAD_DIR = Path("./uploads")
RESULTS_DIR = Path("./results")

@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)
    yield

app = FastAPI(title="IntegrityDesk", version="1.0", lifespan=lifespan)

class AnalysisRequest(BaseModel):
    threshold: float = 0.5

@app.get("/", response_class=HTMLResponse)
async def index():
    return """<html><head><title>IntegrityDesk</title><style>
    body { font-family: Arial, sans-serif; margin: 40px; }
    form { max-width: 600px; margin: 0 auto; }
    .threshold { margin: 20px 0; }
    </style></head><body>
    <h1>IntegrityDesk - Plagiarism Detection</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
        <input type="file" name="files" multiple accept=".py,.java,.c,.cpp,.js,.ts" required><br><br>
        <div class="threshold">Threshold: <input type="range" name="threshold" min="0" max="1" step="0.05" value="0.5" oninput="document.getElementById('val').textContent=this.value"><span id="val">0.5</span></div>
        <button type="submit">Analyze</button>
    </form>
    <p><a href="/reports">View Reports</a></p>
    </body></html>"""

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), threshold: float = 0.5):
    from src.application.services.batch_detection_service import BatchDetectionService
    
    # Save files
    UPLOAD_DIR.mkdir(exist_ok=True)
    for f in files:
        content = await f.read()
        (UPLOAD_DIR / f.filename).write_bytes(content)
    
    # Run analysis
    service = BatchDetectionService(threshold=threshold)
    report = service.run_analysis(UPLOAD_DIR, RESULTS_DIR / "analysis.json")
    
    return {"upload_count": len(files), "report": report}

@app.get('/reports')
async def reports():
    report_path = RESULTS_DIR / "analysis.json"
    if not report_path.exists():
        return "No reports yet. <a href='/'>Upload files</a>"
    import json
    report = json.loads(report_path.read_text())
    
    html = '<h1>Analysis Report</h1>'
    html += f"<p>Total pairs: {report['summary']['total_pairs']}</p>"
    html += f"<p>Suspicious: {report['summary']['suspicious_pairs']} (threshold: {report['summary']['threshold']})</p>"
    
    html += '<h2>Suspicious Pairs</h2><table border="1"><tr><th>File A</th><th>File B</th><th>Score</th><th>Risk</th></tr>'
    for r in report.get('suspicious', []):
        html += f"<tr><td>{r['file_a']}</td><td>{r['file_b']}</td><td>{r['score']}</td><td>{r['risk']}</td></tr>"
    html += '</table>'
    
    html += '<h2>All Results</h2><table border="1"><tr><th>File A</th><th>File B</th><th>Score</th></tr>'
    for r in report.get('all_results', []):
        html += f"<tr><td>{r['file_a']}</td><td>{r['file_b']}</td><td>{r['score']}</td></tr>"
    html += '</table>'
    
    return HTMLResponse(html)
