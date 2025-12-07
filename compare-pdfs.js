/**
 * Deep diagnostic script to compare text extraction from two PDFs
 * and identify encoding differences that cause Q/A parsing to fail
 */

const fs = require('fs');
const path = require('path');
const pdfjsLib = require('pdfjs-dist');

// Disable worker
pdfjsLib.GlobalWorkerOptions.workerSrc = '';

async function dumpRawText(pdfPath, label, outputFile) {
    console.log(`\nDumping raw text from ${label}...`);

    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false, disableFontFace: true });
    const pdfDoc = await loadingTask.promise;

    let output = `=== RAW TEXT DUMP: ${label} ===\n\n`;
    
    const pagesToCheck = Math.min(8, pdfDoc.numPages);
    
    for (let pageNum = 1; pageNum <= pagesToCheck; pageNum++) {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        const items = textContent.items || [];
        
        output += `\n${'='.repeat(60)}\n`;
        output += `PAGE ${pageNum} (${items.length} items, ${viewport.width.toFixed(0)}x${viewport.height.toFixed(0)})\n`;
        output += `${'='.repeat(60)}\n\n`;
        
        // Sort items by position (top to bottom, left to right)
        const sortedItems = items.filter(i => i.str && i.str.trim()).sort((a, b) => {
            const yDiff = (b.transform?.[5] || 0) - (a.transform?.[5] || 0);
            if (Math.abs(yDiff) > 5) return yDiff;
            return (a.transform?.[4] || 0) - (b.transform?.[4] || 0);
        });
        
        for (const item of sortedItems) {
            const x = item.transform ? item.transform[4].toFixed(1) : '?';
            const y = item.transform ? item.transform[5].toFixed(1) : '?';
            const charCodes = [...item.str].slice(0, 30).map(c => c.charCodeAt(0)).join(',');
            
            output += `[${x.padStart(6)}, ${y.padStart(6)}] "${item.str}" | Codes:[${charCodes}]\n`;
        }
    }
    
    fs.writeFileSync(outputFile, output, 'utf-8');
    console.log(`  Written to ${outputFile}`);
    return output;
}

