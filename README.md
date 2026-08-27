# A 股量化研究与回测

这是一个独立于父目录既有前端项目的 Python 项目。第一阶段只做 A 股日线研究与回测，不包含真实账户或自动下单。

## 第一版范围

- 沪深 A 股日线数据与本地缓存（数据下载接口待接入）
- 动量选股基线策略
- 每周/月调仓的长仓回测
- A 股交易约束：T+1、100 股整数倍、佣金、卖出印花税与滑点
- 回测净值、年化收益、最大回撤、夏普率与年化换手率

## 目录说明

```text
a_share_quant/
├── config/                 # 可复制的策略配置
├── data/                   # 本地数据，已被 Git 忽略
├── notebooks/              # 临时研究笔记
├── scripts/                # 可直接执行的入口
├── src/ashare_quant/       # 业务代码
└── tests/                  # 自动化测试
```

## 安装与运行

在本目录中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/run_example.py
pytest
```

示例使用合成数据，确保在没有数据服务 Token 时仍能验证回测闭环。

## 真实数据验证

安装数据依赖后可运行公开的 AkShare/腾讯财经前复权日线验证：

```powershell
pip install -e ".[data]"
python scripts/run_real_backtest.py --start 20240102
```

策略与回测参数从 `config/momentum_weekly.example.yaml` 读取（可用 `--config` 指定其他文件）；`--end` 默认取当天。默认股票池为 15 只大型、流动性较好的 A 股，代码固定在入口中以保证可复现；原始响应缓存到 `data/raw/`，对齐后的开收盘面板写入 `data/processed/`，净值、成交和指标写入 `reports/`。文件使用 UTF-8 CSV，避免运行环境的 Parquet 二进制依赖差异。不会使用合成数据替代下载失败的真实数据。

## 重要限制

本项目是研究工具，回测结果不代表未来收益。实盘前还必须补全停牌、涨跌停、复权、退市、ST、新股、分红配股及可交易性等数据校验。

## Web API（可选扩展）

本仓库自带只读 HTTP API 层：`pip install -e ".[api]"` 后由兄弟项目 `../quant-gateway` 聚合暴露（默认 `127.0.0.1:8600`，前缀 `/api/a-share`），配套统一前端在 `../web-portal`。详见 gateway / portal 各自的 README。
