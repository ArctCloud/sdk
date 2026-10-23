import { mkdtemp, readFile, writeFile, mkdir, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const bootstrap = spawnSync('python3', [join(root, 'scripts/openapi_generator.py'), '--download-only'], { cwd: root, encoding: 'utf8' });
if (bootstrap.status !== 0) throw new Error(bootstrap.stderr || bootstrap.stdout);
const temp = await mkdtemp(join(tmpdir(), 'arct-typescript-'));
const target = join(root, 'typescript/src/generated');
try {
  const run = spawnSync('java', ['-jar', join(root, '.tools/openapi-generator-cli-7.26.0.jar'), 'generate',
    '-i', join(root, 'api/openapi.json'), '-g', 'typescript-fetch', '-o', temp,
    '--additional-properties=withoutRuntimeChecks=true,modelPropertyNaming=original,hideGenerationTimestamp=true,supportsES6=true,importFileExtension=.js',
    '--global-property=apis,models,supportingFiles,apiDocs=false,modelDocs=false,apiTests=false,modelTests=false'], { encoding: 'utf8' });
  if (run.status !== 0) throw new Error(run.stderr || run.stdout);
  const spec = JSON.parse(await readFile(join(root, 'api/openapi.json'), 'utf8'));
  const responses = new Set(Object.entries(spec.components.schemas).filter(([, s]) => s.type === 'object' && s.additionalProperties !== false).map(([n]) => n));
  const files = ['runtime.ts', 'index.ts', 'models/index.ts', 'apis/index.ts', ...(await readdir(join(temp, 'apis'))).filter(n => n !== 'index.ts').map(n => `apis/${n}`)];
  if (process.argv.includes('--check')) {
    const actual = (await readdir(target, { recursive: true, withFileTypes: true })).filter(entry => entry.isFile()).map(entry => join(entry.parentPath ?? entry.path, entry.name).slice(target.length + 1).replaceAll('\\', '/')).sort();
    if (JSON.stringify(actual) !== JSON.stringify([...files].sort())) throw new Error('Generated file-set drift.');
  } else {
    await rm(target, { recursive: true, force: true });
  }
  for (const file of files) {
    let source = await readFile(join(temp, file), 'utf8');
    source = source.replace(/\/\*[\s\S]*?\*\//g, comment => comment.includes('@deprecated') ? '/** @deprecated Use datacenter. */' : '').replace(/^\s*\/\/.*$/gm, '').replace(/[ \t]+\/\/[^\n]*$/gm, '').replace(/\n{3,}/g, '\n\n').trimStart();
    if (file === 'models/index.ts') {
      source = source.replace(/export interface ExpectedAmount \{\s*\}/, 'export type ExpectedAmount = number | string;');
      for (const [name, fields] of [['Location', ['datacenters']], ['Plan', ['datacenters']], ['Server', ['datacenter']], ['Account', ['credit_balance', 'credit_autopay']], ['ResizeOptions', ['payment_methods', 'credit_balance']]]) {
        for (const field of fields) source = source.replace(new RegExp(`(export interface ${name} \\{[\\s\\S]*?\\n    ${field})(\\??):`), '$1?:');
      }
      for (const name of responses) source = source.replace(`export interface ${name} {`, `export interface ${name} {\n    [key: string]: unknown;`);
      for (const name of ['VMStatus', 'InvoiceStatus', 'OrderPaymentMethodEnum', 'ResizeResponseStatusEnum']) {
        source = source.replace(`export type ${name} = typeof ${name}[keyof typeof ${name}];`, `export type ${name} = typeof ${name}[keyof typeof ${name}] | (string & {});`);
      }
    }
    source = ('// Generated file.\n' + source).split('\n').map(line => line.trimEnd()).join('\n').trimEnd() + '\n';
    const out = join(target, file);
    if (process.argv.includes('--check')) {
      if (source !== await readFile(out, 'utf8')) throw new Error(`Generated drift: ${file}`);
    } else {
      await mkdir(dirname(out), { recursive: true });
      await writeFile(out, source);
    }
  }
  console.log(`Generation ${process.argv.includes('--check') ? 'check' : 'complete'}: ${files.length} files, ${Object.values(spec.paths).flatMap(path => Object.values(path)).filter(operation => operation.operationId).length} operations`);
} finally { await rm(temp, { recursive: true, force: true }); }