async function analyzeQAPatterns(pdfPath, label) {
    console.log(`\n${'#'.repeat(80)}`);
    console.log(`Analyzing Q/A patterns in: ${label}`);
    console.log(`${'#'.repeat(80)}\n`);

    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false, disableFontFace: true });
    const pdfDoc = await loadingTask.promise;

    // Collect ALL text items from first 8 pages
    const allItems = [];
    const pagesToCheck = Math.min(8, pdfDoc.numPages);
    
    for (let pageNum = 1; pageNum <= pagesToCheck; pageNum++) {
        const page = await pdfDoc.getPage(pageNum);
        const textContent = await page.getTextContent();
        const items = textContent.items || [];
        
        for (const item of items) {
            if (item.str && item.str.trim()) {
                allItems.push({
                    page: pageNum,
                    str: item.str,
                    trimmed: item.str.trim(),
                    x: item.transform ? item.transform[4] : 0,
                    y: item.transform ? item.transform[5] : 0
                });
            }
        }
    }
    
    console.log(`Total text items from ${pagesToCheck} pages: ${allItems.length}`);
    
    // Search for standard Q. and A. patterns
    const standardQ = allItems.filter(item => /^Q\.\s*/i.test(item.trimmed) || item.trimmed === 'Q.' || item.trimmed === 'Q');
    const standardA = allItems.filter(item => /^A\.\s*/i.test(item.trimmed) || item.trimmed === 'A.' || item.trimmed === 'A');
    
    console.log(`\nStandard Q patterns (Q. or Q): ${standardQ.length}`);
    standardQ.slice(0, 5).forEach(item => {
        const codes = [...item.str].slice(0, 10).map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str.substring(0, 50)}" | Codes: [${codes.join(',')}]`);
    });
    
    console.log(`\nStandard A patterns (A. or A): ${standardA.length}`);
    standardA.slice(0, 5).forEach(item => {
        const codes = [...item.str].slice(0, 10).map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str.substring(0, 50)}" | Codes: [${codes.join(',')}]`);
    });
    
    // Search for text CONTAINING Q or A followed by period
    const containsQDot = allItems.filter(item => item.str.includes('Q.'));
    const containsADot = allItems.filter(item => item.str.includes('A.'));
    
    console.log(`\nItems containing 'Q.': ${containsQDot.length}`);
    containsQDot.slice(0, 5).forEach(item => {
        const codes = [...item.str].slice(0, 15).map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str.substring(0, 60)}" | Codes: [${codes.join(',')}]`);
    });
    
    console.log(`\nItems containing 'A.': ${containsADot.length}`);
    containsADot.slice(0, 5).forEach(item => {
        const codes = [...item.str].slice(0, 15).map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str.substring(0, 60)}" | Codes: [${codes.join(',')}]`);
    });
    
    // Look for single character items that could be Q or A markers
    const singleChar = allItems.filter(item => item.trimmed.length === 1 || item.trimmed.length === 2);
    console.log(`\nSingle/double character items: ${singleChar.length}`);
    const uniqueChars = [...new Set(singleChar.map(i => i.trimmed))];
    console.log(`Unique values: ${uniqueChars.slice(0, 30).join(', ')}`);
    
    // Show items that look like they could be Q or A but aren't being detected
    const potentialQA = allItems.filter(item => {
        const t = item.trimmed;
        const firstCode = t.charCodeAt(0);
        // Q=81, A=65 - look for anything that starts with these or similar chars
        return (firstCode === 81 || firstCode === 65) && (t.length <= 3 || t.charAt(1) === '.' || t.charAt(1) === ' ');
    });
    
    console.log(`\nPotential Q/A markers (char code 81 or 65): ${potentialQA.length}`);
    potentialQA.slice(0, 10).forEach(item => {
        const codes = [...item.str].map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str}" | Codes: [${codes.join(',')}] | x:${item.x.toFixed(0)}`);
    });
    
    // Look for ANY pattern that could be Q/A with non-standard encoding
    // Check for letters in similar position (left side of page, around x < 150)
    const leftMarginItems = allItems.filter(item => item.x < 120 && item.x > 30);
    console.log(`\nLeft margin items (x: 30-120): ${leftMarginItems.length}`);
    const leftMarginSample = leftMarginItems.slice(0, 20);
    leftMarginSample.forEach(item => {
        const codes = [...item.str].slice(0, 10).map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page} x:${item.x.toFixed(0)}: "${item.str.substring(0, 30)}" | Codes: [${codes.join(',')}]`);
    });
    
    return {
        standardQ: standardQ.length,
        standardA: standardA.length,
        containsQDot: containsQDot.length,
        containsADot: containsADot.length,
        potentialQA: potentialQA.length,
        totalItems: allItems.length,
        allItems
    };
}

async function findEncodingDifferences(workingItems, brokenItems) {
    console.log(`\n${'='.repeat(80)}`);
    console.log('ENCODING ANALYSIS');
    console.log(`${'='.repeat(80)}\n`);
    
    // Get unique character codes from both PDFs
    const workingCodes = new Set();
    const brokenCodes = new Set();
    
    workingItems.forEach(item => {
        [...item.str].forEach(c => workingCodes.add(c.charCodeAt(0)));
    });
    
    brokenItems.forEach(item => {
        [...item.str].forEach(c => brokenCodes.add(c.charCodeAt(0)));
    });
    
    // Find codes unique to broken PDF
    const uniqueToBroken = [...brokenCodes].filter(c => !workingCodes.has(c)).sort((a, b) => a - b);
    console.log(`Character codes unique to Broken PDF: ${uniqueToBroken.length}`);
    console.log(`Codes: ${uniqueToBroken.slice(0, 50).join(', ')}`);
    
    // Show what characters these codes represent
    console.log('\nUnique broken characters:');
    uniqueToBroken.slice(0, 30).forEach(code => {
        console.log(`  Code ${code}: '${String.fromCharCode(code)}' (U+${code.toString(16).toUpperCase().padStart(4, '0')})`);
    });
    
    // Look for items in broken PDF that contain these unique codes
    console.log('\nBroken PDF items containing unique characters:');
    const itemsWithUnique = brokenItems.filter(item => {
        return [...item.str].some(c => uniqueToBroken.includes(c.charCodeAt(0)));
    });
    itemsWithUnique.slice(0, 20).forEach(item => {
        const codes = [...item.str].map(c => c.charCodeAt(0));
        console.log(`  Page ${item.page}: "${item.str.substring(0, 40)}" | Codes: [${codes.join(',')}]`);
    });
}

async function main() {
    const workingPdf = path.join(__dirname, 'Transcripts', 'Working transcript.pdf');
    const brokenPdf = path.join(__dirname, 'Transcripts', 'Broken Transcript.pdf');
    
    // Ensure output directory exists
    const outputDir = path.join(__dirname, 'output');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    
    // Check files exist
    if (!fs.existsSync(workingPdf)) {
        console.error('Working transcript not found:', workingPdf);
        return;
    }
    if (!fs.existsSync(brokenPdf)) {
        console.error('Broken transcript not found:', brokenPdf);
        return;
    }
    
    console.log('Starting PDF comparison analysis...\n');
    
    // Dump raw text
    await dumpRawText(workingPdf, 'Working Transcript', path.join(outputDir, 'working-raw.txt'));
    await dumpRawText(brokenPdf, 'Broken Transcript', path.join(outputDir, 'broken-raw.txt'));
    
    // Analyze Q/A patterns
    const workingResults = await analyzeQAPatterns(workingPdf, 'Working Transcript');
    const brokenResults = await analyzeQAPatterns(brokenPdf, 'Broken Transcript');
    
    // Find encoding differences
    await findEncodingDifferences(workingResults.allItems, brokenResults.allItems);
    
    // Summary
    console.log(`\n${'='.repeat(80)}`);
    console.log('SUMMARY');
    console.log(`${'='.repeat(80)}`);
    
    console.log(`\nWorking Transcript:`);
    console.log(`  - Standard Q markers: ${workingResults.standardQ}`);
    console.log(`  - Standard A markers: ${workingResults.standardA}`);
    console.log(`  - Contains Q.: ${workingResults.containsQDot}`);
    console.log(`  - Contains A.: ${workingResults.containsADot}`);
    
    console.log(`\nBroken Transcript:`);
    console.log(`  - Standard Q markers: ${brokenResults.standardQ}`);
    console.log(`  - Standard A markers: ${brokenResults.standardA}`);
    console.log(`  - Contains Q.: ${brokenResults.containsQDot}`);
    console.log(`  - Contains A.: ${brokenResults.containsADot}`);
    
    if (brokenResults.standardQ === 0 && brokenResults.containsQDot === 0) {
        console.log('\n*** The Broken PDF has NO detectable Q. patterns! ***');
        console.log('This indicates the Q and A characters may be encoded differently.');
    }
    
    console.log('\n\nCheck output/working-raw.txt and output/broken-raw.txt for detailed comparison.');
}

main().catch(console.error);
