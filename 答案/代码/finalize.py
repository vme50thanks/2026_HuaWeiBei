"""Independent checks, truthful metadata, Q4 refreeze and exhaustive solve."""
from pathlib import Path
import sys,subprocess,json
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
def run(p,*a):subprocess.run([sys.executable,str(p),*map(str,a)],check=True)
src='D:/研一/比赛/中文题目/D题';pre=ROOT/'outputs/preflight'
run(OUT/'normalize.py','q3')
run(ROOT/'outputs/q3/verify_joint.py','--source',src,'--preflight',pre,'--out',OUT/'q3')
s=load(OUT/'q3/summary.json');s['previous_search_metadata']={k:s.pop(k) for k in ['search','calendar_search'] if k in s}
s['new_search']={k:load(OUT/f) for k,f in [('relay_location','relay_location_search.json'),('joint_calendar','calendar_search.json')] if (OUT/f).exists()}
(OUT/'q3/summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
run(OUT/'prepare_q3.py')
# Replace inherited method paragraph before hashing; numerical tables above stay actual.
for f in ['模型与结果说明.md','独立检查报告.md']:
 p=OUT/'q3'/f;text=p.read_text(encoding='utf-8');start=text.index('新增通信服务日历');end=text.index('中继支持多机',start)
 text=text[:start]+'''本轮以已验证的前序方案作为可行上界。第二问增加三架次重组、整服务区货箱迁移，并分别以最多4点、5点扩大搜索；两次各240秒。第三问在原悬停位置周围以250、125、50米步长搜索平面位置，并比较150、200、250、300米离地高度；只有回传链路可用的位置进入匹配。再将中继服务窗口纳入货箱重组、机型、路线与排序搜索，240秒，最多4点。后续位置细化记录如存在，见relay_location_search.json及细化日志。各限制均为计算限制，不是题目限制。搜索阶段全部期望时限满足属于寻找D=0方案的计算限制，不把普通物资期望时间改称原题硬时限。只有D达到下界0，其余目标未证明全局最优。最终方法、种子、运行次数以搜索代码及日志为准。\n\n'''+text[end:]
 p.write_text(text,encoding='utf-8')
run(ROOT/'outputs/q4/solve_q4.py','--source',src,'--pre',pre,'--q3',OUT/'q3','--out',OUT/'q4')
run(ROOT/'outputs/q4/verify_q4.py','--source',src,'--pre',pre,'--q3',OUT/'q3','--out',OUT/'q4')
run(OUT/'report.py')
