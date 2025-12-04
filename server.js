const http = require('http');
const fs = require('fs');
const path = require('path');

// Add Ghostscript to PATH if installed in standard location
const gsPath = 'C:\\Program Files\\gs\\gs10.02.1\\bin';
if (fs.existsSync(gsPath)) {
    process.env.PATH = gsPath + ';' + process.env.PATH;
    console.log('Added Ghostscript to PATH:', gsPath);
}

const { TextReconstructor } = require('./dist/text-reconstructor.js');

const PORT = 3000;
const UPLOAD_DIR = path.join(__dirname, 'temp', 'uploads');
const IMAGES_DIR = path.join(__dirname, 'temp', 'images');

// Ensure directories exist
[UPLOAD_DIR, IMAGES_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// Clean old images on startup
fs.readdirSync(IMAGES_DIR).forEach(file => {
    fs.unlinkSync(path.join(IMAGES_DIR, file));
});

/**
 * Parse Q/A pairs from examination content
 * Each Q/A object contains:
 * - question: text snippet
 * - questionLocation: page:startLine-endLine
 * - answer: text snippet
 * - answerLocation: page:startLine-endLine
 * - colloquy: text snippet (objections, etc.)
 * - colloquyLocation: page:startLine-endLine
 */
function parseExamination(pages, firstPrintedPage) {
    const qaItems = [];
    
    // Flatten all lines with page/line info
    const allLines = [];
    for (let i = 0; i < pages.length; i++) {
        const printedPage = (i + 1) - firstPrintedPage + 1;
        const page = pages[i];
        const lines = page.lines || [];
        
        for (const line of lines) {
            allLines.push({
                text: line.text || '',
                lineNumber: line.lineNumber,
                pageIndex: i,
                printedPage: printedPage
            });
        }
    }
    
    // Find examination start
    let examStart = -1;
    for (let i = 0; i < allLines.length; i++) {
        const text = allLines[i].text.trim();
        // Look for "EXAMINATION" header or "BY MR./MS. X:"
        if (text.match(/^EXAMINATION$/i) || 
            text.match(/^BY\s+M[RS]\.\s+\w+:$/i) ||
            text.match(/EXAMINATION\s*$/i)) {
            examStart = i;
            break;
        }
    }
    
    if (examStart === -1) {
        // Try to find first Q. or QUESTION if no EXAMINATION header
        // Handle patterns with middle dots like "· · ·Q.·"
        for (let i = 0; i < allLines.length; i++) {
            const lineText = allLines[i].text;
            if (lineText.match(/[·\s]*Q\.[·\s]/i) || 
                lineText.match(/^\s*Q\.\s+/i) || 
                lineText.match(/^\s*QUESTION[:\s]/i)) {
                examStart = i;
                break;
            }
        }
    }
    
    if (examStart === -1) {
        console.log('Could not find examination section');
        return qaItems;
    }
    
    console.log(`Found examination starting at line ${examStart}`);
    
    // Parse Q/A pairs
    let currentQ = null;
    let currentA = null;
    let currentColloquy = null;
    let state = 'searching'; // searching, in_question, in_colloquy, in_answer
    
    for (let i = examStart; i < allLines.length; i++) {
        const line = allLines[i];
        const text = line.text;
        const trimmed = text.trim();
        
        // Skip empty lines
        if (!trimmed) continue;
        
        // Check if this is a Question line (Q. or QUESTION or Question:)
        // Handle patterns like "· · ·Q.·" with middle dots
        const isQuestion = trimmed.match(/^Q\.\s*/i) || 
                          text.match(/^\s+Q\.\s*/i) ||
                          trimmed.match(/^[·\s]*Q\.[·\s]/i) ||
                          trimmed.match(/^QUESTION[:\s]/i) ||
                          trimmed.match(/^Question[:\s]/i);
        // Check if this is an Answer line (A. or ANSWER or Answer:)
        // Handle patterns like "· · ·A.·" with middle dots
        const isAnswer = trimmed.match(/^A\.\s*/i) || 
                        text.match(/^\s+A\.\s*/i) ||
                        trimmed.match(/^[·\s]*A\.[·\s]/i) ||
                        trimmed.match(/^ANSWER[:\s]/i) ||
                        trimmed.match(/^Answer[:\s]/i);
        // Check if this is THE WITNESS: (answer after objection)
        const isWitnessAnswer = trimmed.match(/^[·\s]*THE\s+WITNESS:[·\s]*/i) ||
                               trimmed.match(/^THE\s+WITNESS:/i);
        // Check if this is colloquy (attorney speaking, objection, etc.)
        // But NOT "THE WITNESS:" which is an answer
        const isColloquy = (trimmed.match(/^M[RS]\.\s+\w+:/i) || 
                          trimmed.match(/^THE\s+(REPORTER|COURT):/i) ||
                          trimmed.match(/^\(.*\)$/) || // Parenthetical notes
                          trimmed.match(/^[·\s]*M[RS]\.\s+\w+:/i) ||
                          trimmed.match(/^BY\s+M[RS]\.\s+\w+:$/i)) && // Return to questioning
                          !isWitnessAnswer;
        
        // Check for end of examination (certificate, signature pages)
        if (trimmed.match(/^CERTIFICATE OF REPORTER/i) ||
            trimmed.match(/^PENALTY OF PERJURY/i) ||
            trimmed.match(/^CHANGES AND SIGNATURE/i)) {
            // Save current Q/A if complete
            if (currentQ && currentA) {
                qaItems.push({
                    question: currentQ.text,
                    questionLocation: formatLocation(currentQ),
                    answer: currentA.text,
                    answerLocation: formatLocation(currentA),
                    colloquy: currentColloquy ? currentColloquy.text : '',
                    colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : ''
                });
            }
            break;
        }
        
        if (isQuestion) {
            // Save previous Q/A if complete
            if (currentQ && currentA) {
                qaItems.push({
                    question: currentQ.text,
                    questionLocation: formatLocation(currentQ),
                    answer: currentA.text,
                    answerLocation: formatLocation(currentA),
                    colloquy: currentColloquy ? currentColloquy.text : '',
                    colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : ''
                });
            }
            
            // Start new question
            currentQ = {
                text: cleanQAText(text),
                startPage: line.printedPage,
                startLine: line.lineNumber,
                endPage: line.printedPage,
                endLine: line.lineNumber
            };
            currentA = null;
            currentColloquy = null;
            state = 'in_question';
            
        } else if (isAnswer || isWitnessAnswer) {
            if (currentQ) {
                // Start answer - handle both A. and THE WITNESS:
                const answerText = isWitnessAnswer 
                    ? cleanWitnessText(text)
                    : cleanQAText(text);
                    
                if (!currentA) {
                    // Start new answer
                    currentA = {
                        text: answerText,
                        startPage: line.printedPage,
                        startLine: line.lineNumber,
                        endPage: line.printedPage,
                        endLine: line.lineNumber
                    };
                } else {
                    // Continue existing answer (another THE WITNESS: line)
                    currentA.text += ' ' + answerText;
                    currentA.endPage = line.printedPage;
                    currentA.endLine = line.lineNumber;
                }
                state = 'in_answer';
            }
            
        } else if (isColloquy) {
            if (state === 'in_question' || state === 'in_colloquy') {
                // Colloquy between question and answer (objection, etc.)
                if (!currentColloquy) {
                    currentColloquy = {
                        text: cleanColloquyText(trimmed),
                        startPage: line.printedPage,
                        startLine: line.lineNumber,
                        endPage: line.printedPage,
                        endLine: line.lineNumber
                    };
                } else {
                    currentColloquy.text += ' ' + cleanColloquyText(trimmed);
                    currentColloquy.endPage = line.printedPage;
                    currentColloquy.endLine = line.lineNumber;
                }
                state = 'in_colloquy';
            } else if (state === 'in_answer') {
                // In answer state, colloquy might indicate end of this Q/A
                // or continuation - we'll treat it as end and let next Q pick it up
            }
            
        } else {
            // Continuation of current element
            if (state === 'in_question' && currentQ) {
                currentQ.text += ' ' + trimmed;
                currentQ.endPage = line.printedPage;
                currentQ.endLine = line.lineNumber;
            } else if (state === 'in_answer' && currentA) {
                currentA.text += ' ' + trimmed;
                currentA.endPage = line.printedPage;
                currentA.endLine = line.lineNumber;
            } else if (state === 'in_colloquy' && currentColloquy) {
                currentColloquy.text += ' ' + trimmed;
                currentColloquy.endPage = line.printedPage;
                currentColloquy.endLine = line.lineNumber;
            }
        }
    }
    
    // Don't forget the last Q/A pair
    if (currentQ && currentA) {
        qaItems.push({
            question: currentQ.text,
            questionLocation: formatLocation(currentQ),
            answer: currentA.text,
            answerLocation: formatLocation(currentA),
            colloquy: currentColloquy ? currentColloquy.text : '',
            colloquyLocation: currentColloquy ? formatLocation(currentColloquy) : ''
        });
    }
    
    console.log(`Parsed ${qaItems.length} Q/A pairs`);
    return qaItems;
}

function cleanQAText(text) {
    // Remove Q./A./QUESTION/ANSWER prefix and clean up middle dots/spacing
    // Handle patterns like "· · ·Q.· text" or "· · ·A.· text"
    return text
        .replace(/^[·\s]*Q\.[·\s]*/i, '')
        .replace(/^[·\s]*A\.[·\s]*/i, '')
        .replace(/^\s*QUESTION[:\s]*/i, '')
        .replace(/^\s*ANSWER[:\s]*/i, '')
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function cleanWitnessText(text) {
    // Remove "THE WITNESS:" prefix and clean up
    return text
        .replace(/^[·\s]*THE\s+WITNESS:[·\s]*/i, '')
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function cleanColloquyText(text) {
    // Clean up colloquy text (keep the speaker label for context)
    return text
        .replace(/·/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function formatLocation(item) {
    if (item.startPage === item.endPage) {
        if (item.startLine === item.endLine) {
            return `${item.startPage}:${item.startLine}`;
        }
        return `${item.startPage}:${item.startLine}-${item.endLine}`;
    }
    return `${item.startPage}:${item.startLine}-${item.endPage}:${item.endLine}`;
}

/**
 * Extract text and images from PDF for side-by-side viewing
 */
async function extractPDFWithImages(pdfPath) {
    const { ExternalPDFToImageConverter } = require('./dist/pdf-to-image-external.js');
    const pdfjsLib = require('pdfjs-dist');
    
    if (pdfjsLib.GlobalWorkerOptions) {
        pdfjsLib.GlobalWorkerOptions.workerSrc = '';
    }

    // Get PDF info
    const pdfBuffer = fs.readFileSync(pdfPath);
    const pdfBytes = new Uint8Array(pdfBuffer);
    const loadingTask = pdfjsLib.getDocument({ data: pdfBytes, useWorkerFetch: false, isEvalSupported: false });
    const pdfDoc = await loadingTask.promise;
    const totalPages = pdfDoc.numPages;

    // Convert PDF to images (use lower DPI for display)
    const imageConverter = new ExternalPDFToImageConverter({ dpi: 150, outputDir: IMAGES_DIR });
    const images = await imageConverter.convert(pdfPath);
    
    console.log(`  Converting ${totalPages} pages...`);

    // Legal transcript settings
    const LINES_PER_PAGE = 25;
    const topMarginPercent = 0.10;
    const bottomMarginPercent = 0.10;

    const pages = [];

    for (let pageNum = 1; pageNum <= totalPages; pageNum++) {

        // Get digital text
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        
        const { width, height } = viewport;
        const textItems = [];
        
        for (const item of (textContent.items || [])) {
            const str = item.str || '';
            if (!str.trim()) continue;
            const transform = item.transform || [];
            textItems.push({
                text: str,
                x: transform[4] || 0,
                y: height - (transform[5] || 0),
                width: item.width || 0,
                height: item.height || 12,
            });
        }

        // Find content bounds
        const contentItems = textItems.filter(item => item.x > width * 0.1);
        let minY = height, maxY = 0;
        for (const item of contentItems) {
            if (item.y < minY) minY = item.y;
            if (item.y > maxY) maxY = item.y;
        }

        if (contentItems.length === 0) {
            minY = height * topMarginPercent;
            maxY = height * (1 - bottomMarginPercent);
        }

        // Calculate line positions
        const contentSpan = maxY - minY;
        const lineHeight = contentSpan / (LINES_PER_PAGE - 1) || (height * 0.8 / LINES_PER_PAGE);

        // Generate line numbers with Y positions
        const lineNumbers = [];
        for (let num = 1; num <= LINES_PER_PAGE; num++) {
            const yPosition = minY + (num - 1) * lineHeight;
            lineNumbers.push({
                text: String(num),
                position: { x: 0, y: yPosition, width: 20, height: lineHeight },
                confidence: 100,
                type: 'line_number',
            });
        }

        // Categorize content
        const digitalLeftMargin = width * 0.10;
        const headerBound = minY - lineHeight;
        const footerBound = maxY + lineHeight;

        const mainContent = [];
        for (const item of textItems) {
            const centerY = item.y + (item.height || 0) / 2;
            const centerX = item.x + (item.width || 0) / 2;

            if (centerY >= headerBound && centerY <= footerBound && centerX >= digitalLeftMargin) {
                mainContent.push({
                    text: item.text,
                    position: { x: item.x, y: item.y, width: item.width, height: item.height },
                    confidence: 100,
                    type: 'content',
                });
            }
        }

        // Use TextReconstructor to merge line numbers with content
        const reconstructor = new TextReconstructor();
        const merged = reconstructor.mergeLineNumbersWithContent(lineNumbers, mainContent);

        // Get image URL
        const imageFile = images[pageNum - 1];
        const imageFileName = path.basename(imageFile.imagePath);

        pages.push({
            pageNumber: pageNum,
            imageUrl: `/images/${imageFileName}`,
            lines: merged.filter(m => m.lineNumber).map(m => ({
                lineNumber: m.lineNumber,
                text: m.text || ''
            })),
            unmatched: merged.filter(m => !m.lineNumber && m.text).map(m => m.text)
        });

    }

    console.log(`  ✓ Text extracted from ${totalPages} pages`);
    return { pages, totalPages };
}

const server = http.createServer(async (req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(200);
        res.end();
        return;
    }

    const url = new URL(req.url, `http://localhost:${PORT}`);

    // Serve page images
    if (req.method === 'GET' && url.pathname.startsWith('/images/')) {
        const imageName = url.pathname.replace('/images/', '');
        const imagePath = path.join(IMAGES_DIR, imageName);
        
        if (fs.existsSync(imagePath)) {
            const ext = path.extname(imagePath).toLowerCase();
            const mimeTypes = { '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg' };
            res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'image/png' });
            fs.createReadStream(imagePath).pipe(res);
            return;
        } else {
            res.writeHead(404);
            res.end('Image not found');
            return;
        }
    }

    // Parse Q/A endpoint
    if (req.method === 'POST' && url.pathname === '/api/parse-qa') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const body = JSON.parse(Buffer.concat(chunks).toString());
                const { pages, firstPrintedPage } = body;
                
                console.log(`\nParsing Q/A with first printed page = ${firstPrintedPage}`);
                const qaItems = parseExamination(pages, firstPrintedPage);
                
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    qaItems: qaItems,
                    totalQA: qaItems.length
                }));
            } catch (error) {
                console.error('Parse error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to parse: ' + error.message }));
            }
        });
        return;
    }

    // PDF extraction endpoint
    if (req.method === 'POST' && url.pathname === '/api/extract') {
        const chunks = [];
        req.on('data', chunk => chunks.push(chunk));
        req.on('end', async () => {
            try {
                const buffer = Buffer.concat(chunks);
                const boundary = req.headers['content-type'].split('boundary=')[1];
                const parts = parseMultipart(buffer, boundary);
                
                const filePart = parts.find(p => p.filename);
                if (!filePart) {
                    res.writeHead(400, { 'Content-Type': 'application/json' });
                    res.end(JSON.stringify({ error: 'No PDF file uploaded' }));
                    return;
                }

                const tempPath = path.join(UPLOAD_DIR, `upload_${Date.now()}.pdf`);
                fs.writeFileSync(tempPath, filePart.data);

                console.log(`\n${'='.repeat(50)}`);
                console.log(`Processing: ${filePart.filename}`);
                console.log(`${'='.repeat(50)}`);

                const result = await extractPDFWithImages(tempPath);

                // Clean up uploaded file
                fs.unlinkSync(tempPath);

                console.log(`\n✓ Extraction complete: ${result.totalPages} pages\n`);

                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({
                    success: true,
                    filename: filePart.filename,
                    pages: result.pages,
                    totalPages: result.totalPages
                }));

            } catch (error) {
                console.error('Extraction error:', error);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: 'Failed to extract: ' + error.message }));
            }
        });
        return;
    }

    // Serve static files
    let filePath = path.join(__dirname, 'public', url.pathname === '/' ? 'index.html' : url.pathname);
    const extname = String(path.extname(filePath)).toLowerCase();
    const mimeTypes = {
        '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
        '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpg',
        '.gif': 'image/gif', '.svg': 'image/svg+xml', '.pdf': 'application/pdf'
    };
    
    fs.readFile(filePath, (error, content) => {
        if (error) {
            res.writeHead(error.code === 'ENOENT' ? 404 : 500, { 'Content-Type': 'text/html' });
            res.end(error.code === 'ENOENT' ? '<h1>404 - Not Found</h1>' : 'Server Error');
        } else {
            res.writeHead(200, { 'Content-Type': mimeTypes[extname] || 'application/octet-stream' });
            res.end(content);
        }
    });
});

