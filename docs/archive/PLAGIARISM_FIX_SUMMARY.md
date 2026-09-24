# Plagiarism Checker Timeout Fix - Summary

## Problem Statement
User reported: "when i do Plagiarism Checker (two files), it no longer working. it shows: timeout of 30000ms exceeded"

## Root Cause Analysis
The plagiarism checker was processing the entire analysis **synchronously**:
1. Upload files → Parse → Run 5 engines → External tools → AI detection → Generate reports → Return response
2. This could take 1-3 minutes for complex analyses
3. Frontend timeout (30s, later increased to 120s) was insufficient
4. Server blocked during processing, couldn't handle concurrent requests

## Solution Implemented
Converted to **asynchronous background processing** using FastAPI's BackgroundTasks:
1. Upload endpoints now return immediately with "processing" status
2. Analysis runs in background thread
3. Frontend polls for completion every second
4. No timeout issues, better scalability

## Changes Made

### File: `src/backend/api/server.py`

#### 1. Added Background Task Function
```python
def _run_analysis_background(
    job_id: str,
    job_dir: PathLib,
    # ... other params
) -> None:
    """Run analysis as background task to prevent timeouts."""
    # Creates new event loop and runs async _run_analysis()
    # Handles errors gracefully, updates job status
```

**Location**: Before `async def _run_analysis()` (line ~7139)

#### 2. Updated Upload Endpoints
**Both endpoints modified**:
- `@app.post("/api/upload")` - Two-file comparison
- `@app.post("/api/upload-zip")` - ZIP/multi-file comparison

**Changes**:
- Added `BackgroundTasks` parameter
- Changed from `await _run_analysis(...)` to `background_tasks.add_task(_run_analysis_background, ...)`
- Changed return from waiting for completion to immediate: `{"job_id": "...", "status": "processing"}`

#### 3. Modified Analysis Function
**Function**: `async def _run_analysis()`

**Changes**:
- Removed `JSONResponse` return statements (lines ~7548, 7560, 7578)
- Now just updates job status and logs completion
- Errors update job status to "failed" instead of returning error response

### File: `src/frontend/lib/apiClient.ts`
**No changes needed** - timeout already increased to 120000ms (2 minutes) in previous fix

## Architecture Flow

### Before (Synchronous)
```
Client                    Server
  |                         |
  |------ POST /upload ---->|
  |                         |--- Run all engines (60-120s)
  |                         |--- Generate reports
  |                         |--- Save to DB
  |<------ Response --------|
  |     (TIMEOUT after 30-120s)
```

### After (Asynchronous)
```
Client                    Server                  Background Task
  |                         |                            |
  |------ POST /upload ---->|                            |
  |                         |--- Save files              |
  |                         |--- Create job              |
  |                         |--- Start background ------>|
  |<--- Response (1s) ------|                            |
  | {"status":"processing"} |                            |
  |                         |                            |--- Run engines
  |--- GET /jobs/{id} ----->|                            |--- AI detection
  |<--- "processing" -------|                            |--- Generate reports
  |                         |                            |--- Save to DB
  |--- GET /jobs/{id} ----->|                            |
  |<--- "processing" -------|                            |
  |                         |                            |
  |--- GET /jobs/{id} ----->|                            |
  |<--- "completed" --------|<--- Update status ---------|
  |                         |
  | Redirect to results
```

## Benefits

✅ **No More Timeouts**: API returns in <1 second  
✅ **Better UX**: Users see progress, not just waiting  
✅ **Scalability**: Server handles multiple concurrent uploads  
✅ **Reliability**: Background processing isolates failures  
✅ **Consistency**: Matches AI Detector pattern (proven working)  

## Testing Status

✅ **Code compiles**: `python -m py_compile src/backend/api/server.py`  
✅ **Black formatted**: No style issues  
✅ **Ruff linting**: No linting errors  
✅ **Pattern verified**: Matches existing AI Detector implementation  

**Ready for user testing**: Needs actual upload test to verify end-to-end

## User Testing Steps

1. Start backend: `uvicorn src.backend.api.server:app --port 8000`
2. Start frontend: `npm run dev`
3. Go to http://localhost:3000/upload
4. Upload 2 Python files
5. Click "Analyze"
6. **Expected**: No timeout, shows progress, redirects to results

See `TESTING_PLAGIARISM_FIX.md` for detailed test cases.

## Rollback Plan

If issues occur:
```bash
# Revert backend changes
git checkout HEAD -- src/backend/api/server.py

# Alternative: Increase frontend timeout (temporary workaround)
# Edit src/frontend/lib/apiClient.ts, set timeout to 300000 (5 minutes)
```

## Code Style Compliance

✅ Follows PEP 8 style guide  
✅ Black formatted (max line length 100)  
✅ Ruff linting passed  
✅ Docstrings added for new function  
✅ Type hints used (Python 3.12 compatible)  
✅ Follows project patterns (matches AI Detector)  

## Files Created

1. **PLAGIARISM_CHECKER_TIMEOUT_FIX.md** - Technical documentation
2. **TESTING_PLAGIARISM_FIX.md** - Testing guide and test cases
3. **PLAGIARISM_FIX_SUMMARY.md** - This executive summary

## Next Steps

1. **User Testing**: Have user test the fix with actual uploads
2. **Monitor Logs**: Watch backend for any errors during background processing
3. **Performance Check**: Verify analysis completes in reasonable time
4. **Error Handling**: Test with invalid files to ensure graceful failures
5. **Concurrent Uploads**: Test multiple users uploading simultaneously

## Technical Notes

- Background tasks run in thread pool (FastAPI default)
- New event loop created for each background task (async compatibility)
- Job status persisted to disk (`reports/{job_id}/job.json`)
- Database persistence is non-fatal (file storage is primary)
- Frontend polling continues until "completed" or "failed" status
- Compatible with existing infrastructure (no schema changes needed)

## Impact Assessment

**User Impact**: 
- ✅ Positive - No more timeouts, better experience

**System Impact**: 
- ✅ Minimal - Uses existing background task infrastructure
- ✅ Compatible - No database schema changes
- ✅ Scalable - Better resource utilization

**Code Impact**: 
- Modified: 1 file (server.py)
- Added: 1 function (_run_analysis_background)
- Updated: 2 endpoints (upload, upload-zip)
- Lines changed: ~100 lines total

## Completion Status

✅ **Problem diagnosed**: Synchronous processing causing timeouts  
✅ **Solution designed**: Background task processing  
✅ **Code implemented**: All changes complete  
✅ **Code verified**: Compiles, formatted, linted  
✅ **Documentation created**: 3 documentation files  
✅ **Ready for testing**: Awaiting user validation  

**Status**: COMPLETE - Ready for user testing
