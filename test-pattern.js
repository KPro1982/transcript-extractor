const pattern = /^([1-9]\d?)(\s|$)/;

console.log('Testing pattern:', pattern);
console.log('');
console.log('"1":', pattern.test('1'));
console.log('"14":', pattern.test('14'));
console.log('"14580":', pattern.test('14580'));
console.log('"2025":', pattern.test('2025'));
console.log('"25":', pattern.test('25'));
console.log('"5":', pattern.test('5'));




