# 第一问成果与复算

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
