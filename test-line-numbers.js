/**
 * Test script for debugging line number extraction from legal transcripts
 * Usage: node test-line-numbers.js [pdf-path] [page-number]
 */

const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const { createWorker, PSM, OEM } = require('tesseract.js');

// Add Ghostscript to PATH if installed
const gsPath = 'C:\\Program Files\\gs\\gs10.02.1\\bin';
if (fs.existsSync(gsPath)) {
    process.env.PATH = gsPath + ';' + process.env.PATH;
}

async function testLineNumberExtraction(pdfPath, pageNumber = 1) {
    console.log('\n=== Line Number Extraction Test ===\n');
    
    const { ExternalPDFToImageConverter } = require('./dist/pdf-to-image-external.js');
    
    // Convert PDF to image
    console.log('Converting PDF to image...');
    const imageConverter = new ExternalPDFToImageConverter({ dpi: 400 });
    const images = await imageConverter.convert(pdfPath);
    
    if (pageNumber > images.length) {
        console.error(`Page ${pageNumber} not found. PDF has ${images.length} pages.`);
        return;
    }
    
    const imagePath = images[pageNumber - 1].imagePath;
    console.log(`Using image: ${imagePath}`);
    
    // Get image dimensions
    const metadata = await sharp(imagePath).metadata();
    const width = metadata.width;
    const height = metadata.height;
    console.log(`Image dimensions: ${width}x${height}`);
    
    // Create output directory
    const outputDir = path.join(__dirname, 'temp', 'debug-output');
    if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
    }
    
    // Test different margin widths
    const marginTests = [
        { percent: 0.05, name: '5%' },
        { percent: 0.08, name: '8%' },
        { percent: 0.10, name: '10%' },
        { percent: 0.12, name: '12%' },
        { percent: 0.15, name: '15%' },
    ];
    
    // Initialize OCR worker with digit-only whitelist
    console.log('\nInitializing OCR...');
    const worker = await createWorker('eng');
    await worker.setParameters({
        tessedit_pageseg_mode: PSM.SINGLE_COLUMN,
        tessedit_char_whitelist: '0123456789',
    });
    
    const topMargin = Math.floor(height * 0.06);
    const bottomMargin = Math.floor(height * 0.06);
    const contentHeight = height - topMargin - bottomMargin;
    
    console.log(`\nTop margin: ${topMargin}px, Bottom margin: ${bottomMargin}px`);
    console.log(`Content height: ${contentHeight}px\n`);
    
    for (const test of marginTests) {
        const marginWidth = Math.floor(width * test.percent);
        const croppedPath = path.join(outputDir, `margin-${test.name.replace('%', 'pct')}.png`);
        
        // Crop the margin
        await sharp(imagePath)
            .extract({
                left: 0,
                top: topMargin,
                width: marginWidth,
                height: contentHeight
            })
            .greyscale()
            .normalize()
            .toFile(croppedPath);
        
        console.log(`Testing ${test.name} margin (${marginWidth}px wide)...`);
        
        // OCR the cropped margin
        const { data } = await worker.recognize(croppedPath);
        
        // Extract numbers
        const numbers = [];
        if (data.words) {
            for (const word of data.words) {
                const text = word.text.trim();
                if (/^[1-9]\d?$/.test(text)) {
                    const num = parseInt(text, 10);
                    if (num >= 1 && num <= 25) {
                        numbers.push({
                            text,
                            y: word.bbox.y0,
                            confidence: word.confidence
                        });
                    }
                }
            }
        }
        
        // Also check raw text
        const rawNumbers = [];
        if (data.text) {
            const lines = data.text.split('\n').filter(l => l.trim());
            for (const line of lines) {
                const match = line.trim().match(/^(\d{1,2})$/);
                if (match && parseInt(match[1]) >= 1 && parseInt(match[1]) <= 25) {
                    rawNumbers.push(match[1]);
                }
            }
        }
        
        console.log(`  Words: ${data.words?.length || 0}`);
        console.log(`  Line numbers from words: ${numbers.length} - [${numbers.map(n => n.text).join(', ')}]`);
        console.log(`  Line numbers from text: ${rawNumbers.length} - [${rawNumbers.join(', ')}]`);
        console.log(`  Raw text (first 200 chars): "${data.text?.substring(0, 200).replace(/\n/g, '\\n')}"`);
        console.log(`  Saved to: ${croppedPath}\n`);
    }
    
    // Also test with different preprocessing
    console.log('\n--- Testing different preprocessing ---\n');
    
    const marginWidth = Math.floor(width * 0.10);
    const preprocessTests = [
        { name: 'raw', fn: (img) => img },
        { name: 'sharpen', fn: (img) => img.sharpen({ sigma: 2 }) },
        { name: 'threshold-100', fn: (img) => img.threshold(100) },
        { name: 'threshold-150', fn: (img) => img.threshold(150) },
        { name: 'threshold-200', fn: (img) => img.threshold(200) },
        { name: 'negate', fn: (img) => img.negate() },
        { name: 'linear-contrast', fn: (img) => img.linear(1.5, -(128 * 1.5) + 128) },
    ];
    
    for (const test of preprocessTests) {
        const croppedPath = path.join(outputDir, `preprocess-${test.name}.png`);
        
        let pipeline = sharp(imagePath)
            .extract({
                left: 0,
                top: topMargin,
                width: marginWidth,
                height: contentHeight
            })
            .greyscale();
        
        pipeline = test.fn(pipeline);
        await pipeline.toFile(croppedPath);
        
        console.log(`Testing preprocessing: ${test.name}...`);
        
        const { data } = await worker.recognize(croppedPath);
        
        const numbers = [];
        if (data.words) {
            for (const word of data.words) {
                const text = word.text.trim();
                if (/^[1-9]\d?$/.test(text) && parseInt(text) <= 25) {
                    numbers.push(text);
                }
            }
        }
        
        console.log(`  Line numbers: ${numbers.length} - [${numbers.join(', ')}]`);
        console.log(`  Saved to: ${croppedPath}\n`);
    }
    
    // Test with PSM.SPARSE_TEXT mode
    console.log('\n--- Testing PSM.SPARSE_TEXT mode ---\n');
    
    await worker.setParameters({
        tessedit_pageseg_mode: PSM.SPARSE_TEXT,
    });
    
    const sparsePath = path.join(outputDir, 'margin-sparse.png');
    await sharp(imagePath)
        .extract({
            left: 0,
            top: topMargin,
            width: marginWidth,
            height: contentHeight
        })
        .greyscale()
        .normalize()
        .toFile(sparsePath);
    
    const { data: sparseData } = await worker.recognize(sparsePath);
    
    console.log(`Words: ${sparseData.words?.length || 0}`);
    console.log(`Raw text: "${sparseData.text?.substring(0, 300).replace(/\n/g, '\\n')}"`);
    
    // Cleanup
    await worker.terminate();
    imageConverter.cleanup(images);
    
    console.log('\n=== Test Complete ===');
    console.log(`Debug images saved to: ${outputDir}`);
}

// Get PDF path from command line
const pdfPath = process.argv[2] || './Transcripts/Deposition example.pdf';
const pageNum = parseInt(process.argv[3]) || 5; // Page 5 should have content with line numbers

testLineNumberExtraction(pdfPath, pageNum).catch(console.error);


