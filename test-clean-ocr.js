/**
 * Test the OCR cleaning function
 */

// Smart OCR cleaning function for common misreadings
function cleanOCRNumber(text) {
    const ocrFixes = {
        'Z': '2', 'z': '2',
        '€': '5',
        '¢': '6',
        'C': '0', 'c': '0',
        'O': '0', 'o': '0',
        'l': '1', 'I': '1', '|': '1',
        'S': '5', 's': '5',
        'B': '8',
        'g': '9', 'q': '9',
        ':': '3',
        '(': '0',
        ')': '0',
        '°': '5',
        '&': '8',
        '.': '',
        ',': '',
        ';': '',
        "'": '',
        '"': '',
        '`': '',
    };
    
    let cleaned = '';
    for (const char of text) {
        cleaned += ocrFixes[char] !== undefined ? ocrFixes[char] : char;
    }
    return cleaned;
}

// Test with the actual OCR output we saw
const testInput = "1\nZ\nZ\n€\nI\n€\nc\n1C\n11\n12\n1:z\n14\n1C\n1¢\n17\n1¢&\n1¢\n2(\n21\n22\n2:\n24\n2°";

console.log('Testing OCR cleanup:');
console.log('Raw input:', testInput.replace(/\n/g, ' | '));
console.log('');

const lines = testInput.split('\n');
const results = [];

for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();
    const cleaned = cleanOCRNumber(raw);
    const num = parseInt(cleaned, 10);
    const isValid = /^\d{1,2}$/.test(cleaned) && num >= 1 && num <= 25;
    
    results.push({
        raw,
        cleaned,
        expected: i + 1,
        isValid,
        correct: isValid && num === i + 1
    });
    
    console.log(`Line ${i + 1}: "${raw}" -> "${cleaned}" (expected ${i + 1}) ${isValid ? '✓' : '✗'} ${num === i + 1 ? '✓✓' : ''}`);
}

const validCount = results.filter(r => r.isValid).length;
const correctCount = results.filter(r => r.correct).length;

console.log('');
console.log(`Valid line numbers: ${validCount}/${lines.length}`);
console.log(`Correctly matched: ${correctCount}/${lines.length}`);





