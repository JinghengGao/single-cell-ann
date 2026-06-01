import { useEffect, useMemo, useState } from "react";

import {
  buildIndex,
  getCurrentDataset,
  getCurrentUser,
  getHealth,
  getIndexStatus,
  getVisualizationCells,
  getVisualizationOptions,
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
} from "../api/client";
import { EMPTY_FILTERS, getErrorMessage, permissionFor } from "../constants";

const EMPTY_AUTH = { authenticated: false, user: null };

export function useWorkspace() {
  const [health, setHealth] = useState(null);
  const [auth, setAuth] = useState(EMPTY_AUTH);
  const [datasets, setDatasets] = useState([]);
  const [datasetSummary, setDatasetSummary] = useState(null);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState([]);
  const [indexStatus, setIndexStatus] = useState(null);
  const [selectedIndexId, setSelectedIndexId] = useState("");
  const [indexMode, setIndexMode] = useState("combined");
  const [nlist, setNlist] = useState(256);
  const [nprobe, setNprobe] = useState(16);
  const [visPoints, setVisPoints] = useState([]);
  const [visOptions, setVisOptions] = useState(null);
  const [visualColorBy, setVisualColorBy] = useState("cell_type");
  const [visualLimit, setVisualLimit] = useState(5000);
  const [visualSampleStrategy, setVisualSampleStrategy] = useState("even");
  const [visualFilters, setVisualFilters] = useState(EMPTY_FILTERS);
  const [visualStats, setVisualStats] = useState(null);
  const [visualGeneQuery, setVisualGeneQuery] = useState("ALB");
  const [queryCellId, setQueryCellId] = useState("");
  const [queryDatasetId, setQueryDatasetId] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchResult, setSearchResult] = useState(null);
  const [uploadFile, setUploadFile] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState("");
  const [initializing, setInitializing] = useState(true);

  const role = auth.user?.role;
  const canManageDatasets = permissionFor(role, "manageDatasets");
  const canLoadDataset = permissionFor(role, "loadDataset");
  const canBuildIndex = permissionFor(role, "buildIndex");
  const canSwitchIndex = permissionFor(role, "switchIndex");
  const canSearch = permissionFor(role, "search");
  const canVisualize = true;

  const selectedDatasets = useMemo(
    () => datasets.filter((dataset) => selectedDatasetIds.includes(dataset.dataset_id)),
    [datasets, selectedDatasetIds],
  );
  const indexOptions = indexStatus?.indexes || [];
  const activeIndex =
    indexOptions.find((item) => item.index_id === (selectedIndexId || indexStatus?.active_index_id)) || indexStatus;
  const topKTypeStats = useMemo(() => {
    const counts = new Map();
    (searchResult?.hits || []).forEach((hit) => {
      const key = hit.cell_type || "-";
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    return Array.from(counts.entries()).map(([value, count]) => ({ value, count }));
  }, [searchResult]);
  const topKDistanceStats = useMemo(() => {
    const distances = (searchResult?.hits || []).map((hit) => hit.distance).filter((value) => Number.isFinite(value));
    if (!distances.length) return null;
    return {
      min: Math.min(...distances),
      max: Math.max(...distances),
      mean: distances.reduce((sum, value) => sum + value, 0) / distances.length,
    };
  }, [searchResult]);

  async function runAction(name, action) {
    setBusy(name);
    setError("");
    try {
      return await action();
    } catch (actionError) {
      setError(getErrorMessage(actionError));
      return null;
    } finally {
      setBusy("");
    }
  }

  function resolveSelectedDatasets(nextDatasets, nextIndex, currentSelection = selectedDatasetIds) {
    const availableIds = new Set(nextDatasets.map((dataset) => dataset.dataset_id));
    const retainedIds = currentSelection.filter((datasetId) => availableIds.has(datasetId));
    if (retainedIds.length) return retainedIds;
    const indexedIds = (nextIndex?.dataset_ids || []).filter((datasetId) => availableIds.has(datasetId));
    if (indexedIds.length) return indexedIds;
    return nextDatasets[0] ? [nextDatasets[0].dataset_id] : [];
  }

  async function fetchVisualization(datasetIds = selectedDatasetIds, overrides = {}) {
    if (!datasetIds.length) {
      setVisPoints([]);
      setVisOptions(null);
      setVisualStats(null);
      return null;
    }
    const colorBy = overrides.colorBy ?? visualColorBy;
    const filters = overrides.filters ?? visualFilters;
    const geneQuery = overrides.geneQuery ?? visualGeneQuery;
    const limit = overrides.limit ?? visualLimit;
    const sampleStrategy = overrides.sampleStrategy ?? visualSampleStrategy;
    const filterParams = Object.fromEntries(
      Object.entries(filters)
        .filter(([, value]) => value)
        .map(([fieldName, value]) => [fieldName, [value]]),
    );
    const [optionsData, visData] = await Promise.all([
      getVisualizationOptions({ datasetIds, geneQuery }),
      getVisualizationCells(limit, datasetIds, { colorBy, filters: filterParams, sampleStrategy }),
    ]);
    setVisOptions(optionsData);
    setVisPoints(visData.points || []);
    setVisualStats(visData.stats || null);
    return visData;
  }

  async function fetchWorkspaceStatus({ refreshVisual = true } = {}) {
    const [healthData, authData, datasetList, currentDataset, indexData] = await Promise.all([
      getHealth(),
      getCurrentUser(),
      listDatasets(),
      getCurrentDataset(),
      getIndexStatus(),
    ]);
    const nextDatasets = datasetList.datasets || [];
    const nextSelectedIds = resolveSelectedDatasets(nextDatasets, indexData);
    setHealth(healthData);
    setAuth(authData);
    setDatasets(nextDatasets);
    setDatasetSummary(currentDataset);
    setIndexStatus(indexData);
    setSelectedIndexId(indexData.active_index_id || indexData.index_id || "");
    setSelectedDatasetIds(nextSelectedIds);
    const firstDataset = nextDatasets.find((dataset) => dataset.dataset_id === nextSelectedIds[0]);
    if (firstDataset) {
      setQueryDatasetId((current) => current || firstDataset.dataset_id);
      setQueryCellId((current) => current || firstDataset.sample_cell_ids?.[0] || "");
    }
    if (refreshVisual && nextSelectedIds.length) {
      await fetchVisualization(nextSelectedIds);
    }
    return { authData, nextDatasets, nextSelectedIds, indexData };
  }

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      setInitializing(true);
      setConnectionError("");
      try {
        const [healthData, authData, datasetList, currentDataset, indexData] = await Promise.all([
          getHealth(),
          getCurrentUser(),
          listDatasets(),
          getCurrentDataset(),
          getIndexStatus(),
        ]);
        if (cancelled) return;
        const nextDatasets = datasetList.datasets || [];
        const availableIds = new Set(nextDatasets.map((dataset) => dataset.dataset_id));
        const indexedIds = (indexData.dataset_ids || []).filter((datasetId) => availableIds.has(datasetId));
        const nextSelectedIds = indexedIds.length ? indexedIds : nextDatasets[0] ? [nextDatasets[0].dataset_id] : [];
        const firstDataset = nextDatasets.find((dataset) => dataset.dataset_id === nextSelectedIds[0]);
        setHealth(healthData);
        setAuth(authData);
        setDatasets(nextDatasets);
        setDatasetSummary(currentDataset);
        setIndexStatus(indexData);
        setSelectedIndexId(indexData.active_index_id || indexData.index_id || "");
        setSelectedDatasetIds(nextSelectedIds);
        setQueryDatasetId(firstDataset?.dataset_id || "");
        setQueryCellId(firstDataset?.sample_cell_ids?.[0] || "");
        if (nextSelectedIds.length) {
          const [optionsData, visData] = await Promise.all([
            getVisualizationOptions({ datasetIds: nextSelectedIds, geneQuery: "ALB" }),
            getVisualizationCells(5000, nextSelectedIds, { colorBy: "cell_type", filters: {}, sampleStrategy: "even" }),
          ]);
          if (cancelled) return;
          setVisOptions(optionsData);
          setVisPoints(visData.points || []);
          setVisualStats(visData.stats || null);
        }
      } catch (initializeError) {
        if (cancelled) return;
        const message = getErrorMessage(initializeError);
        setConnectionError(message);
        setError(message);
      } finally {
        if (!cancelled) setInitializing(false);
      }
    }
    initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleAuth({ mode, username, password, role: requestedRole }) {
    return runAction("auth", async () => {
      if (mode === "register") {
        await registerUser({ username, password, role: requestedRole });
      }
      await loginUser({ username, password });
      await fetchWorkspaceStatus();
    });
  }

  async function handleLogout() {
    return runAction("auth", async () => {
      await logoutUser();
      setAuth(EMPTY_AUTH);
      setSearchResult(null);
      await fetchWorkspaceStatus();
    });
  }

  async function handleRefreshStatus() {
    return runAction("refresh", () => fetchWorkspaceStatus());
  }

  async function handleRefreshVisualization(overrides = {}) {
    return runAction("visual", () => fetchVisualization(selectedDatasetIds, overrides));
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
    const nextDatasets = datasetList.datasets || [];
    setDatasets(nextDatasets);
    return nextDatasets;
  }

  async function handleScanDatasets() {
    return runAction("scan", async () => {
      await scanDatasets();
      const nextDatasets = await refreshDatasets();
      const nextSelectedIds = resolveSelectedDatasets(nextDatasets, indexStatus);
      setSelectedDatasetIds(nextSelectedIds);
    });
  }

  async function handleUploadDataset() {
    if (!uploadFile) {
      setError("请选择 .h5ad 文件");
      return;
    }
    return runAction("upload", async () => {
      const uploaded = await uploadDataset(uploadFile);
      await refreshDatasets();
      setSelectedDatasetIds((current) => [...new Set([...current, uploaded.dataset_id])]);
      setUploadFile(null);
    });
  }

  async function handleValidateDatasets() {
    return runAction("validate", async () => {
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
    return runAction("load", async () => {
      const datasetId = selectedDatasetIds[0];
      const loaded = await loadDataset({ datasetId });
      setDatasetSummary(loaded);
      setQueryDatasetId(loaded.dataset_id);
      setQueryCellId(loaded.sample_cell_ids?.[0] || queryCellId);
      await fetchVisualization([loaded.dataset_id]);
      await refreshDatasets();
    });
  }

  async function handleBuildIndex() {
    return runAction("index", async () => {
      const data = await buildIndex({ datasetIds: selectedDatasetIds, mode: indexMode, nlist, nprobe });
      setIndexStatus(data);
      setSelectedIndexId(data.active_index_id || data.index_id || "");
      await fetchVisualization(data.dataset_ids?.length ? data.dataset_ids : selectedDatasetIds);
    });
  }

  async function handleSwitchIndex(indexId) {
    setSelectedIndexId(indexId);
    return runAction("switch", async () => {
      const data = await switchIndex(indexId);
      setIndexStatus(data);
      const nextDatasetIds = data.dataset_ids || [];
      setSelectedDatasetIds(nextDatasetIds);
      await fetchVisualization(nextDatasetIds);
    });
  }

  async function handleSearch() {
    return runAction("search", async () => {
      const result = await searchCells({
        cellId: queryCellId,
        topK,
        datasetId: queryDatasetId,
        indexId: selectedIndexId,
      });
      setSearchResult(result);
      const visualDatasetIds = result.index?.dataset_ids?.length ? result.index.dataset_ids : selectedDatasetIds;
      await fetchVisualization(visualDatasetIds);
    });
  }

  async function handleApplyGeneColor() {
    const geneQuery = visualGeneQuery.trim();
    if (!geneQuery) {
      setError("请输入基因名或 Ensembl ID");
      return;
    }
    const colorBy = `gene:${geneQuery}`;
    setVisualColorBy(colorBy);
    await handleRefreshVisualization({ colorBy, geneQuery });
  }

  async function handleClearVisualFilters() {
    setVisualFilters(EMPTY_FILTERS);
    await handleRefreshVisualization({ filters: EMPTY_FILTERS });
  }

  function handlePickVisualizationCell(point) {
    setQueryDatasetId(point.dataset_id);
    setQueryCellId(point.name);
  }

  function exportVisualizationCsv() {
    const rows = [
      ["dataset_id", "dataset_name", "cell_id", "x", "y", "cell_type", "disease", "AgeGroup", "tissue", "color_value", "expression"],
      ...visPoints.map((point) => [
        point.dataset_id,
        point.dataset_name,
        point.cell_id,
        point.x,
        point.y,
        point.cell_type || "",
        point.disease || "",
        point.AgeGroup || "",
        point.tissue || "",
        point.color_value ?? "",
        point.expression ?? "",
      ]),
    ];
    const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "cellscope_umap_points.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return {
    activeIndex,
    auth,
    busy,
    canBuildIndex,
    canLoadDataset,
    canManageDatasets,
    canSearch,
    canSwitchIndex,
    canVisualize,
    clearError: () => setError(""),
    connectionError,
    datasetSummary,
    datasets,
    error,
    exportVisualizationCsv,
    handleApplyGeneColor,
    handleAuth,
    handleBuildIndex,
    handleClearVisualFilters,
    handleLoadSelectedDataset,
    handleLogout,
    handlePickVisualizationCell,
    handleRefreshStatus,
    handleRefreshVisualization,
    handleScanDatasets,
    handleSearch,
    handleSwitchIndex,
    handleUploadDataset,
    handleValidateDatasets,
    health,
    indexMode,
    indexOptions,
    indexStatus,
    initializing,
    nlist,
    nprobe,
    queryCellId,
    queryDatasetId,
    role,
    searchResult,
    selectedDatasetIds,
    selectedDatasets,
    selectedIndexId,
    setIndexMode,
    setNlist,
    setNprobe,
    setQueryCellId,
    setQueryDatasetId,
    setSelectedDatasetIds,
    setTopK,
    setUploadFile,
    setVisualColorBy,
    setVisualFilters,
    setVisualGeneQuery,
    setVisualLimit,
    setVisualSampleStrategy,
    topK,
    topKDistanceStats,
    topKTypeStats,
    toggleDataset,
    uploadFile,
    visOptions,
    visPoints,
    visualColorBy,
    visualFilters,
    visualGeneQuery,
    visualLimit,
    visualSampleStrategy,
    visualStats,
  };
}
