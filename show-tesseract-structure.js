const Tesseract = require('tesseract.js');
const util = require('util');

async function showStructure() {
    const worker = await Tesseract.createWorker('eng');
    const result = await worker.recognize('test-manual-page3.png');
    
    console.log('Full data structure:');
    console.log(util.inspect(result.data, { depth: 3, colors: true, maxArrayLength: 2 }));
    
    await worker.terminate();
}

showStructure().catch(console.error);

