from pathlib import Path
import json,csv
p=Path(__file__).resolve().parent
def read(name):
    with (p/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
s=json.loads((p/'summary.json').read_text(encoding='utf-8'));b=s[0];alt=s[1]
v=json.loads((p/'verification.json').read_text(encoding='utf-8'))
manifest=json.loads((p/'run_manifest.json').read_text(encoding='utf-8'))
caps=read('safe_payloads_45.csv');plans=json.loads((p/'solutions.json').read_text(encoding='utf-8'))
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|']+['| '+' | '.join(map(str,row))+' |' for row in rows])
text=r'''# 第一问模型与基准求解结果

本结果采用用户明确授权的能耗补全假设及已有航段预处理数据。结果属于该确定性数学模型的求解，不代表题目未明确的能耗口径已获官方确认。所有工作假设需要用户核验。

## 1 输入核验与建模范围

核对原始DOCX、DEM、5份基础Excel、提交模板和地理说明的9个SHA256，均与预处理记录一致。原题未变，因此沿用已经核验的公式缺项结论；没有发现需要替换用户指定基准的新增规则。核对80箱汇总与逐箱数据一致，16节点坐标和海拔与原始表一致，重新检查720条机型航段时间与参数公式一致。未重复栅格化DEM，未修改D盘附件。

只研究O01→Si→O01。每个架次只交付一个服务区的货箱，去程满该架次装载量、返程空载。允许同一服务区多架次，也允许不同架次采用不同机型。不存在实体无人机、电池库存、充电、通信或物资时限约束；这些属于后续问题。

## 2 变量、参数和假设

| 符号 | 含义 | 类型及单位 | 来源 |
|---|---|---|---|
| i、g、b | 服务区、机型、货箱索引 | 离散索引 | 原始节点、机型及逐箱表 |
| w_b、v_b | 货箱质量、体积 | 已知参数，kg、m³ | 逐箱货箱清单 |
| Q_g、V_g | 机型载质量、装载体积上限 | 已知参数，kg、m³ | 运输无人机数据 |
| m_g、E_g、η_g | 含电池空载质量、可用能量、爬升效率 | 已知参数，kg、kWh、无量纲 | 运输无人机数据 |
| L_g^0、L_g^F | 空载、满载标准航程 | 已知参数，m | 运输无人机数据 |
| d_ij、h⁺_ij、h⁻_ij | 水平距离、爬升高度、下降高度 | 派生参数，m | 已核验航段表 |
| ρ | 返航安全余量 | 参数，0—1 | 基准取三类机型共同的20%；其他取情景值 |
| q*_{ig} | 最大安全载荷 | 连续计算结果，kg | 单调能量约束和额定载质量 |
| a_kb | 模式k是否包含货箱b | 0—1模式常数 | 枚举构造 |
| y_k | 模式k是否选用 | 逐箱形式为0—1决策变量 | 组批优化 |
| N、E、T | 架次数、总能耗、累计作业时间 | 优化指标，架次、kWh、s | 所选架次求和 |

实现时将同服务区内质量和体积相同的货箱合为等价类。模式用各等价类箱数表示，可选次数为非负整数；求解后再逐一分配原始货箱编号。本问没有物资类别和时限差异约束，因此该压缩不损失可行解或目标信息。

题目规定：货箱不可拆、每箱恰好交付一次；不得跨服务区组批；质量、体积及返航安全余量同时满足；下降不另加能耗；航程随载荷按3/2次幂关系变化。

工作假设，需要用户核验：

1. 标准航程对应整组可用能量，水平能耗按消耗比例折算；若标准航程已含安全储备，本标定需要修改。
2. 表中爬升效率解释为电能转为重力势能的效率，置于分母。
3. 不额外添加没有功率参数的准备、装载、交接悬停能耗。这可能低估实际飞行任务总耗电，结论仅适用于该基准。
4. 累计作业时间计准备、装载、去返飞行、基础交接和逐箱交接；不计排队、充电。它不是多机并行调度后的最晚完成时间。
5. 沿用预处理中的局部线性米制距离及节点表作业海拔。距离与WGS84地心弦长核查最大相对差约0.02670%；节点与DEM海拔差异已保留，未在本问重新改写。

## 3 模型表达

\[
L_g(q)=L_g^0-(L_g^0-L_g^F)(q/Q_g)^{3/2}.
\]

在明确的工作假设下，单点往返能耗为

\[
E_{ig}(q)=E_g\frac{d_{0i}}{L_g(q)}+
\frac{(m_g+q)9.80665h^+_{0i}}{\eta_g3.6\times10^6}+
E_g\frac{d_{i0}}{L_g^0}+
\frac{m_g9.80665h^+_{i0}}{\eta_g3.6\times10^6}.
\]

空载质量已含电池，不再重复加电池质量。返航货物质量为0；去返爬升高度各用对应航段。

最大安全载荷解为满足 `0≤q≤Q_g` 和 `E_ig(q)≤(1−ρ)E_g` 的最大q。先判断空载可行性，再判断额定满载；仅当能量约束限制时做80轮二分并保留可行侧。因为本附件L0>LF>0且爬升非负，E(q)单调递增，该过程覆盖整个可行区间。容量能力不含体积或特定货箱限制，这些在组批时另行检查。

为每个服务区枚举所有非空箱数组合及三类机型，过滤质量、体积和能量不可行的模式。每个模式k有箱数n_k、成本E_k和T_k：

\[
T_k=t_{g,0i}+t_{g,i0}+t_g^{准备}+n_kt_g^{装载}+t_g^{基础交接}+n_kt_g^{逐箱交接}.
\]

逐箱形式的组批约束为：

\[
\sum_{k:b\in k}y_k=1\quad(\forall b),\qquad y_k\in\{0,1\}.
\]

模式已经内含同服务区、不可拆、质量、体积和能源限制。等价类实现用模式箱数乘选用次数，等于各类库存箱数。

基准目标是 `lex min(N,E,T)`，能耗优先对比为 `lex min(E,N,T)`，时间优先为 `lex min(T,N,E)`。该排序是建模选择，不是题目指定的唯一权重，不使用任意加权和近似字典序。

## 4 求解方法和最优性范围

有限模式枚举之后，使用剩余各类箱数作为状态。空状态成本为零；对任意非空状态，枚举含第一个非空类至少一箱的所有可行模式，再递归求剩余状态，取字典序最小累计成本。每个合法分组中一定有一个模式包含这个类，故该锚定不会漏掉解，只减少重复排列。

模式枚举完整，所有转移完整，没有启发式剪枝、超时或提前终止；服务区之间没有耦合，目标都是可加的，各区字典序最优的和就是全局字典序最优。能耗和时间模式成本由双精度公式产生，DP用其十进制表示做Decimal累计和严格字典序比较，不先四舍五入。状态数及模式数见optimality_certificates.csv。

因此可称为**当前工作假设、给定几何和数值精度下的全局字典序最优**，不是现实物理系统或其他能耗解释下的全局最优。数值误差界见独立核验报告。

对第一目标另有独立下界：S001有154kg，S002和S003各81kg，最大机型一次最多80kg，三者至少各2架次；其余12区至少各1架次，因此总架次至少18。实际可行方案达到18，故第一目标不依赖DP也得到证明。

## 5 基准结果

'''
text+=f"基准安全余量20%，全部80箱交付，18架次（B型9次、C型9次、A型0次）。总能耗 **{b['energy_kWh']:.9f} kWh**，累计作业时间 **{b['operation_s']:.6f}秒（{b['operation_s']/3600:.6f}小时）**。最低返航SOC为 **{b['min_return_soc']*100:.6f}%**。这些是架次的机型选择，并非要求配置9架B型和9架C型实体机。\n\n"
text+='### 5.1 最大安全载荷（kg）\n\n'
capmap={(r['site'],r['model']):r for r in caps}
text+=table(['服务区','A型','B型','C型'],[[site]+[f"{float(capmap[site,g]['max_safe_payload_kg']):.6f}" for g in 'ABC'] for site in sorted({r['site'] for r in caps})])
text+='\n\n45项均空载往返可行；A型全部达到25kg额定值。B型在S008受能量约束，C型在S002、S003、S004、S008、S012受能量约束。完整未取整值、约束类型和能耗见safe_payloads_45.csv。\n\n### 5.2 基准架次摘要\n\n'
baseplans=[r for r in plans if r['scenario']=='baseline']
text+=table(['架次','服务区','机型','箱数','质量kg','体积m³','能耗kWh','作业秒'],[[r['sortie'],r['site'],r['model'],len(r['box_ids']),r['mass_kg'],f"{r['volume_m3']:.3f}",f"{r['energy_kWh']:.6f}",f"{r['operation_s']:.3f}"] for r in baseplans])
text+='\n\n逐箱编号见Q1_单点组批.csv，该文件9个字段名称与原模板完全一致。这里“往返时间（s）”明确填**去返纯飞行时间**；包括准备装载和交接的完整架次作业时间保存在baseline_details.csv的operation_s字段，用后者汇总本问时间目标。若提交方将模板“往返时间”解释为含地面作业的全周期，应按该说明改填operation_s，不应混用两个量。\n\n## 6 目标优先级对比\n\n'
text+=table(['优先级','架次','能耗kWh','累计作业秒'],[[r['priority'],r['sorties'],f"{r['energy_kWh']:.9f}",f"{r['operation_s']:.6f}"] for r in s[:3]])
de=b['energy_kWh']-alt['energy_kWh'];dt=alt['operation_s']-b['operation_s']
text+=f"\n\n能耗优先增加1架次，节省{de:.9f}kWh（{de/b['energy_kWh']*100:.4f}%），增加{dt:.6f}秒（{dt/60:.4f}分钟）的累计作业时间；时间优先在本数据上与基准指标相同。该对比说明极小能耗收益可能需要额外飞行及准备交接，并不意味着能耗与架次数永远同向变化。\n\n## 7 安全余量敏感性\n\n"
rows=[]
for r in [s[3],s[4],s[0],*s[5:10]]:
    rows.append([f"{r['rho']*100:.0f}%",r['sorties'] if r['sorties'] is not None else '整体不可行',f"{r['energy_kWh']:.6f}" if r['energy_kWh'] is not None else '—',f"{r['operation_s']:.3f}" if r['operation_s'] is not None else '—',r['infeasible_sites'] or '无'])
text+=table(['安全余量','最少架次','总能耗kWh','累计作业秒','不可行服务区'],rows)
text+='\n\n每个情景都重新筛选全部模式、计算45项载荷能力、执行组批DP。10%和15%的组批指标未变，不表示所有机型最大安全载荷都未变：离散货箱、体积及额定载质量可能使更大的连续能力暂不改变组批。完整情景载荷与不可运输单箱列表见CSV和summary.json。\n\n'
text+=f"关键阈值如下（采用共同安全余量，均为本模型数值）：\n\n- **{manifest['global_trip_threshold']*100:.7f}%**：保持18架次的最大安全余量，由S004的单架次任务限制。瓶颈DP枚举所有不超过基准架次数的分组，最大化最低返航SOC，因此不是只看当前方案的SOC。阈值下方与上方各1×10⁻⁷的安全余量均重新求解，得到18与19架次。\n- **27.0503919%**：S008保持单架次的最大安全余量；30%情景需要再拆分，合计20架次。\n- **{v['global_full_delivery_reserve_limit']*100:.7f}%**：全部交付的最大共同安全余量；超过时，S008的14kg饮用水即使单箱出航、选最有利机型C也不满足能量约束。因为本问可无限增加架次，且能耗随载荷递增，逐箱都可运既是全交付的必要条件，也是充分条件。\n\n"
text+='40%时S004有3个饮用水箱不可运输，S008的5箱均不可运输。S004还有3箱单箱可行，但求解器不将该区未完成的部分任务冒充完整方案。50%及60%的不可运输单箱分别为30箱、45箱。不可行情景不报告全任务总架次数、总能耗或总时间；solutions.json、model_counts及核验记录中的已解服务区数据仅作局部诊断。\n\n'
text+='## 8 独立验证与限制\n\n'
text+=f"独立检查程序不导入求解器代码，重新读取原始货箱和机型参数，使用原始节点坐标及已验证的DEM最高点重建高度和飞行时间，并以45位Decimal精度独立计算去程水平、去程爬升、返程水平和返程爬升能耗。12个方案/情景和540项载荷能力检查全部通过；最大架次能耗差为{v['max_energy_discrepancy_kWh']:.3e}kWh。详见独立核验报告.md。\n\n"
text+='本结论仍依赖已明示的能耗补全、未计悬停交接能耗和几何近似。连续载荷边界与阈值不应超出输入精度解释；实际使用接近阈值的方案时需提高几何和物理参数精度。若用于正式竞赛，应遵守赛事AI使用及成果提交规则，如实披露工作假设，不将本材料当作完整参赛论文。\n'
(p/'模型与求解报告.md').write_text(text,encoding='utf-8')
vr='# 第一问独立核验报告\n\n核验状态：PASS。检查程序verify_q1.py不调用求解器的能耗、时间、组批函数。\n\n'
vr+=table(['情景','已检查架次','已检查货箱','全部80箱交付','确认不可运输单箱','结果'],[[r['scenario'],r['checked_sorties'],r['checked_boxes'],'是' if r['full_delivery'] else '否，确认整体不可行',r['confirmed_untransportable_boxes'],r['status']] for r in v['scenarios']])
vr+=f"\n\n逐架次检查：编号存在、无重复、目的地正确、质量与体积、去返载荷、分项能耗、SOC、纯飞行与累计作业时间。可行情景必须80箱完整覆盖；不可行情景单独检查不可运输单箱证据，不要求伪造完整交付。540项最大载荷检查覆盖空载不可行、额定载荷绑定及能量边界；能量绑定时额外增加10⁻⁵kg应超过预算。\n\n最大能耗重算差：{v['max_energy_discrepancy_kWh']:.12e}kWh。质量容差10⁻⁹kg、体积10⁻¹²m³、能耗10⁻⁸kWh、时间10⁻⁷s、SOC 10⁻¹⁰。优化筛选未主动放宽能量约束，容量和体积以Decimal精确比较。\n\n独立架次下界：18，等于实际基准架次数。该下界证明最少架次；第二、第三目标的最优性来自完整模式动态规划，独立可行性检查本身不冒称重新证明所有目标。DEM沿线最高值沿用此前已交叉验证结果，未重复处理栅格。\n"
(p/'独立核验报告.md').write_text(vr,encoding='utf-8')
readme=r'''# 第一问成果与复算

先阅读模型与求解报告.md、独立核验报告.md。所有结果以用户授权的工作假设为前提，需要用户核验。

## 文件

- safe_payloads_45.csv：基准45项最大安全载荷。
- Q1_单点组批.csv：与原模板9个字段一致的18架次结果；CSV可用Excel打开，不是已填充的原始XLSX模板。
- baseline_details.csv：完整架次作业时间及基准明细。
- priority_and_sensitivity.csv、summary.json：目标对比及安全余量情景。
- safe_payloads_all_scenarios.csv：12个方案/情景共540项能力结果（含同余量的目标优先级对照）。
- solutions.json：所有方案的逐箱分配；不可行情景只保留已完整求解服务区的局部诊断。
- reserve_thresholds.csv：保持各区基准架次数的最大共同安全余量。
- single_box_reserve_limits.csv：每个货箱单独运输时的最优机型及极限余量。
- optimality_certificates.csv：各情景各区枚举模式数、访问状态数及求解状态。
- independent_energy_breakdown.csv、verification.json：独立计算的能耗分项、能量裕量及检查结果。
- run_manifest.json：参数、原始源哈希核验数量、预处理哈希及数值口径。

## 环境与命令

需要Python 3.10或更新版本及openpyxl；其他依赖为Python标准库。读取既有preflight文件，不需要另装数值优化器，不需联网下载数据。程序只读源文件；输出写入脚本所在目录或--out指定目录。

在本目录打开终端，若Python已安装并能导入openpyxl：

```powershell
python solve_q1.py --source 'D:研一比赛中文题目D题' --preflight '..preflight'
python verify_q1.py --source 'D:研一比赛中文题目D题' --preflight '..preflight'
python make_report.py
```

本次实际使用的Python：
`C:UsersASUS.cachecodex-runtimescodex-primary-runtimedependenciespythonpython.exe`

在PowerShell中可将上述python替换为 `& '该Python绝对路径'`。请不要将求解器输出管道接到提前退出的截断命令；如需保存日志，重定向到日志文件。

报告脚本读取自身目录中的求解结果。若使用--out指向别处，应把make_report.py放到该结果目录再执行。源文件变化导致哈希校验失败时，先更新预处理和审计记录，不应删除校验绕过。

所有CSV为UTF-8带BOM，保存未人为四舍五入的数值；报告表格仅用于阅读。数值比较采用未取整数据。该模型不优化时间窗、不调度实体无人机或电池，后续问题必须另建模型。
'''
(p/'README.md').write_text(readme,encoding='utf-8')
print('Reports written; baseline hours',b['operation_s']/3600)
