const pattern = /^([1-9]\d?)(\s|$)/;

const tests = [
    "1 APPEARANCES",
    "14 SOMETHING",  
    "14580 some text",
    "2025",
    "5 BY: JAMES"
];

for (const test of tests) {
    const match = test.match(pattern);
    console.log(`\n"${test}"`);
    console.log(`  matches: ${!!match}`);
    if (match) {
        console.log(`  match[0]: "${match[0]}"`);
        console.log(`  match[1]: "${match[1]}"`);
        console.log(`  match[2]: "${match[2]}"`);
    }
}

