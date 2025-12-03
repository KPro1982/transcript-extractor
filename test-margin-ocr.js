/**
 * Simple test to see what Tesseract detects in the margin
 */
const fs = require('fs');
const path = require('path');
const { createWorker, PSM } = require('tesseract.js');

async function test() {
    const marginPath = path.join(__dirname, 'temp', 'debug-output', 'margin-15pct.png');
    
    if (!fs.existsSync(marginPath)) {
        console.log('Margin image not found. Run test-line-numbers.js first.');
        return;
    }
    
    console.log('Testing margin OCR without whitelist...');
    
    const worker = await createWorker('eng');
    
    // Test with different PSM modes
    const modes = [
        { mode: PSM.AUTO, name: 'AUTO' },
        { mode: PSM.SINGLE_COLUMN, name: 'SINGLE_COLUMN' },
        { mode: PSM.SINGLE_BLOCK, name: 'SINGLE_BLOCK' },
        { mode: PSM.SPARSE_TEXT, name: 'SPARSE_TEXT' },
        { mode: PSM.RAW_LINE, name: 'RAW_LINE' },
    ];
    
    for (const { mode, name } of modes) {
        await worker.setParameters({
            tessedit_pageseg_mode: mode,
            // NO whitelist - accept any characters
        });
        
        const { data } = await worker.recognize(marginPath);
        
        console.log(`\n=== PSM.${name} ===`);
        console.log(`Words: ${data.words?.length || 0}`);
        console.log(`Confidence: ${data.confidence}`);
        console.log(`Text: "${data.text?.replace(/\n/g, '\\n').substring(0, 300)}"`);
        
        if (data.words && data.words.length > 0) {
            console.log('First 10 words:');
            data.words.slice(0, 10).forEach(w => {
                console.log(`  "${w.text}" at (${w.bbox.x0}, ${w.bbox.y0}) conf=${w.confidence?.toFixed(1)}`);
            });
        }
    }
    
    await worker.terminate();
    
    // Also check the full page image
    const fullPagePath = path.join(__dirname, 'temp', 'page-5.png');
    if (fs.existsSync(fullPagePath)) {
        console.log('\n\n=== Checking full page for line number positions ===');
        
        const worker2 = await createWorker('eng');
        await worker2.setParameters({
            tessedit_pageseg_mode: PSM.AUTO,
        });
        
        const { data: pageData } = await worker2.recognize(fullPagePath);
        
        // Find any words that look like line numbers (1-25) in the left 15% of the page
        const pageWidth = 3400; // From earlier test
        const leftMargin = pageWidth * 0.15;
        
        console.log(`Looking for numbers in left ${leftMargin.toFixed(0)}px...`);
        
        const marginWords = (pageData.words || []).filter(w => {
            const centerX = (w.bbox.x0 + w.bbox.x1) / 2;
            return centerX < leftMargin && /^\d+$/.test(w.text.trim());
        });
        
        console.log(`Found ${marginWords.length} numeric words in left margin:`);
        marginWords.forEach(w => {
            console.log(`  "${w.text}" at x=${w.bbox.x0} (center=${((w.bbox.x0 + w.bbox.x1) / 2).toFixed(0)})`);
        });
        
        // Find all numeric words
        const allNumbers = (pageData.words || []).filter(w => /^\d+$/.test(w.text.trim()));
        console.log(`\nAll numeric words on page (${allNumbers.length}):`);
        allNumbers.slice(0, 20).forEach(w => {
            console.log(`  "${w.text}" at (${w.bbox.x0}, ${w.bbox.y0})`);
        });
        
        await worker2.terminate();
    }
}

test().catch(console.error);


