# Testing the Plagiarism Checker Timeout Fix

## Quick Start Test

1. **Start the backend server**:
   ```bash
   cd /home/tsun/Documents/CodeProvenance
   source venv/bin/activate
   uvicorn src.backend.api.server:app --port 8000 --reload
   ```

2. **Start the frontend** (in another terminal):
   ```bash
   cd /home/tsun/Documents/CodeProvenance
   npm run dev
   ```

3. **Navigate to**: http://localhost:3000/upload

## Test Cases

### Test 1: Two-File Upload (Basic)
**Expected**: No timeout, immediate response, background processing

**Steps**:
1. Go to Plagiarism Checker page
2. Upload 2 Python files (can be any `.py` files)
3. Click "Analyze"
4. **Expected Result**:
   - Page should show "Analyzing submissions..." immediately
   - Progress bar should appear
   - No timeout error
   - After processing completes, redirect to results page

**What Changed**:
- Before: Request would timeout after 30-120 seconds
- After: Returns immediately, polls for completion

### Test 2: Complex Analysis (Multiple Engines)
**Expected**: Background processing handles long-running analysis

**Steps**:
1. Upload 2 larger code files (>500 lines each)
2. Ensure "IntegrityDesk" tool is selected (uses all 5 engines)
3. Click "Analyze"
4. **Expected Result**:
   - Immediate response
   - Progress updates
   - Completes without timeout (may take 1-2 minutes)

### Test 3: ZIP Upload (Multiple Files)
**Expected**: Handles many files without timeout

**Steps**:
1. Create a ZIP with 5-10 Python files
2. Upload the ZIP file
3. Click "Analyze"
4. **Expected Result**:
   - Immediate response
   - Background processing of all pairs
   - Results page shows all comparisons

### Test 4: Error Handling
**Expected**: Graceful error handling

**Steps**:
1. Upload 2 invalid files (e.g., empty files or non-code files)
2. Try to analyze
3. **Expected Result**:
   - Clear error message
   - No server crash
   - Can retry with valid files

## Monitoring

### Check Backend Logs
```bash
# Watch backend logs for background task execution
tail -f <terminal_running_uvicorn>
```

**Look for**:
- `"Background analysis failed for job {job_id}"` - Error case
- `"Analysis completed for job {job_id}"` - Success case
- `"Job {job_id} completed with persistence warning"` - Warning case

### Check Network Tab (Browser DevTools)
1. Open browser DevTools (F12)
2. Go to Network tab
3. Upload files and analyze
4. **Expected**:
   - POST `/api/upload` returns quickly (< 1 second) with `{"job_id": "...", "status": "processing"}`
   - Multiple GET `/api/jobs/{id}` requests polling every ~1 second
   - Final GET returns `{"status": "completed", ...}`

### Check Job Status
Manual API check:
```bash
# Get job status (replace JOB_ID with actual job ID)
curl http://localhost:8000/api/jobs/JOB_ID
```

## Success Criteria

✅ **No timeout errors** when uploading 2 files  
✅ **Immediate API response** (< 1 second) with "processing" status  
✅ **Progress indicator** shows while processing  
✅ **Results page loads** after analysis completes  
✅ **Multiple concurrent uploads** work without blocking  
✅ **Error handling** works (failed jobs show error message)  

## Troubleshooting

### Issue: Still getting timeout
**Check**:
- Is backend server running with the updated code?
- Restart backend server: `Ctrl+C` then restart uvicorn
- Check browser console for errors
- Verify frontend is polling (Network tab should show repeated GET requests)

### Issue: Job stuck in "processing"
**Check**:
- Backend logs for errors
- Job status: `curl http://localhost:8000/api/jobs/{job_id}`
- Reports directory: `ls -la /home/tsun/Documents/CodeProvenance/reports/{job_id}/`

### Issue: "This page couldn't load"
**Check**:
- This was the original error, should be fixed now
- If still occurs, check backend logs for exceptions
- Verify background task is running (check logs)

## Performance Notes

**Before Fix**:
- 2 files, all engines: ~60-120 seconds (would timeout)
- API blocks during entire analysis
- Server can't handle concurrent requests

**After Fix**:
- API response: < 1 second
- Background processing: 30-120 seconds (no timeout)
- Server handles multiple concurrent uploads
- Better user experience with progress indicators

## Rollback Plan

If issues occur, the fix can be reverted by:

1. **Revert backend changes**:
   ```bash
   git diff src/backend/api/server.py  # Review changes
   git checkout HEAD -- src/backend/api/server.py  # Revert if needed
   ```

2. **Increase frontend timeout** (temporary workaround):
   - Edit `src/frontend/lib/apiClient.ts`
   - Increase timeout to 300000 (5 minutes)
   - This allows synchronous processing but is not ideal

## Additional Notes

- Frontend polling logic was already implemented (`startPolling` function)
- Fix follows existing pattern from AI Detector endpoint
- Database persistence is non-fatal (file-based storage is primary)
- Job status persists across server restarts (saved to disk)
