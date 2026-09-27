from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
files=[p for p in OUT.rglob('*') if p.is_file() and p.suffix not in ['.zip','.pyc'] and '__pycache__' not in p.parts and 'replay_q3' not in p.parts and p.name!='artifact_manifest.json']
for q in ['q2','q3','q4']:
 files+=list((ROOT/'outputs'/q).glob('*.py'));files.append(ROOT/'outputs'/q/'summary.json');files.append(ROOT/'outputs/refinement'/q/'summary.json')
files+=list((ROOT/'outputs/q3/support').glob('*.py'))
files+=[ROOT/'outputs/q3/temporal_expanded.json',ROOT/'outputs/q3/ridge_search/relay_candidates.json']
for base in ['outputs','outputs/refinement']:
 for q in ['q2','q3']:
  for name in ['baseline','makespan_first']:
   files.append(ROOT/base/q/name/'plan.json')
   if q=='q3':files.append(ROOT/base/q/name/'relay_plan.json')
files += [p for p in (ROOT/'outputs/preflight').iterdir() if p.is_file() and p.suffix in ['.csv','.json','.md']]
files=sorted(set(files));manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');files.append(OUT/'artifact_manifest.json')
with zipfile.ZipFile(OUT/'问题二三四优化成果.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(OUT/'问题二三四优化成果.zip') as z:assert z.testzip() is None
print('Packaged',len(files),'files',flush=True)
