# Quant Gateway

多板块量化门户的统一 API 网关：把每个量化模块自带的 FastAPI 路由聚合到一个进程、一个端口（默认 `127.0.0.1:8600`）。

当前挂载：

| 前缀 | 模块 |
|---|---|
| `/api/a-share` | A 股量化（`../a_share_quant`） |

新增模块三步走：模块包内实现 `create_router()` → 在 `src/quant_gateway/app.py` 的 `MOUNTS` 里加一行 → 网关重启。

## 安装与运行

单仓环境（推荐）：直接用仓库根目录的 `.venv`，网关以源码经 `PYTHONPATH` 引入：

```powershell
cd <Sino-Quant 仓库根>
$env:PYTHONPATH = "$PWD\quant-gateway\src"
.\.venv\Scripts\python.exe -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600
```

独立 venv 方式：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".." -e "."   # 根包提供 ashare_quant 与 [api] 扩展（需含 fastapi/uvicorn）
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m uvicorn quant_gateway.app:app --host 127.0.0.1 --port 8600
```

验证：浏览器打开 <http://127.0.0.1:8600/docs>，或访问 `/health`。

## 接口一览（V1 只读）

```
GET /api/a-share/reports                 报告列表
GET /api/a-share/runs/{run_id}/summary   指标 + 净值/回撤曲线
GET /api/a-share/runs/{run_id}/trades    成交明细
```

`ASHARE_REPORTS_DIR` 环境变量可覆盖报告目录（默认使用 a_share_quant 项目内 `reports/`）。
