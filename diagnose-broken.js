/**
 * Comprehensive diagnostic to test Q/A detection - handles both formats
 */

const fs = require('fs');
const path = require('path');
const pdfjsLib = require('pdfjs-dist');

pdfjsLib.GlobalWorkerOptions.workerSrc = '';

async function testQAExtraction(pdfPath, label, pages) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`TESTING Q/A EXTRACTION: ${label}`);
    console.log(`${'='.repeat(80)}\n`);

    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false });
    const pdfDoc = await loadingTask.promise;

    console.log(`Total pages: ${pdfDoc.numPages}`);
    
    for (const pageNum of pages) {
        if (pageNum > pdfDoc.numPages) continue;
        
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        const { width, height } = viewport;
        
        console.log(`\n--- PAGE ${pageNum} (${width.toFixed(0)}x${height.toFixed(0)}) ---`);
        
        // Extract text items
        const textItems = [];
        for (const item of (textContent.items || [])) {
            const str = item.str || '';
            if (!str.trim()) continue;
            const transform = item.transform || [];
            textItems.push({
                text: str,
                x: transform[4] || 0,
                y: height - (transform[5] || 0),
                width: item.width || 0,
                height: item.height || 12,
            });
        }
        
        console.log(`Total text items: ${textItems.length}`);
        
        // Find line numbers
        const leftMarginThreshold = width * 0.15;
        const actualLineNumbers = [];
        
        for (const item of textItems) {
            const text = item.text.trim();
            if (item.x < leftMarginThreshold && /^[1-9]$|^1[0-9]$|^2[0-5]$/.test(text)) {
                actualLineNumbers.push({
                    number: parseInt(text),
                    text: text,
                    x: item.x,
                    y: item.y,
                    height: item.height || 12
                });
            }
        }
        
        actualLineNumbers.sort((a, b) => a.y - b.y);
        console.log(`Line numbers found: ${actualLineNumbers.length}`);
        
        let lineHeight = 25;
        if (actualLineNumbers.length >= 2) {
            const yDiffs = [];
            for (let i = 1; i < Math.min(actualLineNumbers.length, 10); i++) {
                yDiffs.push(Math.abs(actualLineNumbers[i].y - actualLineNumbers[i-1].y));
            }
            lineHeight = yDiffs.reduce((a, b) => a + b, 0) / yDiffs.length;
        }
        
        // Build content with Y-grouping fix
        const digitalLeftMargin = width * 0.18;
        const lineNumberItems = new Set(actualLineNumbers.map(ln => `${ln.x.toFixed(1)}_${ln.y.toFixed(1)}`));
        
        // Find content Y bounds
        let minY, maxY;
        if (actualLineNumbers.length >= 2) {
            minY = Math.min(...actualLineNumbers.map(ln => ln.y));
            maxY = Math.max(...actualLineNumbers.map(ln => ln.y));
        } else {
            const contentItems = textItems.filter(item => item.x > digitalLeftMargin);
            if (contentItems.length > 0) {
                const contentYs = contentItems.map(i => i.y);
                minY = Math.min(...contentYs);
                maxY = Math.max(...contentYs);
            } else {
                minY = height * 0.10;
                maxY = height * 0.90;
            }
        }
        
        if (!isFinite(minY) || !isFinite(maxY)) {
            minY = height * 0.10;
            maxY = height * 0.90;
        }
        
        const headerBound = minY - lineHeight;
        const footerBound = maxY + lineHeight;
        
        // Collect raw content
        const rawContent = [];
        for (const item of textItems) {
            const centerY = item.y + (item.height || 0) / 2;
            const centerX = item.x + (item.width || 0) / 2;
            const itemKey = `${item.x.toFixed(1)}_${item.y.toFixed(1)}`;
            
            const isInLeftMargin = centerX < digitalLeftMargin;
            const isLineNumber = lineNumberItems.has(itemKey) || 
                                 (item.x < leftMarginThreshold && /^[1-9]$|^1[0-9]$|^2[0-5]$/.test(item.text.trim()));
            
            if (centerY >= headerBound && centerY <= footerBound && !isInLeftMargin && !isLineNumber) {
                rawContent.push({
                    text: item.text,
                    position: { x: item.x, y: item.y, width: item.width, height: item.height },
                });
            }
        }
        
        console.log(`Raw content items: ${rawContent.length}`);
        
        // Group by Y position
        const yTolerance = lineHeight * 0.4;
        const groupedByLine = new Map();
        
        for (const item of rawContent) {
            const itemY = item.position.y;
            let foundGroup = false;
            
            for (const [groupY, items] of groupedByLine) {
                if (Math.abs(itemY - groupY) < yTolerance) {
                    items.push(item);
                    foundGroup = true;
                    break;
                }
            }
            
            if (!foundGroup) {
                groupedByLine.set(itemY, [item]);
            }
        }
        
        // Join text items per line
        const mainContent = [];
        for (const [groupY, items] of groupedByLine) {
            items.sort((a, b) => a.position.x - b.position.x);
            const joinedText = items.map(i => i.text).join(' ');
            mainContent.push({
                text: joinedText,
                y: groupY,
            });
        }
        
        mainContent.sort((a, b) => a.y - b.y);
        console.log(`Grouped lines: ${mainContent.length}`);
        
        // Find Q/A lines - handle both formats:
        // Format 1 (Broken): "Q. question text"
        // Format 2 (Working): "· · ·Q.· question text"
        const qLines = mainContent.filter(m => {
            // Match Q. at start or after middle-dots/spaces
            return /^Q\./i.test(m.text.trim()) || /[·\s]Q\.[·\s]/i.test(m.text);
        });
        const aLines = mainContent.filter(m => {
            // Match A. at start or after middle-dots/spaces
            return /^A\./i.test(m.text.trim()) || /[·\s]A\.[·\s]/i.test(m.text);
        });
        
        console.log(`\nQ. lines: ${qLines.length}`);
        qLines.slice(0, 5).forEach(m => console.log(`  "${m.text.substring(0, 65)}"`));
        
        console.log(`A. lines: ${aLines.length}`);
        aLines.slice(0, 5).forEach(m => console.log(`  "${m.text.substring(0, 65)}"`));
        
        // Show sample content
        console.log(`\nFirst 10 lines:`);
        mainContent.slice(0, 10).forEach((m, i) => {
            console.log(`  ${i}: "${m.text.substring(0, 65)}"`);
        });
    }
}

async function main() {
    const brokenPdf = path.join(__dirname, 'Transcripts', 'Broken Transcript.pdf');
    const workingPdf = path.join(__dirname, 'Transcripts', 'Working transcript.pdf');
    
    // Test Broken Transcript pages 7-9 (where Q/A starts)
    await testQAExtraction(brokenPdf, 'Broken Transcript', [7, 8, 9]);
    
    // Test Working Transcript pages 5-8 (examination should start around page 5-6)
    await testQAExtraction(workingPdf, 'Working Transcript', [5, 6, 7, 8]);
    
    console.log('\n\nDone!');
}

main().catch(console.error);
