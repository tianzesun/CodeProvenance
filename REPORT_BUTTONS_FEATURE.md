# PDF Download and Print Buttons Feature

## Overview
Added PDF download and print functionality to the IntegrityDesk Originality Report (committee report).

## Changes Made

### File Modified
- `src/backend/infrastructure/professional_report_generator.py`

### Features Added

1. **Download PDF Button**
   - Links to `/report/{job_id}/download-pdf` endpoint
   - Uses existing weasyprint PDF generation backend
   - Styled with primary button design (white background, blue text)
   - Includes download icon (SVG)

2. **Print Report Button**
   - Triggers browser's native print dialog via `window.print()`
   - Styled with secondary button design (semi-transparent white)
   - Includes printer icon (SVG)

3. **Print-Friendly Styling**
   - Buttons hidden when printing (`.no-print` class)
   - Print media query ensures clean output
   - Maintains existing print styles for report content

### CSS Classes Added
```css
.action-buttons { display: flex; gap: 10px; margin-top: 8px; }
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 700; text-decoration: none; cursor: pointer; border: none; transition: all 0.2s; }
.btn-primary { background: rgba(255,255,255,.95); color: #1a73e8; }
.btn-primary:hover { background: #fff; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.btn-secondary { background: rgba(255,255,255,.15); color: #fff; border: 1px solid rgba(255,255,255,.3); }
.btn-secondary:hover { background: rgba(255,255,255,.25); }
.no-print { display: block; }
.icon { width: 16px; height: 16px; }
```

### Print Media Query Updated
```css
@media print {
    body { background: #fff; }
    .shell { box-shadow: none; }
    summary:after { display: none; }
    .no-print { display: none !important; }
    .action-buttons { display: none !important; }
}
```

## User Experience

### Before
- Users had to manually use browser's print function (Ctrl+P / Cmd+P)
- No obvious way to download as PDF
- Had to know the PDF endpoint URL manually

### After
- Clear "Download PDF" button in report header
- Clear "Print Report" button in report header
- Buttons are visually prominent but don't interfere with report content
- Buttons automatically hidden when printing
- Professional appearance with hover effects

## Technical Details

### Button Placement
- Located in the report header, below the title
- Part of the `.report-head-left` section
- Wrapped in `.action-buttons.no-print` container

### PDF Download Flow
1. User clicks "Download PDF" button
2. Browser navigates to `/report/{job_id}/download-pdf`
3. Backend generates PDF using weasyprint
4. Browser downloads the PDF file

### Print Flow
1. User clicks "Print Report" button
2. JavaScript executes `window.print()`
3. Browser opens native print dialog
4. Buttons are hidden via CSS print media query

## Testing

### Automated Tests
- Verified HTML contains download button with correct href
- Verified HTML contains print button with onclick handler
- Verified SVG icons are present
- Verified print media query hides buttons
- All checks passed ✓

### Manual Testing Recommended
1. Navigate to any committee report: `http://localhost:3000/report/{job_id}/committee`
2. Verify buttons appear in header
3. Click "Download PDF" - should download PDF file
4. Click "Print Report" - should open print dialog
5. In print preview, verify buttons are hidden

## Backend Endpoint
The PDF download endpoint already exists at:
- **Route**: `/report/{job_id}/download-pdf`
- **Method**: GET
- **Authentication**: Not required (unauthenticated access allowed)
- **Implementation**: Uses weasyprint library to convert HTML to PDF
- **Fallback**: Returns styled HTML if weasyprint unavailable

## Commit
- **Branch**: cms
- **Commit**: d79809bd
- **Message**: feat: add PDF download and print buttons to committee report
- **Status**: Pushed to GitHub ✓

## Future Enhancements
- Add loading spinner while PDF is generating
- Add success/error toast notifications
- Add option to email report
- Add option to share report link
- Add custom PDF filename option
