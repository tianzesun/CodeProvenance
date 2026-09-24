# Plagiarism Checker Timeout Fix

## Problem
When users uploaded two files for plagiarism checking, the request would timeout with "timeout of 30000ms exceeded" error. The plagiarism analysis was taking longer than the frontend's timeout limit.

## Root Cause
The plagiarism checker endpoints (`/api/upload` and `/api/upload-zip`) were running the entire analysis **synchronously** before returning a response:

1. Upload files
2. Run all similarity engines (Token, AST, Winnowing, GST, Semantic)
3. Run external tools (MOSS, JPlag, etc.)
4. Run AI detection
5. Generate reports (HTML, JSON, committee report)
6. Save to database
7. Finally return response

For complex analyses with multiple engines, this could take several minutes, causing timeouts.

## Solution
Converted the plagiarism checker to use **background task processing**, matching the pattern already used by the AI detector endpoint:

### Changes Made

#### 1. Frontend Timeout Increase
- **File**: `src/frontend/lib/apiClient.ts`
- Increased global timeout from 30 seconds to 120 seconds (2 minutes)
- This was already done in previous context, but still insufficient for synchronous processing

#### 2. Backend Endpoints Updated
- **File**: `src/backend/api/server.py`
- Added `BackgroundTasks` parameter to both upload endpoints
- Endpoints now return immediately with `{"job_id": "...", "status": "processing"}`
- Frontend polling mechanism (`startPolling`) handles checking for completion

**Modified Endpoints**:
- `POST /api/upload` - Two-file plagiarism comparison
- `POST /api/upload-zip` - Multi-file/ZIP plagiarism comparison

#### 3. Background Task Function Created
- **Function**: `_run_analysis_background()`
- Wraps the async `_run_analysis()` function to run in a background task
- Creates a new event loop for the background thread
- Handles errors gracefully by updating job status to "failed"
- Logs completion/errors without blocking the API response

#### 4. Analysis Function Updated
- **Function**: `_run_analysis()`
- Removed `JSONResponse` return statements (no longer needed for background tasks)
- Now updates job status in-memory and persists to disk
- Errors are logged and job status is updated to "failed"

## How It Works Now

### Upload Flow
```
1. User uploads files → POST /api/upload
2. Files are saved to disk
3. Job ID is created with status "processing"
4. Background task is started
5. Response returned immediately: {"job_id": "abc123", "status": "processing"}
6. Frontend starts polling GET /api/jobs/abc123 every second
```

### Background Processing
```
1. Analysis runs in background (engines, AI detection, reports)
2. Job status updates from "processing" → "analyzing" → "completed"
3. Results saved to disk and database
4. Frontend polling detects "completed" status
5. User redirected to results page
```

### Error Handling
```
- If analysis fails: status → "failed", error message stored
- If DB persistence fails: status → "completed" with warning
- Frontend polling shows error state to user
- All errors logged for debugging
```

## Benefits

1. **No More Timeouts**: API returns immediately, analysis runs in background
2. **Better UX**: Users see progress indicators while analysis runs
3. **Scalability**: Server can handle multiple concurrent uploads
4. **Consistent Pattern**: Matches AI detector implementation
5. **Existing Infrastructure**: Uses frontend's polling mechanism (already built)

## Testing Recommendations

1. **Two-file upload**: Upload two Python files, verify no timeout
2. **ZIP upload**: Upload ZIP with 10+ files, verify background processing
3. **Large files**: Upload large code files (>1000 lines each)
4. **Multiple engines**: Select all engines (Token, AST, Winnowing, GST, Semantic)
5. **External tools**: Enable MOSS/JPlag and verify processing completes
6. **Error handling**: Test with invalid files to verify error handling

## Files Modified

- `src/backend/api/server.py`:
  - Added `_run_analysis_background()` function
  - Updated `upload_files()` endpoint with BackgroundTasks
  - Updated `upload_zip()` endpoint with BackgroundTasks
  - Modified `_run_analysis()` to work as background task
  - Removed JSONResponse returns from analysis function

- `src/frontend/lib/apiClient.ts`:
  - Timeout already increased to 120000ms (from previous fix)

## Notes

- The 2-minute frontend timeout is now mainly a safety net
- Actual processing time is unlimited (runs in background)
- Frontend polling continues until job completes or fails
- Job status is persisted to disk, survives server restarts
- Database persistence failures are non-fatal (file-based storage is primary)

## Related Files

- AI Detector reference: `/api/ai-detect` endpoint (similar pattern)
- Background task example: `_finalize_ai_detection_job()` function
- Polling logic: `src/frontend/app/upload/page.tsx` (`startPolling` function)
