# 目录：optional-skills/finance/dcf-model

## 它负责什么

`optional-skills/finance/dcf-model` 是一个可选金融建模技能目录，用来指导 Hermes Agent 生成机构级 DCF 估值模型。它本身不是一个完整应用，也不是直接提供“一键生成模型”的业务服务，而是一组面向 Agent 的操作规范、质量约束、校验脚本和排障说明。核心产物是磁盘上的 `.xlsx` 文件，通常由 Agent 结合 `openpyxl`、`excel-author` 或相关 Excel 写作能力来创建。

这个技能覆盖的估值范围比较明确：收入预测、经营利润率假设、Unlevered FCF 构建、WACC 计算、终值计算、企业价值到股权价值桥接、Bear/Base/Bull 场景、以及底部敏感性分析表。它强调“模型必须可审计、可刷新、可调假设”，因此 `SKILL.md` 里反复要求公式优先，不能把 Python 预先算好的结果硬写进 Excel。允许硬编码的内容主要是历史输入、假设驱动项和市场数据；投影、折现、PV、敏感性单元格都应写成 Excel 公式。

这个目录的定位偏“方法论 + 交付检查”，尤其适合作为 Agent 创建 DCF Excel 模型时的操作手册。它还明确要求分阶段向用户确认：先确认原始输入，再确认收入预测，再确认 FCF，再确认 WACC，再确认终值和股权桥，最后再做敏感性表。也就是说，该技能并不鼓励 Agent 一口气闭门生成完整模型，而是把估值过程拆成可审查的连续节点。

## 直接子目录地图

这个目录结构很小，直接子目录只有一个：

`optional-skills/finance/dcf-model/scripts`

`scripts` 放置辅助脚本，目前关键文件是 `scripts/validate_dcf.py`。它用于校验生成后的 Excel DCF 模型，检查公式错误和常见估值逻辑问题。它不是模型生成器，而是交付前的质量检查工具。

目录根部还有几个关键文件：

`optional-skills/finance/dcf-model/SKILL.md` 是主入口和主要规范来源，包含技能元数据、建模步骤、公式约束、表结构要求、格式标准、敏感性分析写法和常见错误。

`optional-skills/finance/dcf-model/TROUBLESHOOTING.md` 是简短排障手册，面向 `#REF!`、`#DIV/0!`、`#VALUE!`、估值异常、场景选择器失效等常见问题。

`optional-skills/finance/dcf-model/requirements.txt` 声明运行辅助逻辑可能需要的 Python 依赖，目前包含 `openpyxl` 和 `requests`。根据当前片段推断，`openpyxl` 是主要依赖，`requests` 可能用于数据获取或后续扩展，但当前读取到的校验脚本主要只直接使用 `openpyxl`。

## 关键入口

第一入口是 `optional-skills/finance/dcf-model/SKILL.md`。它通过 frontmatter 声明技能名 `dcf-model`、标签、相关技能和支持平台。正文中最重要的是几个部分：`Critical Constraints - Read These First`、`DCF Process Workflow`、`correct_patterns`、`common_mistakes`、`Excel File Creation`、`Input Requirements`、`Excel Model Structure`。这些内容共同定义了 Agent 应该如何从输入数据走到 Excel 交付物。

第二入口是 `optional-skills/finance/dcf-model/scripts/validate_dcf.py`。脚本中核心类是 `DCFModelValidator`，核心方法是 `validate_all()`。它依次调用 `check_sheet_structure()`、`check_formula_errors()`、`check_dcf_logic()`，输出 JSON 风格的校验结果。文件底部的 `main()` 提供命令行入口，支持 `python validate_dcf.py <excel_file> [output.json]` 这种用法，并根据校验状态返回退出码。

第三入口是 `optional-skills/finance/dcf-model/TROUBLESHOOTING.md`。它不是执行入口，但对使用者理解失败模式很有帮助。它把错误大致分成公式错误、估值结果不合理、场景选择器不工作三类，和 `SKILL.md` 中的质量约束形成互补。

第四入口是 `optional-skills/finance/dcf-model/requirements.txt`。它说明这个技能的脚本侧依赖，不负责安装逻辑，只是给环境准备提供依据。

## 主流程位置

主流程主要写在 `SKILL.md` 的 `DCF Process Workflow` 中，可以理解为十步式 DCF 生成流程。

第一步是数据获取与验证。技能要求优先使用可用 MCP 数据源，其次使用用户提供数据，最后再通过搜索或抓取补足市场数据。关键检查项包括净债务或净现金、稀释股数、历史利润率、收入增长、税率合理性等。

第二步是历史分析，通常覆盖三到五年。这里需要整理收入增长、毛利率、EBIT margin、D&A、CapEx、NWC、ROIC 或 ROE 等指标，为后续假设提供依据。

第三步是收入预测。技能要求从最近实际收入出发，按年度增长率向前投影，并同时展示金额和增长率。Bear/Base/Bull 三场景通常分别代表保守、基准和乐观增长路径。

第四步是经营费用建模。重点是费用应基于收入而不是毛利计算，并体现经营杠杆。`SKILL.md` 特别点名 Sales & Marketing、R&D、G&A 等费用项要有独立逻辑。

