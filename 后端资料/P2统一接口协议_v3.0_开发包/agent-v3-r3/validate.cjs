// Validate proposed wire fixtures only. This does not run or validate backend business operations.
const fs = require('node:fs');
const path = require('node:path');
let Ajv;
try {
  const moduleExport = require(process.argv[2] || 'ajv');
  Ajv = moduleExport.default || moduleExport;
} catch {
  process.stderr.write('Use an environment with Ajv, or pass its installed module path: node validate.cjs <ajv-path>\n');
  process.exit(2);
}
const schema = JSON.parse(fs.readFileSync(path.join(__dirname, 'control.schema.json'), 'utf8'));
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'examples.json'), 'utf8'));
const ajv = new Ajv({allErrors: true});
if (!ajv.validateSchema(schema)) throw new Error(JSON.stringify(ajv.errors));
ajv.addSchema(schema);
let failed = 0;
for (const [list, expected] of [[fixtures.cases, true], [fixtures.invalidCases, false]]) {
  for (const item of list) {
    if (!schema.definitions[item.schema]) throw new Error(`Unknown schema: ${item.schema}`);
    const validate = ajv.compile({$ref: `${schema.$id}#/definitions/${item.schema}`});
    const valid = validate(item.body);
    if (valid !== expected) {
      failed++;
      process.stderr.write(`${item.name}: expected=${expected}, actual=${valid}\n${JSON.stringify(validate.errors)}\n`);
    }
  }
}
if (failed) process.exit(1);
process.stdout.write(`PASS: ${fixtures.cases.length} valid examples; ${fixtures.invalidCases.length} rejected counterexamples. Business-state tests are not included.\n`);
