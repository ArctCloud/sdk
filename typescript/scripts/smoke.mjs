import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const consumer = await mkdtemp(join(tmpdir(), 'arct-consumer-'));
function run(args, cwd) {
  const result = spawnSync(process.execPath, args, { cwd, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(result.stdout + result.stderr);
  return result.stdout;
}
try {
  if (!process.env.npm_execpath) throw new Error('Run with npm run smoke.');
  const [pack] = JSON.parse(run([process.env.npm_execpath, 'pack', '--json', '--pack-destination', consumer], root));
  if (!pack.files.some(file => file.path === 'LICENSE')) throw new Error('Missing packaged license.');
  await writeFile(join(consumer, 'package.json'), '{"type":"module","private":true}');
  run([process.env.npm_execpath, 'install', '--ignore-scripts', '--no-audit', '--no-fund', join(consumer, pack.filename)], consumer);
  const installed = JSON.parse(await readFile(join(consumer, 'node_modules/@arct-cloud/sdk/package.json'), 'utf8'));
  if (Object.keys(installed.dependencies ?? {}).length) throw new Error('Unexpected runtime dependencies.');
  run(['--input-type=module', '-e', `import { Arct, Secret } from '@arct-cloud/sdk'; const client = new Arct({token:'test-only',fetch:async()=>new Response('{"id":"account"}')}); if((await client.account.get()).id!=='account') throw new Error('Request failed'); if(JSON.stringify(new Secret('hidden'))!=='"[REDACTED]"') throw new Error('Secret failed');`], consumer);
  await writeFile(join(consumer, 'consumer.ts'), `import { Arct, type CreateResult } from '@arct-cloud/sdk'; const a=new Arct({token:'x'}); const r:CreateResult=await a.servers.create({hostname:'web',location:'fra',plan:'vm.small',image_id:'id'}); const id:string=r.order.id; r.password?.getSecretValue(); void id;`);
  run([join(root, 'node_modules/typescript/bin/tsc'), '--noEmit', '--strict', '--target', 'ES2022', '--module', 'NodeNext', '--moduleResolution', 'NodeNext', 'consumer.ts'], consumer);
  console.log(`Tarball: ${pack.entryCount} files, license included, zero runtime dependencies`);
  console.log('Clean installed ESM import, injected request and secret masking: pass');
  console.log('Strict installed declarations without skipLibCheck or @types/node: pass');
} finally { await rm(consumer, { recursive: true, force: true }); }
