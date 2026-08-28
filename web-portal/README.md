# Web Portal · 多板块量化统一前端

Vue 3 + Vite + TypeScript + Naive UI + ECharts。每个量化板块在 `src/views/<板块>/` 下拥有独立页面区，左侧导航天然支持后续板块扩展。

## 运行

前置：仓库根的网关已在 `127.0.0.1:8600` 运行（见 `../quant-gateway/README.md`）；本机需 Node ≥ 18。

```powershell
npm install          # 首次
npm run dev          # http://localhost:5173
```

开发代理：`/api/* → http://127.0.0.1:8600`（见 `vite.config.ts`）。

## 目录

```
src/
├── layouts 布局（侧边栏板块菜单）
├── views/
│   ├── OverviewView.vue        板块总览
│   └── a-share/                A 股板块页面区
├── services/api.ts             后端接口封装（同 /api 网关契约）
└── types.ts                    与 Pydantic/JSON 结构对应的 TS 类型
```

新增板块：加一个 `views/<name>/` 目录 + 一条路由 + 侧边栏一个菜单项。
