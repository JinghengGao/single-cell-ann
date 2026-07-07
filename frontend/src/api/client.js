import axios from "axios";

const TOKEN_KEY = "single_cell_ann_token";

// 前端所有 API 请求都通过同一个 axios 实例，便于统一配置 baseURL、超时和认证头。
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000/api",
  timeout: 120000,
});

const LLM_REQUEST_TIMEOUT_MS = 300000;

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
  // 登录态存放在 localStorage，刷新页面后会自动恢复 Authorization 请求头。
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token);
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    window.localStorage.removeItem(TOKEN_KEY);
    delete api.defaults.headers.common.Authorization;
  }
}

setAuthToken(getStoredToken());

export async function getHealth() {
  const { data } = await api.get("/health");
  return data;
}

export async function registerUser({ username, password, role }) {
  const { data } = await api.post("/auth/register", { username, password, role });
  return data;
}

export async function loginUser({ username, password }) {
  const { data } = await api.post("/auth/login", { username, password });
  setAuthToken(data.token);
  return data;
}

export async function logoutUser() {
  const { data } = await api.post("/auth/logout", {});
  setAuthToken("");
  return data;
}

export async function getCurrentUser() {
  const { data } = await api.get("/auth/me");
  return data;
}

export async function listDatasets() {
  const { data } = await api.get("/datasets");
  return data;
}

export async function scanDatasets() {
  const { data } = await api.post("/datasets/scan", {});
  return data;
}

