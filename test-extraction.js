const fs = require('fs');
const http = require('http');
const path = require('path');

const pdfPath = path.join(__dirname, 'Transcripts', 'Deposition example.pdf');
const pdfData = fs.readFileSync(pdfPath);
const boundary = '----FormBoundary' + Math.random().toString(36).substring(2);

const body = Buffer.concat([
    Buffer.from(`--${boundary}\r\n`),
    Buffer.from('Content-Disposition: form-data; name="pdf"; filename="test.pdf"\r\n'),
    Buffer.from('Content-Type: application/pdf\r\n\r\n'),
    pdfData,
    Buffer.from(`\r\n--${boundary}--\r\n`)
]);

const options = {
    hostname: 'localhost',
    port: 3000,
    path: '/api/extract-hybrid?preview=true',
    method: 'POST',
    headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        'Content-Length': body.length
    }
};

const req = http.request(options, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
        const result = JSON.parse(data);
        console.log(`Pages extracted: ${result.pageCount} / ${result.totalPages}\n`);
        
        // Show all pages
        const lines = result.text.split('\n');
        let currentPage = 0;
        let lineCount = 0;
        
        for (const line of lines) {
            // Detect page headers
            if (line.match(/^PAGE \d+/)) {
                currentPage++;
                console.log('\n' + '='.repeat(70));
                console.log(line);
                console.log('='.repeat(70));
                lineCount = 0;
            } else if (line.includes('--- CONTENT ---')) {
                console.log(line);
            } else if (line.match(/^\s*\d{1,2}\s*\|/)) {
                // Line with line number
                console.log(line);
                lineCount++;
            } else if (line.match(/^\s+\|/) && lineCount < 30) {
                // Unmatched content (should be rare now)
                console.log(line);
            }
        }
    });
});

req.on('error', e => console.error('Error:', e.message));
req.write(body);
req.end();

