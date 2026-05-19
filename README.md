# 单细胞 ANN 检索系统

本项目是软件工程课程的单细胞相似细胞检索 Web 系统。当前版本已从单一 `data/liver.h5ad` 演示链路升级为多模块工作台，支持数据集库、网页上传、单/多数据集索引构建、Top-K 相似细胞检索、UMAP 可视化和简单用户登录。

## 已实现功能

- 数据管理模块：扫描 `data/*.h5ad`、`data/datasets/*.h5ad`，上传 `.h5ad` 到 `data/uploads/`，校验 `X_pca`、`X_umap`、`obs/_index`。
- 索引构建模块：基于 FAISS IVF_FLAT 构建 ANN 索引，支持联合索引和独立索引，GPU 可用时优先使用 GPU。
- 查询检索模块：按 `cell_id` 执行 Top-K 相似细胞搜索，返回距离、相似度、细胞类型、疾病、年龄组、组织、UMAP 坐标和所属数据集。
- 可视化展示模块：展示 UMAP 抽样点，高亮查询细胞和 Top-K 命中结果。
- 用户信息模块：本地演示级注册、登录、退出和当前用户显示。

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

前端：

```powershell
cd frontend
npm install
npm run dev
```

默认后端地址是 `http://127.0.0.1:5000`，前端通常是 `http://127.0.0.1:5173`。

## 页面流程

1. 在“用户信息模块”注册或登录演示账号。
2. 在“数据管理模块”点击“扫描本地”，或上传 `.h5ad` 文件。
3. 选择一个或多个数据集，点击“校验选中”。
4. 在“索引构建模块”选择“联合索引”或“独立索引”，点击“构建索引”。
5. 在“查询检索模块”选择查询数据集，输入 `cell_id` 和 Top-K，点击“查询”。
6. 在结果表格和“可视化展示模块”查看相似细胞和 UMAP 高亮。

## API 摘要

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
- `GET /api/visualization/cells?limit=5000`

## 验证

```powershell
conda activate single-cell-ann
python -m pytest tests
python tests/smoke_midterm.py
cd frontend
npm run build
```

当前测试覆盖用户登录、数据集扫描与校验、联合/独立索引、数据集感知 Top-K 检索和前端构建。
