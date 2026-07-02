# 单细胞 ANN 检索系统

本项目是软件工程课程的单细胞相似细胞检索 Web 系统。系统围绕 `.h5ad` 单细胞数据构建，使用 `obsm/X_pca` 作为检索向量，使用 `obsm/X_umap` 作为二维可视化坐标，提供数据集管理、FAISS ANN 索引管理、条件 Top-K 检索、性能评估、UMAP 交互可视化和 AI 辅助分析。

## 当前状态

- 基础功能：已覆盖结项要求中的可运行系统、条件检索、实验评估、可视化展示、数据集管理和动态索引管理。
- 加分功能：支持 HNSW/IVF_FLAT 参数化索引、多数据集联合索引、向量直接检索、批量评测、RAG 风格 Top-K 结果 AI 分析、管理员监控。
- 测试状态：`python -m pytest tests\test_backend_api.py` 当前为 `21 passed, 2 skipped`；`npm run build` 通过。
- 已知风险：当前本机 conda 环境中 FAISS IVF `train()` 在测试进程里会崩溃，建议演示前使用已有索引、HNSW 或修复/替换 FAISS 包。默认 Python 环境没有 FAISS 时，相关测试会被跳过。

## 技术栈

- 后端：Flask、h5py、NumPy、FAISS、pytest。
- 前端：React、Vite、Axios、ECharts、Lucide React。
- 存储：`data/registry.json`、`runtime/users.json`、`indexes/*.faiss`、`indexes/*.meta.json`、`logs/*.jsonl`。

## 主要功能

- 用户与权限：注册、登录、退出、Bearer Token、角色权限、管理员修改角色、启用/禁用和删除用户。
- 数据集管理：扫描 `data/*.h5ad` 和 `data/datasets/*.h5ad`，上传到 `data/uploads/`，校验、加载、激活、下线、恢复、删除和元信息维护。
- 索引管理：构建 IVF_FLAT 或 HNSW，支持 L2/Cosine/IP，支持联合索引和独立索引，支持保存、加载、切换和删除索引。
- 条件检索：按 `cell_id` 或直接输入向量检索，支持 Top-K、数据集限定和 `cell_type`、`disease`、`AgeGroup`、`tissue` 条件过滤。
- 实验评估：返回查询耗时，支持 ANN vs Exact Recall/延迟/speedup，对批量查询统计 QPS、Avg、P50、P99，并写入评测日志。
- 可视化：UMAP 散点图、元数据着色、条件过滤、Top-K 高亮和连线、点击点回填查询细胞、基因表达叠加、CSV 导出。
- AI 分析：把 Top-K 检索结果和自然语言问题发送给配置的 LLM Provider，生成邻域解释报告，支持重试、缓存和日志。
- 管理监控：管理员可查看系统状态、FAISS 状态、数据集/索引状态、查询日志和评测日志。

## 权限模型

- 未登录：可浏览首页、数据集列表、索引状态和公开可视化，不可执行写操作或检索。
- 普通用户：可执行检索、精确检索、对比评估、批量查询和可视化查看。
- 研究人员：可加载数据集、构建/切换/加载/删除索引、执行检索和评估。
- 数据维护者：可扫描、上传、校验、维护数据集，也可加载数据集、构建索引和检索。
- 管理员：拥有全部功能，并可管理用户与查看监控日志。

## 环境

```powershell
conda env create -f environment.yml
conda activate single-cell-ann
python -c "import faiss; print(faiss.__version__)"
```

如果 `faiss-gpu` 在本机不稳定，可改用 `faiss-cpu` 或优先演示 HNSW/已有索引。后端健康检查会返回当前 FAISS 版本、GPU 数量和运行模式。

## 启动

后端：

```powershell
conda activate single-cell-ann
python -m backend.app
```

也可以使用本地脚本：

```powershell
.\start_backend_local.ps1
.\stop_backend.ps1
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

默认后端地址为 `http://127.0.0.1:5000`，前端通常为 `http://127.0.0.1:5173`。

