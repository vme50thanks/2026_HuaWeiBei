from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).parent
s=(ROOT/'outputs/q3/solve_joint.py').read_text(encoding='utf-8');f=s[s.index('def fit('):s.index('\ndef main(')]
f=f.replace('start=float(tt.min())-5;end=float(tt.max())+5',"start=max(c['earliest_service'],float(tt.min())-5);end=float(tt.max())+5\n    if start>float(tt.min()):break")
(OUT/'fit_v2.py').write_text('import numpy as np\n'+f,encoding='utf-8')
