const fs = require('fs');
const path = require('path');

async function debugPage5() {
    const pdfjsLib = require('pdfjs-dist');
    pdfjsLib.GlobalWorkerOptions.workerSrc = '';
    
    const pdfPath = path.join(__dirname, 'Transcripts', 'Deposition example.pdf');
    const pdfBuffer = fs.readFileSync(pdfPath);
    const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(pdfBuffer) });
    const pdfDoc = await loadingTask.promise;
    
    const page = await pdfDoc.getPage(5);
    const viewport = page.getViewport({ scale: 1.0 });
    const textContent = await page.getTextContent();
    
    console.log('Page 5 dimensions:', viewport.width, 'x', viewport.height);
    console.log('Total text items:', textContent.items.length);
    console.log('\nFirst 30 text items sorted by Y position:\n');
    
    const items = textContent.items
        .filter(item => item.str && item.str.trim())
        .map(item => ({
            text: item.str,
            x: item.transform[4],
            y: viewport.height - item.transform[5],
            height: item.height
        }))
        .sort((a, b) => a.y - b.y);
    
    items.slice(0, 30).forEach((item, i) => {
        console.log(`${i+1}. y=${item.y.toFixed(1)} x=${item.x.toFixed(1)} "${item.text}"`);
    });
}

debugPage5().catch(console.error);


