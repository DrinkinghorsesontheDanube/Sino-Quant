# Quant Gateway

多板块量化门户的统一 API 网关：把每个量化模块自带的 FastAPI 路由聚合到一个进程、一个端口（默认 `127.0.0.1:8600`）。

代码位于仓库根的 `src/quant_gateway/`（作为根包的一个子包分发，`pip install -e ".[api]"` 即覆盖网关依赖），本目录只保留说明文档。

当前挂载：

| 前缀 | 模块 |
|---|---|
| `/api/a-share` | A 股量化（`src/ashare_quant`） |

新增模块三步走：模块包内实现 `create_router()` → 在 `src/quant_gateway/app.py` 的 `MOUNTS` 里加一行 → 网关重启。

## 安装与运行

```powershell
cd <Sino-Quant 仓库根>
pip install -e ".[api]"
.\.venv\Scripts\python.exe -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600
```

验证：浏览器打开 <http://127.0.0.1:8600/docs>，或访问 `/health`。

## 接口一览

```
GET  /api/a-share/reports                 报告列表（含运行参数）
GET  /api/a-share/runs/{run_id}/summary   指标 + 净值/回撤曲线
GET  /api/a-share/runs/{run_id}/trades    成交明细
POST /api/a-share/backtests               触发回测（后台任务，返回 job_id）
GET  /api/a-share/jobs/{job_id}           查询任务状态
```

`ASHARE_REPORTS_DIR` 环境变量可覆盖报告目录（默认使用仓库根 `reports/`）。
