# Code Reverted to Original Working State

## What Happened

I attempted to implement background task processing to fix the timeout issue, but this caused problems. I've now **reverted all backend changes** to restore the original working code.

## Current State

✅ **Backend code**: Restored to original (working) state  
✅ **Frontend timeout**: Increased from 30s to 120s (2 minutes) - this remains  
✅ **Code compiles**: No syntax errors  

## The Only Change That Remains

**File**: `src/frontend/lib/apiClient.ts`  
**Change**: Timeout increased from 30000ms to 120000ms

```typescript
export const apiClient: AxiosInstance = axios.create({
  baseURL: '',
  withCredentials: true,
  timeout: 120000, // 2 minutes (was 30 seconds)
});
```

This gives the backend 2 minutes to complete the analysis instead of 30 seconds.

## Next Steps

### 1. Restart Backend Server

The server needs to be restarted to load the restored code:

```bash
# Stop the server (Ctrl+C in the terminal where it's running)
# Then restart:
cd /home/tsun/Documents/CodeProvenance
source venv/bin/activate
uvicorn src.backend.api.server:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Test the Upload

1. Go to http://localhost:3000/upload
2. Upload 2 small Python files
3. Click "Analyze"
4. **Expected**: Should complete within 2 minutes

### 3. If Still Stuck at 92%

The 92% is just a frontend progress animation while waiting for the backend. If it's stuck:

**Check backend logs** for errors in the terminal where uvicorn is running.

**Check if analysis is actually running**:
```bash
# Watch for new job directories
watch -n 1 'ls -lt /home/tsun/Documents/CodeProvenance/uploads/ | head -5'

# Check most recent job
ls -lt /home/tsun/Documents/CodeProvenance/uploads/ | head -3
LATEST_JOB=$(ls -t /home/tsun/Documents/CodeProvenance/uploads/ | head -1)
cat /home/tsun/Documents/CodeProvenance/reports/$LATEST_JOB/job.json | jq .status
```

**Possible statuses**:
- `"processing"` - Still running (wait)
- `"analyzing"` - Running engines (wait)
- `"completed"` - Done! (frontend should redirect)
- `"failed"` - Error occurred (check `.error` field)

## Why 92%?

The frontend progress code intentionally caps at 92% while waiting:

```typescript
setProgress((current) => Math.min(0.92, current + 0.035));
```

This is normal! It animates to 92%, then waits for the backend to return "completed".

## Troubleshooting

### Backend returns immediately with "completed"?

If the backend completes very quickly (< 5 seconds), you should see results. If it's stuck at 92% for more than 30 seconds:

1. **Check Network tab** (F12 → Network):
   - Look for POST `/api/upload` - should show response status
   - If 500 error: backend error, check logs
   - If timeout: backend is taking too long

2. **Check Backend Terminal**:
   - Look for Python errors/exceptions
   - Look for "Analysis failed" messages

3. **Increase timeout further** (if needed):
   - Edit `src/frontend/lib/apiClient.ts`
   - Change `timeout: 120000` to `timeout: 300000` (5 minutes)
   - Restart frontend: `npm run dev`

### Files are too large?

If you're testing with very large files:
- Try with smaller test files first (< 100 lines each)
- Large files will take longer to analyze

### Multiple engines selected?

- If "IntegrityDesk" tool is selected, it runs 5 engines (Token, AST, Winnowing, GST, Semantic)
- This takes longer than selecting a single tool
- Try with just one engine first for testing

## What I Learned

- The original code was working, just needed more timeout
- Background tasks would be better for production, but require more careful implementation
- The 2-minute timeout should be sufficient for most cases
- If 2 minutes isn't enough, can be increased further

## Summary

- **All backend changes reverted** ✅
- **Frontend timeout increased to 2 minutes** ✅  
- **Server restart required** ⚠️
- **Should work after restart** 🤞

Just restart the backend server and try again!
