const Tesseract = require('tesseract.js');

async function testBlocks() {
    console.log('Testing Tesseract blocks output...\n');
    
    const worker = await Tesseract.createWorker('eng');
    
    console.log('Processing test-manual-page3.png...');
    const result = await worker.recognize('test-manual-page3.png');
    
    console.log(`\nBlocks: ${result.data.blocks.length}`);
    
    if (result.data.blocks.length > 0) {
        console.log(`\nFirst 3 blocks:`);
        for (let i = 0; i < Math.min(3, result.data.blocks.length); i++) {
            const block = result.data.blocks[i];
            console.log(`\nBlock ${i}:`);
            console.log(`  text: "${block.text.substring(0, 80)}"`);
            console.log(`  bbox: x0=${block.bbox.x0}, y0=${block.bbox.y0}, x1=${block.bbox.x1}, y1=${block.bbox.y1}`);
            console.log(`  has lines: ${!!block.lines}`);
            if (block.lines && block.lines.length > 0) {
                console.log(`  lines: ${block.lines.length}`);
                const line = block.lines[0];
                console.log(`    First line: "${line.text.substring(0, 60)}"`);
                console.log(`    bbox: x0=${line.bbox.x0}, y0=${line.bbox.y0}`);
                console.log(`    has words: ${!!line.words}`);
                if (line.words && line.words.length > 0) {
                    console.log(`    words: ${line.words.length}`);
                    const word = line.words[0];
                    console.log(`      First word: "${word.text}" at x=${word.bbox.x0}, y=${word.bbox.y0}`);
                }
            }
        }
    }
    
    await worker.terminate();
}

testBlocks().catch(console.error);

