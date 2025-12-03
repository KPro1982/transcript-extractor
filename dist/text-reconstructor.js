"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TextReconstructor = void 0;
class TextReconstructor {
    reconstructText(pages, options) {
        switch (options.format) {
            case 'json':
                return this.toJSON(pages);
            case 'md':
                return this.toMarkdown(pages, options);
            case 'txt':
            default:
                return this.toPlainText(pages, options);
        }
    }
    toPlainText(pages, options) {
        let output = '';
        for (const page of pages) {
            output += `${'='.repeat(80)}\n`;
            output += `PAGE ${page.pageNumber} (${page.dimensions.width.toFixed(0)} x ${page.dimensions.height.toFixed(0)}) - Confidence: ${page.confidence.toFixed(1)}%\n`;
            output += `${'='.repeat(80)}\n\n`;
            // Headers
            if (page.headers.length > 0) {
                output += '--- HEADERS ---\n';
                output += this.formatBlocks(page.headers, options);
                output += '\n';
            }
            // Line Numbers & Content
            if (page.lineNumbers.length > 0 || page.mainContent.length > 0) {
                output += '--- CONTENT ---\n';
                // Merge line numbers with content by proximity
                const merged = this.mergeLineNumbersWithContent(page.lineNumbers, page.mainContent);
                for (const item of merged) {
                    if (item.lineNumber) {
                        output += `${item.lineNumber.padStart(4)} | `;
                    }
                    else {
                        output += '     | ';
                    }
                    output += item.text;
                    if (options.includeConfidence && item.confidence !== undefined) {
                        output += ` [${item.confidence.toFixed(1)}%]`;
                    }
                    output += '\n';
                }
                output += '\n';
            }
            // Footers
            if (page.footers.length > 0) {
                output += '--- FOOTERS ---\n';
                output += this.formatBlocks(page.footers, options);
                output += '\n';
            }
        }
        return output;
    }
    toMarkdown(pages, options) {
        let output = '# PDF OCR Extraction\n\n';
        for (const page of pages) {
            output += `## Page ${page.pageNumber}\n\n`;
            if (options.includeConfidence) {
                output += `*Confidence: ${page.confidence.toFixed(1)}%*\n\n`;
            }
            if (page.headers.length > 0) {
                output += '### Headers\n\n';
                page.headers.forEach(h => {
                    output += `${h.text}  \n`;
                });
                output += '\n';
            }
            if (page.mainContent.length > 0) {
                output += '### Content\n\n';
                const merged = this.mergeLineNumbersWithContent(page.lineNumbers, page.mainContent);
                for (const item of merged) {
                    if (item.lineNumber) {
                        output += `**${item.lineNumber}** `;
                    }
                    output += `${item.text}  \n`;
                }
                output += '\n';
            }
            if (page.footers.length > 0) {
                output += '### Footers\n\n';
                page.footers.forEach(f => {
                    output += `${f.text}  \n`;
                });
                output += '\n';
            }
            output += '---\n\n';
        }
        return output;
    }
    toJSON(pages) {
        return JSON.stringify({ pages }, null, 2);
    }
    formatBlocks(blocks, options) {
        let output = '';
        for (const block of blocks) {
            if (options.includePositions) {
                output += `[${block.position.x.toFixed(0)}, ${block.position.y.toFixed(0)}] `;
            }
            output += block.text;
            if (options.includeConfidence) {
                output += ` [${block.confidence.toFixed(1)}%]`;
            }
            output += '\n';
        }
        return output;
    }
    mergeLineNumbersWithContent(lineNumbers, content) {
        const merged = [];
        
        // Calculate line height from line numbers if available
        let lineHeight = 30; // Default
        if (lineNumbers.length >= 2) {
            lineHeight = Math.abs(lineNumbers[1].position.y - lineNumbers[0].position.y);
        }
        const tolerance = lineHeight * 0.6; // Match within 60% of line height
        
        // For each line number, find content that falls within its range
        const usedContent = new Set();
        
        for (const lineNum of lineNumbers) {
            const lineY = lineNum.position.y;
            const rangeTop = lineY - tolerance / 2;
            const rangeBottom = lineY + tolerance / 2;
            
            // Find all content blocks within this line's Y range
            const matchedBlocks = [];
            for (let i = 0; i < content.length; i++) {
                if (usedContent.has(i)) continue;
                
                const block = content[i];
                const blockCenterY = block.position.y + (block.position.height || 0) / 2;
                
                if (blockCenterY >= rangeTop && blockCenterY <= rangeBottom) {
                    matchedBlocks.push({ block, index: i });
                }
            }
            
            // Sort matched blocks by X position (left to right)
            matchedBlocks.sort((a, b) => a.block.position.x - b.block.position.x);
            
            // Mark these blocks as used
            matchedBlocks.forEach(m => usedContent.add(m.index));
            
            // Combine text from matched blocks
            const text = matchedBlocks.map(m => m.block.text).join(' ');
            const confidence = matchedBlocks.length > 0 
                ? Math.min(lineNum.confidence, ...matchedBlocks.map(m => m.block.confidence))
                : lineNum.confidence;
            
            merged.push({
                lineNumber: lineNum.text,
                text: text.trim(),
                confidence,
            });
        }
        
        // Add any remaining unmatched content at the end
        for (let i = 0; i < content.length; i++) {
            if (!usedContent.has(i)) {
                merged.push({
                    text: content[i].text,
                    confidence: content[i].confidence,
                });
            }
        }
        
        return merged;
    }
}
exports.TextReconstructor = TextReconstructor;
