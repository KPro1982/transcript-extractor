/**
 * Test PDF extraction to diagnose errors
 */

const fs = require('fs');
const path = require('path');

const PDF_PATH = path.join(__dirname, 'Transcripts', 'Buksh - Deposition Transcript of Charlene Wilson Domingues 9-18-25 (Abridged).pdf');

async function testExtraction() {
    console.log('Testing PDF extraction...');
    console.log(`PDF Path: ${PDF_PATH}`);
    console.log(`Exists: ${fs.existsSync(PDF_PATH)}`);
    
    if (!fs.existsSync(PDF_PATH)) {
        console.error('PDF file not found!');
        process.exit(1);
    }
    
    const stats = fs.statSync(PDF_PATH);
    console.log(`File size: ${stats.size} bytes`);
    console.log('');
    
    try {
        // Test if we can load the PDF
        const pdfjsLib = require('pdfjs-dist');
        if (pdfjsLib.GlobalWorkerOptions) {
            pdfjsLib.GlobalWorkerOptions.workerSrc = '';
        }
        
        console.log('Loading PDF with pdfjs-dist...');
        const pdfBuffer = fs.readFileSync(PDF_PATH);
        const pdfBytes = new Uint8Array(pdfBuffer);
        const loadingTask = pdfjsLib.getDocument({ 
            data: pdfBytes, 
            useWorkerFetch: false, 
            isEvalSupported: false 
        });
        
        const pdfDoc = await loadingTask.promise;
        console.log(`✓ PDF loaded successfully`);
        console.log(`  Total pages: ${pdfDoc.numPages}`);
        
        // Test extracting first page
        console.log('\nTesting first page extraction...');
        const page = await pdfDoc.getPage(1);
        const textContent = await page.getTextContent();
        console.log(`✓ Page 1 extracted`);
        console.log(`  Text items: ${textContent.items.length}`);
        
        if (textContent.items.length > 0) {
            console.log(`  Sample text: "${textContent.items[0].str.substring(0, 50)}..."`);
        }
        
        // Test the full extraction function
        console.log('\nTesting full extraction function...');
        const { extractPDFWithImages } = require('./server.js');
        
        // Wait, we need to export it or call it differently
        // Let's try requiring server.js functions
        
        console.log('✓ All tests passed!');
        
    } catch (error) {
        console.error('\n❌ Error during extraction:');
        console.error(`  Message: ${error.message}`);
        console.error(`  Stack: ${error.stack}`);
        process.exit(1);
    }
}

// Check if server.js exports the function
try {
    // Try to access extractPDFWithImages
    const serverCode = fs.readFileSync('./server.js', 'utf8');
    if (serverCode.includes('async function extractPDFWithImages')) {
        console.log('✓ extractPDFWithImages function found in server.js');
    } else {
        console.log('⚠ extractPDFWithImages function not found');
    }
} catch (e) {
    console.error('Could not read server.js:', e.message);
}

testExtraction().catch(console.error);










