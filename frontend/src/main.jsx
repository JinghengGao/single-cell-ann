import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { GridComponent, TooltipComponent } from "echarts/components";
import { use as useEcharts, init as initEcharts } from "echarts/core";
import { ScatterChart } from "echarts/charts";
import { CanvasRenderer } from "echarts/renderers";
import {
  Activity,
  AlertCircle,
  Database,
  GitBranch,
  LoaderCircle,
  LogIn,
  LogOut,
  Play,
  RefreshCw,
  Search,
  Upload,
  User,
} from "lucide-react";

import "./styles.css";
import {
  buildIndex,
  getCurrentDataset,
  getCurrentUser,
  getHealth,
  getIndexStatus,
  getVisualizationCells,
  listDatasets,
  loadDataset,
  loginUser,
  logoutUser,
  registerUser,
  scanDatasets,
  searchCells,
  switchIndex,
  uploadDataset,
  validateDatasets,
} from "./api/client";

useEcharts([GridComponent, TooltipComponent, ScatterChart, CanvasRenderer]);

const palette = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2", "#be123c", "#4d7c0f"];

const ROLE_LABELS = {
  normal_user: "普通用户",
  researcher: "研究人员",
  data_manager: "数据维护者",
  admin: "管理员",
};

const ROLE_PERMISSIONS = {
  normal_user: { search: true, visualize: true },
  researcher: { loadDataset: true, buildIndex: true, switchIndex: true, search: true, visualize: true },
  data_manager: {
    manageDatasets: true,
    loadDataset: true,
    buildIndex: true,
    switchIndex: true,
    search: true,
    visualize: true,
  },
  admin: {
    manageDatasets: true,
    loadDataset: true,
    buildIndex: true,
    switchIndex: true,
    search: true,
    visualize: true,
  },
};

function getErrorMessage(error) {
  return error?.response?.data?.message || error?.response?.data?.error || error?.message || "请求失败";
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "-";
  return Number(value).toLocaleString("zh-CN");
}

function permissionFor(role, key) {
  return Boolean(ROLE_PERMISSIONS[role]?.[key]);
}

function StatusBadge({ value, tone = "neutral" }) {
  return <span className={`status-badge ${tone}`}>{value || "-"}</span>;
}

