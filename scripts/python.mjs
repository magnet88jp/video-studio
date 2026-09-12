import {existsSync,mkdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const python=process.env.EDITOR_PYTHON || (existsSync(path.join(root,'work/analysis-venv/bin/python'))?path.join(root,'work/analysis-venv/bin/python'):'python3');
mkdirSync(path.join(root,'work/python-cache'),{recursive:true});
const result=spawnSync(python,process.argv.slice(2),{cwd:root,stdio:'inherit',env:{...process.env,PYTHONPYCACHEPREFIX:path.join(root,'work/python-cache')}});
if(result.error)throw result.error;process.exit(result.status??1);
