const Tesseract = require('tesseract.js');

async function testDetailed() {
    console.log('Testing Tesseract detailed output...\n');
    
    const worker = await Tesseract.createWorker('eng');
    
    console.log('Processing test-manual-page3.png...');
    const result = await worker.recognize('test-manual-page3.png');
    
    console.log(`\nData structure:`,  Object.keys(result.data));
    console.log(`\nHas words array:`, !!result.data.words);
    console.log(`Words length:`, result.data.words ? result.data.words.length : 0);
    console.log(`\nHas lines array:`, !!result.data.lines);
    console.log(`Lines length:`, result.data.lines ? result.data.lines.length : 0);
    console.log(`\nHas paragraphs array:`, !!result.data.paragraphs);
    console.log(`Paragraphs length:`, result.data.paragraphs ? result.data.paragraphs.length : 0);
    
    if (result.data.lines && result.data.lines.length > 0) {
        console.log(`\nFirst 5 lines with bounding boxes:`);
        for (let i = 0; i < Math.min(5, result.data.lines.length); i++) {
            const line = result.data.lines[i];
            console.log(`Line ${i}: "${line.text.substring(0, 50)}"`);
            console.log(`  bbox: x0=${line.bbox.x0}, y0=${line.bbox.y0}, x1=${line.bbox.x1}, y1=${line.bbox.y1}`);
            console.log(`  words: ${line.words.length}`);
            if (line.words.length > 0) {
                console.log(`    First word: "${line.words[0].text}" at x=${line.words[0].bbox.x0}`);
            }
        }
    }
    
    await worker.terminate();
}

testDetailed().catch(console.error);



