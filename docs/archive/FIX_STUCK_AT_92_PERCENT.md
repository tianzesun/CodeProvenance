# Fix: Plagiarism Checker Stuck at 92%

## Problem
The plagiarism checker gets stuck at 92% progress and never completes.

## Why This Happens
The frontend progress bar is intentionally capped at 92% while waiting for the backend to complete processing. However, **the backend server is running OLD code** (before the background task fix), which causes it to:
1. Try to process everything synchronously
2. Hit timeout or error
3. Never return a "completed" response
4. Frontend stays stuck at 92% waiting forever

## Solution: Restart Backend Server

The code fix has been applied, but you need to **restart the backend server** to load the new code.

### Option 1: Use the Restart Script
```bash
cd /home/tsun/Documents/CodeProvenance
./RESTART_BACKEND.sh
```

### Option 2: Manual Restart

#### Step 1: Stop the old backend
```bash
# Find the backend process
ps aux | grep "uvicorn src.backend.api.server:app" | grep -v grep

# Kill it (replace PID with actual process ID)
pkill -f "uvicorn src.backend.api.server:app"

# OR if running in a terminal, press Ctrl+C
```

#### Step 2: Start the new backend
```bash
cd /home/tsun/Documents/CodeProvenance
source venv/bin/activate
uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --reload
```

**Note**: The `--reload` flag makes the server automatically reload when code changes, avoiding this issue in the future.

### Option 3: If Backend is Running in a Terminal
1. Go to the terminal running uvicorn
2. Press `Ctrl+C` to stop it
3. Run the same command again to restart

## Verify the Fix

After restarting:

1. **Test the upload**:
   - Go to http://localhost:3000/upload
   - Upload 2 Python files
   - Click "Analyze"
   
2. **Expected behavior**:
   - Progress shows up to 92%
   - Then **immediately** jumps to 100% (backend returns "processing" status)
   - Starts polling every second
   - Analysis runs in background
   - After 30-120 seconds, redirects to results page

3. **Check in browser DevTools** (F12 → Network tab):
   - POST `/api/upload` returns quickly: `{"job_id":"abc123", "status":"processing"}`
   - Multiple GET `/api/jobs/abc123` requests (polling)
   - Final GET returns: `{"status":"completed", ...}`

## What Changed in the Code

**Before** (OLD CODE - causes stuck at 92%):
```python
@app.post("/api/upload")
async def upload_files(...):
    # ... upload files ...
    return await _run_analysis(...)  # ❌ Blocks here for 1-3 minutes
```

**After** (NEW CODE - returns immediately):
```python
@app.post("/api/upload")
async def upload_files(..., background_tasks: BackgroundTasks):
    # ... upload files ...
    background_tasks.add_task(_run_analysis_background, ...)  # ✅ Runs in background
    return JSONResponse({"job_id": job_id, "status": "processing"})  # ✅ Returns immediately
```

## Troubleshooting

### Still stuck at 92%?

**Check if backend restarted**:
```bash
ps aux | grep uvicorn | grep server:app
# Should show recent start time
```

**Check backend logs**:
Look for errors in the terminal where uvicorn is running.

**Check job status manually**:
```bash
# Find recent upload
ls -lt /home/tsun/Documents/CodeProvenance/uploads/ | head -5

# Check job status (replace JOB_ID)
curl http://127.0.0.1:8000/api/jobs/JOB_ID | jq
```

**Expected responses**:
- While processing: `{"status": "processing", ...}` or `{"status": "analyzing", ...}`
- When done: `{"status": "completed", ...}`
- On error: `{"status": "failed", "error": "...", ...}`

### Backend won't start?

**Check if port 8000 is in use**:
```bash
lsof -i :8000
# Kill any process using it
kill -9 <PID>
```

**Check for Python errors**:
```bash
cd /home/tsun/Documents/CodeProvenance
source venv/bin/activate
python -c "from src.backend.api.server import app; print('OK')"
```

### Frontend issues?

**Clear browser cache**:
1. Open DevTools (F12)
2. Right-click refresh button
3. Select "Empty Cache and Hard Reload"

**Check frontend is running**:
```bash
# Should be running on port 3000
curl http://localhost:3000
```

## Quick Checklist

- [ ] Backend server restarted with new code
- [ ] Backend shows recent start time in `ps aux`
- [ ] Upload 2 files on http://localhost:3000/upload
- [ ] Click "Analyze"
- [ ] Progress goes to 92% then quickly returns
- [ ] Polling starts (see Network tab)
- [ ] After 30-120 seconds, redirects to results

## Why Use --reload Flag?

Adding `--reload` when starting uvicorn means:
- Server automatically reloads when Python files change
- No need to manually restart after code changes
- Useful during development
- **Recommended for testing this fix**

```bash
uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --reload
```

## Files Modified

All changes are in: `src/backend/api/server.py`
- Added `_run_analysis_background()` function
- Updated `/api/upload` endpoint
- Updated `/api/upload-zip` endpoint

No database migrations or frontend changes needed.

## Success Indicators

✅ Backend restarts without errors  
✅ POST /api/upload returns in < 1 second  
✅ Response includes `"status": "processing"`  
✅ Frontend starts polling GET /api/jobs/{id}  
✅ Progress bar completes (not stuck at 92%)  
✅ Results page loads after analysis completes  

## Contact

If issues persist after restart:
1. Check backend logs for errors
2. Check frontend browser console for errors
3. Verify both backend and frontend are running
4. Try with very small test files first