export async function uploadDataset(file) {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post("/datasets/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function validateDatasets(datasetIds) {
  const { data } = await api.post("/datasets/validate", { dataset_ids: datasetIds });
  return data;
}

export async function updateDatasetMetadata(datasetId, updates) {
  const { data } = await api.patch(`/datasets/${encodeURIComponent(datasetId)}/metadata`, updates);
  return data;
}

export async function activateDataset(datasetId) {
  const { data } = await api.post(`/datasets/${encodeURIComponent(datasetId)}/activate`, {});
  return data;
}

export async function offlineDataset(datasetId) {
  const { data } = await api.post(`/datasets/${encodeURIComponent(datasetId)}/offline`, {});
  return data;
}

export async function restoreDataset(datasetId) {
  const { data } = await api.post(`/datasets/${encodeURIComponent(datasetId)}/restore`, {});
  return data;
}

export async function deleteDataset(datasetId) {
  const { data } = await api.delete(`/datasets/${encodeURIComponent(datasetId)}`);
  return data;
}

export async function loadDataset({ datasetId, path } = {}) {
  const payload = {};
  if (datasetId) payload.dataset_id = datasetId;
  if (path) payload.path = path;
  const { data } = await api.post("/datasets/load", payload);
  return data;
}

export async function getCurrentDataset() {
  const { data } = await api.get("/datasets/current");
  return data;
}

export async function buildIndex({ datasetIds, mode, nlist, nprobe, indexType, metric, M, efConstruction, efSearch } = {}) {
  // IVF_FLAT 和 HNSW 共用构建入口，HNSW 参数仅在选择 hnsw 时发送。
  const payload = {
    dataset_ids: datasetIds || [],
    mode: mode || "combined",
    index_type: indexType || "ivf_flat",
    metric: metric || "l2",
    nlist,
    nprobe,
  };
  if (indexType === "hnsw") {
    payload.M = M || 32;
    payload.ef_construction = efConstruction || 200;
    payload.ef_search = efSearch || 64;
  }
  const { data } = await api.post("/index/build", payload);
  return data;
}

export async function switchIndex(indexId) {
  const { data } = await api.post("/index/switch", { index_id: indexId });
  return data;
}

export async function loadIndex(indexId) {
  const { data } = await api.post("/index/load", { index_id: indexId });
  return data;
}

export async function deleteIndex(indexId) {
  const { data } = await api.delete(`/index/${encodeURIComponent(indexId)}`);
  return data;
}

export async function getIndexStatus() {
  const { data } = await api.get("/index/status");
  return data;
}

export async function searchCells({ cellId, topK, datasetId, indexId, metadataFilters } = {}) {
  // 元数据过滤条件展开为后端兼容的 cell_type/disease/AgeGroup/tissue 字段。
  const payload = {
    cell_id: cellId,
    top_k: topK,
    dataset_id: datasetId || undefined,
    index_id: indexId || undefined,
  };
  if (metadataFilters) {
    Object.entries(metadataFilters).forEach(([key, value]) => {
      if (value) payload[key] = value;
    });
  }
  const { data } = await api.post("/search", payload);
  return data;
}

export async function exactSearch({ cellId, topK, datasetId }) {
  const { data } = await api.post("/search/exact", {
    cell_id: cellId,
    top_k: topK,
    dataset_id: datasetId || undefined,
  });
  return data;
}

export async function vectorSearch({ queryVector, topK, indexId, metadataFilters } = {}) {
  const payload = {
    query_vector: queryVector,
    top_k: topK,
    index_id: indexId || undefined,
  };
  if (metadataFilters) {
    Object.entries(metadataFilters).forEach(([key, value]) => {
      if (value) payload[key] = value;
    });
  }
  const { data } = await api.post("/search/vector", payload);
  return data;
}

export async function compareSearch({ cellId, topK, datasetId, indexId }) {
  const { data } = await api.post("/search/compare", {
    cell_id: cellId,
    top_k: topK,
    dataset_id: datasetId || undefined,
    index_id: indexId || undefined,
  });
  return data;
}

export async function batchSearch({ cellIds, topK, datasetId, indexId }) {
  const { data } = await api.post("/search/batch", {
    cell_ids: cellIds,
    top_k: topK,
    dataset_id: datasetId || undefined,
    index_id: indexId || undefined,
  });
  return data;
}

export async function demoSearch(cellId, topK = 5) {
  const params = { top_k: topK };
  if (cellId) params.cell_id = cellId;
  const { data } = await api.get("/demo/search", { params });
  return data;
}

export async function analyzeSearchResult({ searchResult, question, enableThinking }) {
  const { data } = await api.post("/search/analyze", {
    search_result: searchResult,
    question: question || undefined,
    enable_thinking: Boolean(enableThinking),
  }, { timeout: LLM_REQUEST_TIMEOUT_MS });
  return data;
}

export async function ragSearch({ question, topK, datasetIds, indexId, enableThinking }) {
  const { data } = await api.post("/search/rag", {
    question,
    top_k: topK,
    dataset_ids: datasetIds || [],
    index_id: indexId || undefined,
    enable_thinking: Boolean(enableThinking),
  }, { timeout: LLM_REQUEST_TIMEOUT_MS });
  return data;
}

export async function getVisualizationCells(limit = 5000, datasetIds = [], options = {}) {
  const params = {
    limit,
    color_by: options.colorBy,
    sample_strategy: options.sampleStrategy,
  };
  if (datasetIds.length) params.dataset_ids = datasetIds.join(",");
  Object.entries(options.filters || {}).forEach(([fieldName, values]) => {
    if (values?.length) params[`filter_${fieldName}`] = values.join(",");
  });
  const { data } = await api.get("/visualization/cells", { params });
  return data;
}

export async function getVisualizationOptions({ datasetIds = [], geneQuery = "" } = {}) {
  const params = {};
  if (datasetIds.length) params.dataset_ids = datasetIds.join(",");
  if (geneQuery) params.gene_query = geneQuery;
  const { data } = await api.get("/visualization/options", { params });
  return data;
}

// -- Admin APIs --
export async function listUsers() {
  const { data } = await api.get("/admin/users");
  return data;
}

export async function updateUserRole(username, role) {
  const { data } = await api.put(`/admin/users/${encodeURIComponent(username)}/role`, { role });
  return data;
}

export async function updateUserStatus(username, status) {
  const { data } = await api.put(`/admin/users/${encodeURIComponent(username)}/status`, { status });
  return data;
}

export async function deleteUser(username) {
  const { data } = await api.delete(`/admin/users/${encodeURIComponent(username)}`);
  return data;
}

export async function getQueryLogs(limit = 100) {
  const { data } = await api.get("/admin/logs/query", { params: { limit } });
  return data;
}

export async function getBenchmarkLogs(limit = 100) {
  const { data } = await api.get("/admin/logs/benchmark", { params: { limit } });
  return data;
}

export async function getSystemStatus() {
  const { data } = await api.get("/admin/system/status");
  return data;
}
