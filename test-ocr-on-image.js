const Tesseract = require('tesseract.js');

async function testOCR() {
    console.log('Testing OCR on manually generated Ghostscript image...\n');
    
    const worker = await Tesseract.createWorker('eng');
    
    console.log('Processing test-manual-page3.png...');
    const { data } = await worker.recognize('test-manual-page3.png');
    
    console.log(`Confidence: ${data.confidence.toFixed(1)}%`);
    console.log(`Text length: ${data.text.length} characters`);
    console.log(`Words found: ${data.words ? data.words.length : 0}`);
    console.log(`Lines found: ${data.lines ? data.lines.length : 0}\n`);
    
    if (data.text.length > 0) {
        console.log('First 500 characters of extracted text:');
        console.log('---');
        console.log(data.text.substring(0, 500));
        console.log('---\n');
    }
    
    // Check for line numbers specifically
    const lineNumbers = [];
    if (data.words) {
        for (const word of data.words) {
            const text = word.text.trim();
            const x = word.bbox.x0;
            
            // Check if it's a number in the left margin (X < 200)
            if (x < 200 && /^\d+$/.test(text)) {
                lineNumbers.push({ text, x: x.toFixed(0), y: word.bbox.y0.toFixed(0) });
            }
        }
    }
    
    console.log(`Line numbers found: ${lineNumbers.length}`);
    if (lineNumbers.length > 0) {
        console.log('Line numbers detected:');
        lineNumbers.forEach(ln => {
            console.log(`  [${ln.x}, ${ln.y}] ${ln.text}`);
        });
    }
    
    await worker.terminate();
}

testOCR().catch(console.error);

