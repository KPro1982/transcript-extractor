# Highlighting Misalignment Issue - Context Summary

## Problem Statement
PDF highlighting is misaligned with actual line numbers on the page. The highlight overlay does not match where the line numbers appear in the rendered PDF image.

## Current Architecture

### Backend (Line Number Extraction)
- **File**: `backend/services/pdf_service.py`
- **Function**: `_extract_line_numbers()` (lines 674-694)
- **Process**:
  1. Extracts line numbers from left margin (x < 15% of page width)
  2. Matches numbers 1-25 (legal transcript standard)
  3. Stores: `{number, x, y, height}` for each line number
  4. Sorts by Y position (top to bottom)

- **Function**: `_find_closest_line_number()` (lines 1101-1107)
- **Process**:
  - Takes a Y position (in PDF points) and finds closest line number
  - Returns the line number (1-25) for that Y position
  - Used to assign line numbers to Q&A pairs based on question Y position

### Frontend (Highlight Rendering)
- **File**: `frontend/components/PDFViewer.tsx`
- **Constant**: `LINES_PER_PAGE = 25` (line 18)
- **Function**: `calculateHighlightStyle()` (lines 107-140)
- **Current Calculation**:
  ```typescript
  const topMarginPercent = 0.12  // 12% top margin
  const bottomMarginPercent = 0.08  // 8% bottom margin
  const contentHeight = displayDimensions.height * (1 - topMarginPercent - bottomMarginPercent)
  const lineHeight = contentHeight / LINES_PER_PAGE
  const topMargin = displayDimensions.height * topMarginPercent
  
  // Start position: between line numbers (offset by -1.5 lines)
  const startY = topMargin + (highlightStartLine - 1.5) * lineHeight
  
  // End position: between line numbers (offset by -0.5 lines)
  const endY = topMargin + (endLine - 0.5) * lineHeight
  ```

## What Was Attempted

### Previous Fix Attempt (Commit f1e6dfb)
- Changed margins from 12%/8% to 10%/7%
- Changed positioning from "between lines" to "start of lines"
- Updated calculation to: `(line - 1) * lineHeight - 0.1 * lineHeight`
- **Result**: Still misaligned

### Current State
- **On `dev` branch**: Code still shows OLD calculation (0.12/0.08 margins, -1.5/-0.5 offsets)
- **On `master` branch**: Fix exists (commit f1e6dfb) with updated margins (0.10/0.07) and positioning
- **Issue**: Fix was committed to `master` but NOT merged to `dev` branch
- **Result**: `dev` branch (which Railway monitors) still has the old misaligned code
- **Additional Issue**: Even with the fix, highlighting is still reported as misaligned, suggesting the fix didn't fully solve the problem

## Root Cause Analysis Needed

### Key Questions to Investigate:

1. **Coordinate System Mismatch?**
   - Backend extracts line numbers using PDF coordinates (points)
   - Frontend renders PDF as image (pixels)
   - Are the Y positions being correctly converted from PDF points to display pixels?

2. **Margin Assumptions Wrong?**
   - Frontend assumes fixed margins (12% top, 8% bottom)
   - Actual PDFs may have different margins
   - Line numbers might not start exactly at the assumed top margin

3. **Line Number Positioning?**
   - Backend finds line numbers at specific Y positions in PDF
   - Frontend calculates positions assuming uniform spacing
   - Are line numbers evenly spaced, or do they vary?

4. **Image Scaling?**
   - PDF is rendered as image at 2.0x scale (see `render_page_as_image()`)
   - Display dimensions might not match actual PDF dimensions
   - Is the scaling factor being accounted for?

5. **Line Number Extraction Accuracy?**
   - Backend extracts line numbers from left margin
   - Uses `_find_closest_line_number()` to map Q&A Y positions to line numbers
   - Is this mapping accurate?

## Data Flow

1. **PDF Extraction**:
   - Backend extracts text items with (x, y) positions in PDF points
   - Extracts line numbers from left margin (x < 15% width)
   - Finds closest line number for each Q&A pair's Y position