## AI 配置

复制 `.env.example` 为 `.env` 并按需修改：

```bash
SCANN_LLM_PROVIDER=siliconflow
SCANN_LLM_API_KEY=sk-...
SCANN_LLM_MODEL=Qwen/Qwen3-8B
```

也支持 OpenAI 或本地 OpenAI-compatible 服务：

```bash
SCANN_LLM_PROVIDER=openai
SCANN_LLM_API_KEY=sk-...
SCANN_LLM_MODEL=gpt-4.1-mini

SCANN_LLM_PROVIDER=local
SCANN_LLM_API_URL=http://127.0.0.1:11434/v1/chat/completions
SCANN_LLM_MODEL=qwen3:8b
```

常用参数包括 `SCANN_LLM_ENABLE_THINKING`、`SCANN_LLM_TIMEOUT_SECONDS`、`SCANN_LLM_MAX_TOKENS`、`SCANN_LLM_MAX_HITS_FOR_PROMPT`、`SCANN_LLM_CACHE_TTL_SECONDS`。

## 数据准备

默认数据：

```text
data/liver.h5ad
```

更多数据集可放入：

```text
data/datasets/
```

网页上传文件保存到：

```text
data/uploads/
```

多数据集联合索引要求各数据集 PCA 向量维度一致。

## 推荐演示流程

1. 登录管理员或研究人员账号。
2. 在“数据集”页扫描本地数据，校验 `liver` 数据集。
3. 加载数据集，检查细胞数、向量维度和样例 Cell ID。
4. 在“索引”页加载已有 `liver_ivf_flat` 索引，或构建 HNSW 索引。
5. 在“分析工作台”输入或点击 UMAP 点回填 Cell ID，执行 Top-K 检索。
6. 添加 `cell_type` 等条件过滤，展示条件 Top-K 检索。
7. 开启 ANN vs Exact 对比，展示 Recall、延迟和 speedup。
8. 执行批量查询，展示 QPS、P50、P99。
9. 切换到“AI 辅助分析”，输入自然语言问题生成解释报告。
10. 在“系统管理”查看查询日志、评测日志和系统状态。

## API 摘要

认证：

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

数据集：

- `GET /api/datasets`
- `GET /api/datasets/current`
- `GET /api/datasets/<dataset_id>`
- `POST /api/datasets/scan`
- `POST /api/datasets/upload`
- `POST /api/datasets/validate`
- `POST /api/datasets/load`
- `PATCH /api/datasets/<dataset_id>/metadata`
- `POST /api/datasets/<dataset_id>/activate`
- `POST /api/datasets/<dataset_id>/offline`
- `POST /api/datasets/<dataset_id>/restore`
- `DELETE /api/datasets/<dataset_id>`

索引：

- `POST /api/index/build`
- `GET /api/index/status`
- `POST /api/index/switch`
- `POST /api/index/load`
- `DELETE /api/index/<index_id>`

检索与评估：

- `POST /api/search`
- `POST /api/search/vector`
- `POST /api/search/exact`
- `POST /api/search/compare`
- `POST /api/search/batch`
- `POST /api/search/analyze`
- `GET /api/demo/search`

可视化：

- `GET /api/visualization/cells`
- `GET /api/visualization/options`

管理员：

- `GET /api/admin/users`
- `PUT /api/admin/users/<username>/role`
- `PUT /api/admin/users/<username>/status`
- `DELETE /api/admin/users/<username>`
- `GET /api/admin/logs/query`
- `GET /api/admin/logs/benchmark`
- `GET /api/admin/system/status`

## 验证

```powershell
python -m pytest tests\test_backend_api.py
cd frontend
npm run build
```

当前已验证前端生产构建通过。后端默认 Python 环境测试结果为 `21 passed, 2 skipped`，跳过项为 FAISS 不可用时的索引集成测试。若使用 conda 环境进行 IVF 构建测试，请先确认 FAISS IVF `train()` 在本机不会崩溃。
