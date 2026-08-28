# Sino Quant · A 股量化研究与回测

单仓 monorepo，包含三个部分：A 股日线研究回测库（Python）、统一 API 网关（FastAPI）、统一前端（Vue 3）。第一阶段只做 A 股日线研究与回测，不包含真实账户或自动下单。

## 仓库结构

```text
Sino Quant/
├── config/                 # 可复制的策略配置（YAML）
├── data/                   # 本地数据缓存，已被 Git 忽略
│   ├── raw/                #   数据源原始响应缓存
│   └── processed/          #   对齐后的开收盘面板
├── notebooks/              # 临时研究笔记
├── reports/                # 回测报告（每次运行一个目录，含 meta.json），已被 Git 忽略
├── scripts/                # 可直接执行的入口（CLI）
├── src/
│   ├── ashare_quant/       # A 股业务代码：数据、策略、回测引擎、指标、管线、API
│   └── quant_gateway/      # FastAPI 网关，聚合各量化模块的路由
├── tests/                  # 自动化测试
└── web-portal/             # Vue 3 前端（Naive UI + ECharts）
```

## 回测能力

- 沪深 A 股日线数据（AkShare/腾讯财经前复权）与本地缓存
- 动量选股基线策略（top-N 等权，周/月调仓）
- A 股交易约束：T+1、100 股整数倍、佣金、卖出印花税与滑点、现金不为负
- **交易日历与可交易性**：保留完整联合日历，停牌日 forward-fill 估值、禁止交易；开盘涨停禁止买入、跌停禁止卖出（按板块涨跌幅：主板 10%、创业板/科创板 20%、北交所 30%）
- 回测净值、年化收益、最大回撤、夏普率与年化换手率
- CLI 与 Web 触发的回测走**同一条管线**（`src/ashare_quant/pipeline.py`），产物完全一致；每次运行写入独立目录并记录参数、股票池、费率与 git commit（`meta.json`）

## 快速开始

网关直接托管前端页面，一条命令启动整个门户（API、`/docs`、网页界面同端口）：

```powershell
.\.venv\Scripts\python -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600
```

打开 <http://127.0.0.1:8600> 即可使用。

## 安装与运行（手动方式）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"          # 回测库 + 测试工具
python scripts/run_example.py    # 合成数据冒烟测试
pytest
```

真实数据验证（A 股前复权日线）：

```powershell
pip install -e ".[data]"
python scripts/run_real_backtest.py --start 20240102
```

策略与回测参数从 `config/momentum_weekly.example.yaml` 读取（可用 `--config` 指定其他文件）；`--end` 默认取当天。默认股票池为 15 只大型、流动性较好的 A 股（定义在 `pipeline.py` 的 `DEFAULT_UNIVERSE`，CLI 与 Web 共用）；原始响应缓存到 `data/raw/`，对齐后的开收盘面板写入 `data/processed/`，报告写入 `reports/{run_id}/`。文件使用 UTF-8 CSV，避免运行环境的 Parquet 二进制依赖差异。不会使用合成数据替代下载失败的真实数据。

## Web 门户（手动开发模式）

前端改代码时才需要这一节：`cd web-portal && npm run dev`（`http://localhost:5173`，`/api` 自动代理到 8600）；改完后 `npm run build` 让一键门户用上新页面。日常使用请直接双击 `启动门户.bat`。

接口一览见 `quant-gateway/README.md`。报告为只读查询；也支持从网页触发回测（后台任务轮询）。新增量化模块（如港股）三步走：模块内实现 `create_router()` → 网关 `MOUNTS` 加一行 → 前端加一个 `views/<板块>/` 目录。

## 重要限制

本项目是研究工具，回测结果不代表未来收益。当前数据层已覆盖停牌与涨跌停的一阶近似，但实盘前还必须补全：ST/退市风险警示的窄幅涨跌停（5%）、分红送转的除权除息现金流、新股上市与可交易性校验、以及盘中流动性约束。

## 路线图

1. **数据可信**（当前基线）：完整日历、停牌/涨跌停蒙版、带元数据的报告 ✅
2. **策略框架**：多策略注册与对比、参数扫描、基准对比（沪深300）
3. **数据增强**：复权因子本地化、ST/退市标注、指数与行业数据
4. **运维健壮性**：任务状态落盘、锁文件（uv.lock）、报告清理策略
