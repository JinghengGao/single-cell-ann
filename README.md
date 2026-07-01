# 单细胞 ANN 检索系统

本项目是软件工程课程的单细胞相似细胞检索 Web 系统。当前版本已从单一 `data/liver.h5ad` 演示链路升级为多模块工作台，支持数据集库、网页上传、单/多数据集索引构建、Top-K 相似细胞检索、UMAP 可视化和简单用户登录。

## 已实现功能

- 数据管理模块：扫描 `data/*.h5ad`、`data/datasets/*.h5ad`，上传 `.h5ad` 到 `data/uploads/`，校验 `X_pca`、`X_umap`、`obs/_index`。
- 索引构建模块：基于 FAISS IVF_FLAT 构建 ANN 索引，支持联合索引和独立索引，GPU 可用时优先使用 GPU。
- 查询检索模块：按 `cell_id` 执行 Top-K 相似细胞搜索，返回距离、相似度、细胞类型、疾病、年龄组、组织、UMAP 坐标和所属数据集。
- 大模型辅助分析模块：可将 Top-K 检索结果发送到后端配置的 LLM Provider，默认使用硅基流动 `Qwen/Qwen3-8B`，也支持 OpenAI 兼容接口和本地 vLLM/Ollama 服务。
- 可视化展示模块：升级为 UMAP 分析工作台，支持元信息着色、过滤、统计摘要、基因表达叠加、Top-K 连线、点击选点和 CSV 导出。
- 用户信息模块：未登录可预览主页，登录后按身份开放操作；支持本地演示级注册、登录、退出和当前用户显示。

## 权限模型

- 未登录：可以预览主页、数据集列表、索引状态和模块布局，但不能执行数据导入、校验、加载、建索引或查询。
- 普通用户：可以执行 Top-K 查询和查看可视化。
- 研究人员：可以加载数据集、构建/切换索引、查询和查看可视化。
- 数据维护者：可以扫描、上传、校验数据集，也可以加载数据集、构建索引和查询。
- 管理员：拥有全部演示权限。

## 环境

```powershell
conda env create -f environment.yml
conda activate single-cell-ann
python -c "import faiss; print(faiss.__version__)"
```

如果 `faiss-gpu` 在本机无法求解，可将 `environment.yml` 中的 `faiss-gpu` 替换为 `faiss-cpu` 后重新创建环境。后端会自动报告当前 FAISS 运行模式。

## 数据

默认演示数据：

```text
data/liver.h5ad
```

可以把更多 `.h5ad` 文件放到：

```text
data/datasets/
```

也可以在前端“数据管理模块”中上传。大数据文件、上传文件、索引、日志和运行状态不会提交到 Git。

## 运行

后端：

```powershell
conda activate single-cell-ann
python -m backend.app
```

如需启用 AI 辅助分析，先复制并编辑环境变量文件：

```bash
cp .env.example .env
# 编辑 .env，填入你的 SCANN_LLM_API_KEY
```

配置项说明见 `.env.example` 中的注释。后端启动时会自动读取项目根目录下的 `.env` 文件。常用 Provider 配置示例：

```bash
# 默认硅基流动
SCANN_LLM_PROVIDER=siliconflow
SCANN_LLM_API_KEY=sk-...
SCANN_LLM_MODEL=Qwen/Qwen3-8B

# OpenAI Chat Completions
SCANN_LLM_PROVIDER=openai
SCANN_LLM_API_KEY=sk-...
SCANN_LLM_MODEL=gpt-4.1-mini

# 本地 OpenAI-compatible 服务，如 Ollama/vLLM
SCANN_LLM_PROVIDER=local
SCANN_LLM_API_URL=http://127.0.0.1:11434/v1/chat/completions
SCANN_LLM_MODEL=qwen3:8b
```

AI 分析会对可重试错误进行指数退避重试，并对“相同检索结果 + 相同问题 + 相同模型配置”的请求做短期内存缓存，减少重复 Token 消耗。可通过 `SCANN_LLM_MAX_HITS_FOR_PROMPT` 控制纳入 Prompt 的命中数量，通过 `SCANN_LLM_CACHE_TTL_SECONDS` 调整缓存时间。

进入工作区后，可在左侧导航打开“AI 辅助分析”大屏，临时开启或关闭 Qwen3 思考模式；开启后分析更充分但响应会更慢。大屏会复用检索后的 UMAP 空间图展示查询细胞与 Top-K 命中位置关系，同时把系统提示词增强后的分析结构渲染为 SVG 层次图，并结合距离统计、细胞组成、查询邻域网络和 AI Markdown 报告形成完整可视化视图。

前端：

```powershell
cd frontend
npm install
npm run dev
```

默认后端地址是 `http://127.0.0.1:5000`，前端通常是 `http://127.0.0.1:5173`。

## 页面流程

1. 未登录时可以先预览主页；需要操作时在“用户信息模块”注册或登录演示账号。
2. 数据维护者或管理员在“数据管理模块”点击“扫描本地”，或上传 `.h5ad` 文件。
3. 选择一个或多个数据集，点击“校验选中”。
4. 在“索引构建模块”选择“联合索引”或“独立索引”，点击“构建索引”。
5. 在“查询检索模块”选择查询数据集，输入 `cell_id` 和 Top-K，点击“查询”。
6. 在结果表格和“可视化展示模块”查看相似细胞和 UMAP 高亮。
7. 在可视化工具条中切换着色字段、过滤细胞类型/疾病/年龄/组织，输入基因名如 `ALB` 后点击“基因上色”查看表达量叠加。

## API 摘要

除健康检查、登录注册、数据集列表、当前状态等公开接口外，数据管理、索引构建和查询接口需要携带登录后的 Bearer Token。

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/datasets`
- `POST /api/datasets/scan`
- `POST /api/datasets/upload`
- `POST /api/datasets/validate`
- `POST /api/datasets/load`
- `GET /api/datasets/current`
- `POST /api/index/build`
- `POST /api/index/switch`
- `GET /api/index/status`
- `POST /api/search`
- `POST /api/search/analyze`
- `GET /api/visualization/cells?limit=5000`
- `GET /api/visualization/options?dataset_ids=liver&gene_query=ALB`

## 验证

```powershell
conda activate single-cell-ann
python -m pytest tests
python tests/smoke_midterm.py
cd frontend
npm run build
```

当前测试覆盖用户登录、数据集扫描与校验、联合/独立索引、数据集感知 Top-K 检索和前端构建。
