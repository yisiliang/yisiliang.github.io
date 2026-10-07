// Called by repair_source_excerpts.py; reads a JSON array of {language, code}.
const fs = require('node:fs');
const hljs = require('highlight.js');
const inputs = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(inputs.map(({language, code}) => hljs.highlight(code, {language}).value)));