第五步是 Free Cash Flow 构建。标准路径是 EBIT、税、NOPAT、D&A、CapEx、ΔNWC，最终得到 Unlevered FCF。这里强调公式顺序和工作资本的方向，避免现金流符号错置。

第六步是 WACC。技能采用 CAPM 计算股权成本，并结合税后债务成本和资本结构权重。特殊情况包括净现金公司、无债务公司、债务权重为负等。

第七步是折现。技能推荐 mid-year convention，折现期通常是 `0.5, 1.5, 2.5...`，PV 公式必须写在 Excel 中。

第八步是终值。首选 perpetuity growth method，并强调 terminal growth 必须小于 WACC。也可以使用 exit multiple method，但需要来自可比公司或交易倍数的依据。

第九步是 Enterprise Value 到 Equity Value 桥接。核心结构是 PV of FCFs 加 PV of Terminal Value 得到 EV，再扣除 Net Debt 或加上 Net Cash，除以稀释股数得到每股隐含价值。

第十步是敏感性分析。它要求在 DCF sheet 底部生成三个 5×5 或 7×7 的公式网格，包括 WACC vs Terminal Growth、Revenue Growth vs EBIT Margin、Beta vs Risk-Free Rate。这里明确禁止使用 Excel 的 Data Table 功能，也禁止留下占位文字或线性近似。每个单元格都要完整重算 DCF。

脚本侧主流程位于 `scripts/validate_dcf.py` 的 `DCFModelValidator.validate_all()`。该流程不会创建模型，只验证现有 Excel 文件：先看推荐 sheet 是否存在，再扫描所有 sheet 的公式错误，最后检查 DCF 特有逻辑，包括 terminal growth 是否小于 WACC、WACC 是否在合理范围、terminal value 占 EV 的比例是否异常。

## 推荐阅读顺序

建议先读 `optional-skills/finance/dcf-model/SKILL.md` 的开头元数据和 `Environment`，理解它依赖 headless `openpyxl`，并且会配合 `excel-author` 或 Excel 写作规范生成 `.xlsx`。

第二步读 `Critical Constraints - Read These First`。这里是整个目录的红线，包括公式不能硬编码、每阶段要用户确认、敏感性表必须全公式填满、硬编码输入必须有来源注释、行号布局要先规划、交付前必须重算。

第三步读 `DCF Process Workflow`。这部分是建模主线，从数据检索一直到敏感性分析，适合建立完整业务流程图。

第四步读 `correct_patterns` 和 `common_mistakes`。这里最能体现这个技能的“经验沉淀”：例如用 scenario block 加 consolidation column 管理 Bear/Base/Bull，而不是在每个投影公式里散落复杂 IF；敏感性表要用真实 DCF 重算公式，而不是近似。

第五步读 `Excel File Creation`、`Input Requirements`、`Excel Model Structure` 和格式规范。读到这里就能知道最终 Excel 应该有几个 sheet、颜色如何区分输入和公式、边框如何划分区域、数值格式如何展示。

第六步读 `scripts/validate_dcf.py`。重点看 `DCFModelValidator` 的几个检查函数，理解自动化校验的覆盖范围和盲区。

最后读 `TROUBLESHOOTING.md`。它适合作为修复清单，而不是第一遍学习材料。

## 常见误区

一个常见误区是把这个目录当成“DCF 生成代码”。实际不是。当前目录没有完整的模型生成脚本，核心生成逻辑是写在 `SKILL.md` 里的 Agent 操作规范。真正写 Excel 的过程需要由 Agent 根据这些规则调用 `openpyxl` 或相关 Excel 技能完成。

第二个误区是认为 `scripts/validate_dcf.py` 能替代 Excel 重算。它可以读取公式和值并扫描错误，但 `SKILL.md` 仍明确要求使用 `excel-author` 的 `recalc.py` 或同类机制触发 LibreOffice 重算。根据当前片段推断，`validate_dcf.py` 更像补充校验器，而不是唯一验收工具。

第三个误区是把敏感性分析做成 Excel Data Table。该技能明确反对这种方式，因为 Data Table 需要人工操作，无法通过 `openpyxl` 稳定自动生成。正确做法是在每个敏感性单元格写入完整公式。

第四个误区是先写公式再插入标题和分区。`SKILL.md` 多次强调要先规划 row positions，先写 header 和 labels，再写公式。否则 D&A、CapEx、FCF、终值等公式很容易引用错行，造成 `#REF!` 或更隐蔽的估值错误。

第五个误区是忽视硬编码输入的来源注释。该技能要求所有蓝色输入都要在创建时添加 comment，格式类似 `Source: [System/Document], [Date], [Reference]...`。这不是美化要求，而是审计要求。

第六个误区是把场景选择逻辑散落到每个投影公式中。`SKILL.md` 推荐 Bear/Base/Bull 分块展示，并使用 consolidation column 加 `INDEX` 统一拉取当前场景假设。这样模型更容易审阅，也更容易定位错误。

第七个误区是只看估值输出，不看估值结构。`scripts/validate_dcf.py` 专门检查 terminal growth 与 WACC、WACC 合理区间、terminal value 占 EV 比例，说明这个技能关注的不只是“算出一个每股价格”，还包括这个价格是否来自合理的财务结构。