function parseMultipart(buffer, boundary) {
    const parts = [];
    const boundaryBuffer = Buffer.from('--' + boundary);
    let start = buffer.indexOf(boundaryBuffer) + boundaryBuffer.length;
    
    while (start < buffer.length) {
        let end = buffer.indexOf(boundaryBuffer, start);
        if (end === -1) break;
        
        const partData = buffer.slice(start, end);
        const headerEnd = partData.indexOf('\r\n\r\n');
        if (headerEnd === -1) { start = end + boundaryBuffer.length; continue; }
        
        const headers = partData.slice(0, headerEnd).toString();
        const body = partData.slice(headerEnd + 4, -2);
        
        parts.push({
            name: (headers.match(/name="([^"]+)"/) || [])[1],
            filename: (headers.match(/filename="([^"]+)"/) || [])[1],
            data: body
        });
        
        start = end + boundaryBuffer.length;
        if (buffer.slice(end + boundaryBuffer.length, end + boundaryBuffer.length + 2).toString() === '--') break;
    }
    return parts;
}

server.listen(PORT, () => {
    console.log(`\n${'='.repeat(50)}`);
    console.log('  DepoDigest - Deposition Summarization Tool');
    console.log(`${'='.repeat(50)}`);
    console.log(`\n  Server: http://localhost:${PORT}/`);
    console.log(`\n  Features:`);
    console.log('    - Upload deposition PDFs');
    console.log('    - Confirm first printed page number');
    console.log('    - Parse Q/A examination section');
    console.log('    - Navigate through Q/A pairs');
    console.log(`\n${'='.repeat(50)}\n`);

    // Open in default browser
    const { exec } = require('child_process');
    const url = `http://localhost:${PORT}/`;
    
    // Windows
    exec(`start ${url}`);
});