2. **Database Storage**:
   - Q&A pairs stored with `line_number` (1-25) and `page_number`
   - Also stores `pdf_page_index` (1-based PDF file index)

3. **Frontend Display**:
   - Receives Q&A items with `line_number` and `page_number`
   - Renders PDF page as image (scaled)
   - Calculates highlight position based on `line_number` and assumed layout

## Potential Solutions to Investigate

### Option 1: Pass Actual Line Number Positions from Backend
- Backend already extracts line numbers with Y positions
- Could pass these Y positions to frontend
- Frontend could map highlights directly to actual positions
- **Pros**: Most accurate
- **Cons**: Requires API changes, more data transfer

### Option 2: Use Actual PDF Dimensions
- Get actual PDF page dimensions (width, height in points)
- Get actual image render dimensions (width, height in pixels)
- Calculate scale factor: `scale = imageHeight / pdfHeight`
- Map PDF Y positions to image Y positions using scale
- **Pros**: Uses actual coordinates
- **Cons**: Need to pass PDF dimensions to frontend

### Option 3: Adjust Margin/Offset Calculations
- Test with actual PDF to measure real margins
- Adjust `topMarginPercent` and `bottomMarginPercent` based on measurements
- Fine-tune offset calculations
- **Pros**: Simple fix
- **Cons**: May not work for all PDF formats

### Option 4: Use CSS Transform Based on Actual Positions
- If backend passes line number Y positions
- Convert PDF Y to display Y using scale factor
- Position highlights using actual coordinates
- **Pros**: Most accurate
- **Cons**: Requires backend changes

## Files to Check

1. **Backend**:
   - `backend/services/pdf_service.py` - Line number extraction
   - `backend/api/documents.py` - Q&A items API (what data is sent to frontend)

2. **Frontend**:
   - `frontend/components/PDFViewer.tsx` - Highlight calculation
   - `frontend/app/results/[jobId]/page.tsx` - How Q&A items are passed to PDFViewer

3. **API Response**:
   - Check what data structure is returned from `/api/documents/{id}/qa-items`
   - Verify line numbers and page numbers are correct

## Testing Approach

1. **Inspect Actual PDF**:
   - Open a test PDF
   - Measure actual margins (top, bottom)
   - Count actual lines per page
   - Measure line number positions

2. **Compare Backend vs Frontend**:
   - Log backend-extracted line number Y positions
   - Log frontend-calculated highlight Y positions
   - Compare to see the offset

3. **Test with Known Values**:
   - Use a Q&A pair at line 1, 10, 25
   - Check if highlights align correctly
   - Measure actual offset

## Next Steps

1. Verify current code state (check if previous fix was applied)
2. Inspect actual PDF layout (margins, line spacing)
3. Compare backend Y positions vs frontend calculations
4. Consider passing actual line number positions from backend
5. Test with real document to measure alignment accuracy

## Related Commits

- `f1e6dfb` - "Fix highlighting misalignment with page line numbers" (on `master` branch, NOT on `dev`)
- `e92e95c` - "Fix intermittent summary failures when OpenAI returns fewer results than expected" (on both branches)
- `c36a1b6` - "Add editable summaries with date tracking and fix highlighting offset" (previous attempt)

## Current Branch Status

- **Current branch**: `dev`
- **Railway monitors**: `dev` branch for auto-deployment
- **Problem**: The fix (f1e6dfb) exists on `master` but NOT on `dev`
- **Action needed**: 
  1. Either merge `master` → `dev` to get the fix
  2. Or create a new fix directly on `dev` branch
  3. The fix may need further refinement since highlighting is still reported as misaligned

## Important Note

The previous fix attempt (f1e6dfb) changed:
- Margins: 12%/8% → 10%/7%
- Positioning: `(line - 1.5)` → `(line - 1) - 0.1 * lineHeight`

But highlighting is STILL misaligned, suggesting:
- The margin assumptions may still be wrong
- The coordinate system conversion may be incorrect
- Need to investigate actual PDF layout vs assumptions

