const Tesseract = require('tesseract.js');

async function debugPage3() {
    const worker = await Tesseract.createWorker('eng');
    const result = await worker.recognize('test-manual-page3.png');
    
    console.log('=== RAW TEXT OUTPUT ===');
    console.log(result.data.text);
    console.log('\n=== LINE BY LINE ANALYSIS ===');
    
    const lines = result.data.text.split('\n');
    const lineNumberPattern = /^([1-9]\d?)(\s|$)/;
    
    for (let i = 0; i < lines.length && i < 30; i++) {
        const line = lines[i];
        const trimmed = line.trim();
        if (!trimmed) continue;
        
        const match = trimmed.match(lineNumberPattern);
        if (match) {
            console.log(`Line ${i}: [LINE NUMBER FOUND: ${match[1]}] "${trimmed.substring(0, 60)}"`);
        } else {
            console.log(`Line ${i}: [NO LINE NUM] "${trimmed.substring(0, 60)}"`);
        }
    }
    
    await worker.terminate();
}

debugPage3().catch(console.error);