function ModulePanel({ title, icon, children, actions, className = "" }) {
  return (
    <section className={`module-panel ${className}`}>
      <div className="panel-heading">
        <div className="heading-title">
          {icon}
          <h2>{title}</h2>
        </div>
        {actions ? <div className="heading-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

function StatGrid({ rows }) {
  return (
    <dl className="status-grid">
      {rows.map((row) => (
        <React.Fragment key={row.label}>
          <dt>{row.label}</dt>
          <dd>{row.value ?? "-"}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function UmapChart({ points, queryCell, hits }) {
  const ref = useRef(null);
  const hitKeys = useMemo(() => new Set((hits || []).map((hit) => `${hit.dataset_id}:${hit.cell_id}`)), [hits]);

  useEffect(() => {
    if (!ref.current) return;
    const chart = initEcharts(ref.current);
    const colorByDataset = new Map();
    const data = (points || []).map((point) => {
      if (!colorByDataset.has(point.dataset_id)) {
        colorByDataset.set(point.dataset_id, palette[colorByDataset.size % palette.length]);
      }
      return {
        value: [point.x, point.y],
        name: point.cell_id,
        dataset_id: point.dataset_id,
        dataset_name: point.dataset_name,
        cell_type: point.cell_type,
        itemStyle: {
          color: colorByDataset.get(point.dataset_id),
          opacity: hitKeys.has(`${point.dataset_id}:${point.cell_id}`) ? 0.95 : 0.45,
        },
      };
    });

    const hitData = (hits || [])
      .filter((hit) => hit.umap)
      .map((hit) => ({
        value: hit.umap,
        name: hit.cell_id,
        dataset_id: hit.dataset_id,
        dataset_name: hit.dataset_name,
        cell_type: hit.cell_type,
      }));

    const queryData = queryCell?.umap
      ? [
          {
            value: queryCell.umap,
            name: queryCell.cell_id,
            dataset_id: queryCell.dataset_id,
            dataset_name: queryCell.dataset_name,
            cell_type: queryCell.cell_type,
          },
        ]
      : [];

    chart.setOption({
      animation: false,
      grid: { left: 8, right: 8, top: 8, bottom: 8 },
      tooltip: {
        trigger: "item",
        formatter: (params) => {
          const item = params.data || {};
          return `${item.name}<br/>${item.dataset_name || item.dataset_id || "-"}<br/>${item.cell_type || "-"}`;
        },
      },
      xAxis: { type: "value", show: false },
      yAxis: { type: "value", show: false },
      series: [
        { name: "cells", type: "scatter", symbolSize: 5, data },
        {
          name: "top-k",
          type: "scatter",
          symbolSize: 13,
          data: hitData,
          itemStyle: { color: "#f97316", borderColor: "#7c2d12", borderWidth: 1.5 },
          z: 3,
        },
        {
          name: "query",
          type: "scatter",
          symbol: "diamond",
          symbolSize: 18,
          data: queryData,
          itemStyle: { color: "#111827", borderColor: "#ffffff", borderWidth: 2 },
          z: 4,
        },
      ],
    });

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [points, queryCell, hits, hitKeys]);

  if (!points?.length) {
    return <div className="empty-plot">未加载 UMAP 点</div>;
  }

  return <div ref={ref} className="chart" />;
}

function App() {
  const [health, setHealth] = useState(null);
  const [auth, setAuth] = useState({ authenticated: false, user: null });
  const [datasets, setDatasets] = useState([]);
  const [datasetSummary, setDatasetSummary] = useState(null);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState([]);
  const [indexStatus, setIndexStatus] = useState(null);
  const [selectedIndexId, setSelectedIndexId] = useState("");
  const [indexMode, setIndexMode] = useState("combined");
  const [nlist, setNlist] = useState(256);
  const [nprobe, setNprobe] = useState(16);
  const [visPoints, setVisPoints] = useState([]);
  const [queryCellId, setQueryCellId] = useState("");
  const [queryDatasetId, setQueryDatasetId] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchResult, setSearchResult] = useState(null);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ username: "admin_user", password: "secret123", role: "admin" });
  const [uploadFile, setUploadFile] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const role = auth.user?.role;
  const canManageDatasets = permissionFor(role, "manageDatasets");
  const canLoadDataset = permissionFor(role, "loadDataset");
  const canBuildIndex = permissionFor(role, "buildIndex");
  const canSwitchIndex = permissionFor(role, "switchIndex");
  const canSearch = permissionFor(role, "search");
  const canVisualize = permissionFor(role, "visualize");

  const selectedDatasets = useMemo(
    () => datasets.filter((dataset) => selectedDatasetIds.includes(dataset.dataset_id)),
    [datasets, selectedDatasetIds],
  );

  const indexOptions = indexStatus?.indexes || [];
  const activeIndex = indexOptions.find((item) => item.index_id === (selectedIndexId || indexStatus?.active_index_id)) || indexStatus;

  async function loadWorkspace() {
    const [datasetList, currentDataset, indexData] = await Promise.all([listDatasets(), getCurrentDataset(), getIndexStatus()]);
    const nextDatasets = datasetList.datasets || [];
    setDatasets(nextDatasets);
    setDatasetSummary(currentDataset);
    setIndexStatus(indexData);
    setSelectedIndexId(indexData.active_index_id || indexData.index_id || "");

    const nextSelected = selectedDatasetIds.length
      ? selectedDatasetIds
      : (indexData.dataset_ids?.length ? indexData.dataset_ids : nextDatasets.slice(0, 1).map((item) => item.dataset_id)) || [];
    if (!selectedDatasetIds.length && nextSelected.length) {
      setSelectedDatasetIds(nextSelected);
      const first = nextDatasets.find((item) => item.dataset_id === nextSelected[0]);
      setQueryDatasetId(first?.dataset_id || "");
      setQueryCellId(first?.sample_cell_ids?.[0] || queryCellId);
    }
  }

  async function refreshStatus() {
    const [healthData, authData] = await Promise.all([getHealth(), getCurrentUser()]);
    setHealth(healthData);
    setAuth(authData);
    await loadWorkspace();
  }

  useEffect(() => {
    refreshStatus().catch((err) => setError(getErrorMessage(err)));
  }, []);

  async function runAction(name, action) {
    setBusy(name);
    setError("");
    try {
      await action();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy("");
    }
  }

  function toggleDataset(datasetId) {
    setSelectedDatasetIds((current) => {
      if (current.includes(datasetId)) return current.filter((item) => item !== datasetId);
      return [...current, datasetId];
    });
    const dataset = datasets.find((item) => item.dataset_id === datasetId);
    if (dataset?.sample_cell_ids?.[0]) {
      setQueryDatasetId(dataset.dataset_id);
      setQueryCellId(dataset.sample_cell_ids[0]);
    }
  }

  async function refreshDatasets() {
    const datasetList = await listDatasets();
    setDatasets(datasetList.datasets || []);
    return datasetList.datasets || [];
  }

  async function refreshVisualization(datasetIds = selectedDatasetIds) {
    if (!canVisualize || !datasetIds.length) return;
    const visData = await getVisualizationCells(5000, datasetIds);
    setVisPoints(visData.points || []);
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    await runAction("auth", async () => {
      if (authMode === "register") {
        await registerUser(authForm);
      }
      await loginUser(authForm);
      await refreshStatus();
    });
  }

  async function handleLogout() {
    await runAction("auth", async () => {
      await logoutUser();
      setAuth({ authenticated: false, user: null });
      setSearchResult(null);
      setVisPoints([]);
      await loadWorkspace();
    });
  }

  async function handleScanDatasets() {
    await runAction("scan", async () => {
      await scanDatasets();
      const nextDatasets = await refreshDatasets();
      if (!selectedDatasetIds.length && nextDatasets[0]) {
        setSelectedDatasetIds([nextDatasets[0].dataset_id]);
        setQueryDatasetId(nextDatasets[0].dataset_id);
        setQueryCellId(nextDatasets[0].sample_cell_ids?.[0] || "");
      }
    });
  }

  async function handleUploadDataset() {
    if (!uploadFile) {
      setError("请选择 .h5ad 文件");
      return;
    }
    await runAction("upload", async () => {
      const uploaded = await uploadDataset(uploadFile);
      await refreshDatasets();
      setSelectedDatasetIds((current) => [...new Set([...current, uploaded.dataset_id])]);
      setUploadFile(null);
    });
  }

  async function handleValidateDatasets() {
    await runAction("validate", async () => {
      await validateDatasets(selectedDatasetIds);
      const nextDatasets = await refreshDatasets();
      const firstSelected = nextDatasets.find((item) => selectedDatasetIds.includes(item.dataset_id)) || nextDatasets[0];
      if (firstSelected?.sample_cell_ids?.[0]) {
        setQueryDatasetId(firstSelected.dataset_id);
        setQueryCellId(firstSelected.sample_cell_ids[0]);
      }
    });
  }

  async function handleLoadSelectedDataset() {
    await runAction("load", async () => {
      const datasetId = selectedDatasetIds[0];
      const loaded = await loadDataset({ datasetId });
      setDatasetSummary(loaded);
      setQueryDatasetId(loaded.dataset_id);
      setQueryCellId(loaded.sample_cell_ids?.[0] || queryCellId);
      await refreshVisualization([loaded.dataset_id]);
      await refreshDatasets();
    });
  }

  async function handleBuildIndex() {
    await runAction("index", async () => {
      const data = await buildIndex({ datasetIds: selectedDatasetIds, mode: indexMode, nlist, nprobe });
      setIndexStatus(data);
      setSelectedIndexId(data.active_index_id || data.index_id || "");
      const visualDatasetIds = data.dataset_ids?.length ? data.dataset_ids : selectedDatasetIds;
      await refreshVisualization(visualDatasetIds);
    });
  }

  async function handleSwitchIndex(event) {
    const indexId = event.target.value;
    setSelectedIndexId(indexId);
    await runAction("switch", async () => {
      const data = await switchIndex(indexId);
      setIndexStatus(data);
      await refreshVisualization(data.dataset_ids || []);
    });
  }

  async function handleSearch(event) {
    event.preventDefault();
    await runAction("search", async () => {
      const result = await searchCells({
        cellId: queryCellId,
        topK,
        datasetId: queryDatasetId,
        indexId: selectedIndexId,
      });
      setSearchResult(result);
      const visualDatasetIds = result.index?.dataset_ids?.length ? result.index.dataset_ids : selectedDatasetIds;
      await refreshVisualization(visualDatasetIds);
    });
  }

  const faissMode = health?.faiss?.mode || indexStatus?.mode || "-";
  const datasetTone = datasetSummary?.loaded ? "good" : datasetSummary?.status === "error" ? "bad" : "neutral";
  const indexTone = activeIndex?.ready ? "good" : activeIndex?.status === "error" ? "bad" : "neutral";

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">Single-cell ANN Retrieval</p>
          <h1>单细胞 ANN 检索系统</h1>
        </div>
        <button className="ghost-button" onClick={() => runAction("refresh", refreshStatus)} disabled={Boolean(busy)}>
          <RefreshCw size={18} className={busy === "refresh" ? "spin" : ""} />
          刷新
        </button>
      </header>

      {error ? (
        <div className="error-banner">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      ) : null}

      <section className="top-grid">
        <ModulePanel title="用户信息模块" icon={<User size={20} />}>
          {auth.authenticated ? (
            <>
              <StatGrid
                rows={[
                  { label: "用户", value: auth.user?.username },
                  { label: "身份", value: ROLE_LABELS[role] || role },
                  { label: "FAISS", value: faissMode },
                ]}
              />
              <div className="permission-strip">
                <StatusBadge value={canManageDatasets ? "可管理数据" : "不可管理数据"} tone={canManageDatasets ? "good" : "neutral"} />
                <StatusBadge value={canBuildIndex ? "可构建索引" : "不可构建索引"} tone={canBuildIndex ? "good" : "neutral"} />
                <StatusBadge value={canSearch ? "可查询" : "不可查询"} tone={canSearch ? "good" : "bad"} />
              </div>
              <button className="secondary-button" onClick={handleLogout} disabled={Boolean(busy)}>
                <LogOut size={18} />
                退出登录
              </button>
            </>
          ) : (
            <>
              <p className="permission-note">未登录可以预览系统页面；扫描、上传、校验、加载、建索引和查询需要登录后按身份授权。</p>
              <form className="auth-form" onSubmit={handleAuthSubmit}>
                <div className="segmented-control">
                  <button type="button" className={authMode === "login" ? "active" : ""} onClick={() => setAuthMode("login")}>
                    登录
                  </button>
                  <button type="button" className={authMode === "register" ? "active" : ""} onClick={() => setAuthMode("register")}>
                    注册
                  </button>
                </div>
                <label>
                  用户名
                  <input value={authForm.username} onChange={(event) => setAuthForm({ ...authForm, username: event.target.value })} />
                </label>
                <label>
                  密码
                  <input
                    type="password"
                    value={authForm.password}
                    onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })}
                  />
                </label>
                {authMode === "register" ? (
                  <label>
                    身份
                    <select value={authForm.role} onChange={(event) => setAuthForm({ ...authForm, role: event.target.value })}>
                      <option value="admin">管理员</option>
                      <option value="data_manager">数据维护者</option>
                      <option value="researcher">研究人员</option>
                      <option value="normal_user">普通用户</option>
                    </select>
                  </label>
                ) : null}
                <button type="submit" disabled={Boolean(busy)}>
                  {busy === "auth" ? <LoaderCircle size={18} className="spin" /> : <LogIn size={18} />}
                  {authMode === "register" ? "注册并登录" : "登录"}
                </button>
              </form>
            </>
          )}
        </ModulePanel>

        <ModulePanel title="数据管理模块" icon={<Database size={20} />}>
          {!canManageDatasets ? <p className="permission-note">当前身份只能查看数据集，不能扫描、上传或校验数据。</p> : null}
          <div className="button-row">
            <button onClick={handleScanDatasets} disabled={Boolean(busy) || !canManageDatasets}>
              {busy === "scan" ? <LoaderCircle size={18} className="spin" /> : <RefreshCw size={18} />}
              扫描本地
            </button>
            <button onClick={handleValidateDatasets} disabled={Boolean(busy) || !canManageDatasets || !selectedDatasetIds.length}>
              {busy === "validate" ? <LoaderCircle size={18} className="spin" /> : <Database size={18} />}
              校验选中
            </button>
            <button onClick={handleLoadSelectedDataset} disabled={Boolean(busy) || !canLoadDataset || selectedDatasetIds.length !== 1}>
              {busy === "load" ? <LoaderCircle size={18} className="spin" /> : <Play size={18} />}
              加载单个
            </button>
          </div>
          <div className="upload-row">
            <input type="file" accept=".h5ad" onChange={(event) => setUploadFile(event.target.files?.[0] || null)} disabled={!canManageDatasets} />
            <button onClick={handleUploadDataset} disabled={Boolean(busy) || !canManageDatasets || !uploadFile}>
              {busy === "upload" ? <LoaderCircle size={18} className="spin" /> : <Upload size={18} />}
              上传
            </button>
          </div>
          <div className="table-wrap compact-table">
            <table>
              <thead>
                <tr>
                  <th>选择</th>
                  <th>数据集</th>
                  <th>状态</th>
                  <th>细胞数</th>
                  <th>维度</th>
                  <th>示例 cell_id</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map((dataset) => (
                  <tr key={dataset.dataset_id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedDatasetIds.includes(dataset.dataset_id)}
                        onChange={() => toggleDataset(dataset.dataset_id)}
                      />
                    </td>
                    <td>
                      <strong>{dataset.name}</strong>
                      <span className="subtle">{dataset.dataset_id}</span>
                    </td>
                    <td>
                      <StatusBadge value={dataset.status} tone={dataset.status === "error" ? "bad" : dataset.status === "loaded" ? "good" : "neutral"} />
                    </td>
                    <td>{formatNumber(dataset.cell_count)}</td>
                    <td>{dataset.vector_dim || "-"}</td>
                    <td>{dataset.sample_cell_ids?.[0] || "-"}</td>
                  </tr>
                ))}
                {!datasets.length ? (
                  <tr>
                    <td colSpan="6" className="empty-cell">
                      尚未扫描数据集
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </ModulePanel>
      </section>

      <section className="middle-grid">
        <ModulePanel title="索引构建模块" icon={<GitBranch size={20} />}>
          {!canBuildIndex ? <p className="permission-note">当前身份不能构建或切换索引。</p> : null}
          <StatGrid
            rows={[
              { label: "当前索引", value: activeIndex?.index_id || "-" },
              { label: "状态", value: <StatusBadge value={activeIndex?.status || "not_built"} tone={indexTone} /> },
              { label: "模式", value: activeIndex?.build_mode || indexMode },
              { label: "向量数", value: formatNumber(activeIndex?.vector_count) },
              { label: "FAISS", value: activeIndex?.mode || faissMode },
              { label: "nprobe", value: activeIndex?.nprobe || "-" },
            ]}
          />
          <div className="control-grid">
            <label>
              构建模式
              <select value={indexMode} onChange={(event) => setIndexMode(event.target.value)} disabled={!canBuildIndex}>
                <option value="combined">联合索引</option>
                <option value="separate">独立索引</option>
              </select>
            </label>
            <label>
              nlist
              <input type="number" min="1" value={nlist} onChange={(event) => setNlist(Number(event.target.value))} disabled={!canBuildIndex} />
            </label>
            <label>
              nprobe
              <input type="number" min="1" value={nprobe} onChange={(event) => setNprobe(Number(event.target.value))} disabled={!canBuildIndex} />
            </label>
          </div>
          <div className="button-row">
            <button onClick={handleBuildIndex} disabled={Boolean(busy) || !canBuildIndex || !selectedDatasetIds.length}>
              {busy === "index" ? <LoaderCircle size={18} className="spin" /> : <GitBranch size={18} />}
              构建索引
            </button>
            <select value={selectedIndexId} onChange={handleSwitchIndex} disabled={!canSwitchIndex || !indexOptions.length || Boolean(busy)}>
              <option value="">选择索引</option>
              {indexOptions.map((item) => (
                <option key={item.index_id} value={item.index_id}>
                  {item.index_id}
                </option>
              ))}
            </select>
          </div>
        </ModulePanel>

        <ModulePanel title="查询检索模块" icon={<Search size={20} />}>
          <form className="search-form" onSubmit={handleSearch}>
            <label>
              查询数据集
              <select value={queryDatasetId} onChange={(event) => setQueryDatasetId(event.target.value)}>
                <option value="">自动匹配</option>
                {selectedDatasets.map((dataset) => (
                  <option key={dataset.dataset_id} value={dataset.dataset_id}>
                    {dataset.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              细胞 ID
              <input value={queryCellId} onChange={(event) => setQueryCellId(event.target.value)} />
            </label>
            <label>
              Top-K
              <input type="number" min="1" max="100" value={topK} onChange={(event) => setTopK(Number(event.target.value))} />
            </label>
            <button type="submit" disabled={Boolean(busy) || !canSearch || !queryCellId || !activeIndex?.ready}>
              {busy === "search" ? <LoaderCircle size={18} className="spin" /> : <Play size={18} />}
              查询
            </button>
          </form>
          <div className="metric-strip">
            <div>
              <span>耗时</span>
              <strong>{searchResult ? `${searchResult.query_time_ms} ms` : "-"}</strong>
            </div>
            <div>
              <span>结果数</span>
              <strong>{searchResult?.result_count ?? "-"}</strong>
            </div>
          </div>
          <div className="table-wrap result-table">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>数据集</th>
                  <th>Cell ID</th>
                  <th>Type</th>
                  <th>Disease</th>
                  <th>Distance</th>
                </tr>
              </thead>
              <tbody>
                {(searchResult?.hits || []).map((hit) => (
                  <tr key={`${hit.dataset_id}:${hit.cell_id}`}>
                    <td>{hit.rank}</td>
                    <td>{hit.dataset_name || hit.dataset_id}</td>
                    <td>{hit.cell_id}</td>
                    <td>{hit.cell_type || "-"}</td>
                    <td>{hit.disease || "-"}</td>
                    <td>{hit.distance.toFixed(4)}</td>
                  </tr>
                ))}
                {!searchResult?.hits?.length ? (
                  <tr>
                    <td colSpan="6" className="empty-cell">
                      无结果
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </ModulePanel>
      </section>

      <ModulePanel
        title="可视化展示模块"
        icon={<Activity size={20} />}
        actions={
          <button
            className="secondary-button"
            onClick={() => runAction("visual", () => refreshVisualization(selectedDatasetIds))}
            disabled={Boolean(busy) || !canVisualize || !selectedDatasetIds.length}
          >
            {busy === "visual" ? <LoaderCircle size={18} className="spin" /> : <RefreshCw size={18} />}
            刷新 UMAP
          </button>
        }
      >
        <UmapChart points={visPoints} queryCell={searchResult?.query_cell} hits={searchResult?.hits || []} />
      </ModulePanel>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
