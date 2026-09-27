"""Canonicalize sub-nanosecond arithmetic ties before exact resource event replay."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'outputs/q2'))
from solve_q2 import Problem,export,score,dump
pr=Problem(Path('D:/研一/比赛/中文题目/D题'),ROOT/'outputs/preflight')
folder=Path(__file__).parent/sys.argv[1];s=json.loads((folder/'summary.json').read_text(encoding='utf-8'));changes=[]
for name in ['baseline','makespan_first']:
 p=json.loads((folder/name/'plan.json').read_text(encoding='utf-8'));ur={};br={};ans=[]
 for old in sorted(p,key=lambda x:(x['start'],x['sortie'])):
  start=max(old['start'],ur.get(old['unit'],0),br.get(old['battery'],0));assert start-old['start']<1e-7
  q=pr.evaluate(old['model'],old['boxes'],old['route'],start);assert q is not None
  q.update(unit=old['unit'],battery=old['battery'],sortie=old['sortie'],charge_start=q['finish'],battery_ready=q['finish']+pr.charge(q['model'],q['soc']))
  ur[q['unit']]=q['finish'];br[q['battery']]=q['battery_ready'];ans.append(q);changes.append(abs(start-old['start']))
 ans.sort(key=lambda x:x['sortie']);export(pr,ans,folder,name);s[name].update(zip(['D','Cmax','E','N'],score(pr,ans)))
 if 'C_joint' in s[name]:
  r=json.loads((folder/name/'relay_plan.json').read_text(encoding='utf-8'));s[name]['C_joint']=max(x['finish'] for x in ans+r);s[name]['total_E']=s[name]['E']+s[name]['relay_E']
# A 1e-12 s arithmetic tie must not justify sacrificing actual on-time delivery.
if sys.argv[1]=='q2' and abs(s['baseline']['Cmax']-s['makespan_first']['Cmax'])<1e-7 and s['baseline']['D']<s['makespan_first']['D']:
 p=json.loads((folder/'baseline/plan.json').read_text(encoding='utf-8'));export(pr,p,folder,'makespan_first');s['makespan_first']=dict(s['baseline']);s['alternative_note']='Numerically tied makespan: selected zero-delay plan at 1e-7 s comparison tolerance.'
s['canonicalization_max_shift_s']=max(changes,default=0);dump(folder/'summary.json',s);print('max timestamp change',max(changes,default=0))
