import axios from "axios";

const TOKEN_KEY = "single_cell_ann_token";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000/api",
  timeout: 120000,
});

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token) {
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

export async function buildIndex({ datasetIds, mode, nlist, nprobe } = {}) {
  const { data } = await api.post("/index/build", {
    dataset_ids: datasetIds || [],
    mode: mode || "combined",
    nlist,
    nprobe,
  });
  return data;
}

export async function switchIndex(indexId) {
  const { data } = await api.post("/index/switch", { index_id: indexId });
  return data;
}

export async function getIndexStatus() {
  const { data } = await api.get("/index/status");
  return data;
}

export async function searchCells({ cellId, topK, datasetId, indexId }) {
  const { data } = await api.post("/search", {
    cell_id: cellId,
    top_k: topK,
    dataset_id: datasetId || undefined,
    index_id: indexId || undefined,
  });
  return data;
}

export async function getVisualizationCells(limit = 5000, datasetIds = []) {
  const params = { limit };
  if (datasetIds.length) params.dataset_ids = datasetIds.join(",");
  const { data } = await api.get("/visualization/cells", { params });
  return data;
}
