const { exec } = require('child_process');
const { promisify } = require('util');
const execAsync = promisify(exec);

async function test() {
    console.log('Testing Ghostscript detection...\n');
    
    const command = process.platform === 'win32' ? 'gswin64c --version' : 'gs --version';
    console.log(`Command: ${command}`);
    console.log(`Platform: ${process.platform}\n`);
    
    try {
        const result = await execAsync(command);
        console.log('✓ SUCCESS!');
        console.log('Output:', result.stdout.trim());
        console.log('Stderr:', result.stderr);
        return true;
    } catch (error) {
        console.log('✗ FAILED!');
        console.log('Error:', error.message);
        console.log('Code:', error.code);
        console.log('Stderr:', error.stderr);
        return false;
    }
}

test().then(success => {
    console.log(`\nResult: ${success ? 'Ghostscript IS available' : 'Ghostscript NOT available'}`);
    process.exit(success ? 0 : 1);
});

