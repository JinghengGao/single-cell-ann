export const CHART_PALETTE = [
  "#168995",
  "#e47b48",
  "#6f8f3d",
  "#7c70b1",
  "#d05d75",
  "#4f73a3",
  "#c89a2d",
  "#357d64",
  "#ad6b9f",
  "#677684",
  "#b7653d",
  "#2f9d8f",
];

export const EXPRESSION_PALETTE = ["#edf7f5", "#bdded8", "#64b8ad", "#168995", "#07505a"];

export const METADATA_FIELDS = ["cell_type", "disease", "AgeGroup", "tissue"];

export const COLOR_FIELD_LABELS = {
  dataset: "数据集",
  cell_type: "细胞类型",
  disease: "疾病",
  AgeGroup: "年龄组",
  tissue: "组织",
};

export const ROLE_LABELS = {
  normal_user: "普通用户",
  researcher: "研究人员",
  data_manager: "数据维护者",
  admin: "管理员",
};

export const ROLE_PERMISSIONS = {
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

export const EMPTY_FILTERS = { cell_type: "", disease: "", AgeGroup: "", tissue: "" };

export function permissionFor(role, key) {
  return Boolean(ROLE_PERMISSIONS[role]?.[key]);
}

export function colorByLabel(colorBy) {
  if (colorBy?.startsWith("gene:")) return colorBy.replace("gene:", "基因 ");
  return COLOR_FIELD_LABELS[colorBy] || colorBy || "-";
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === "") return "-";
  return Number(value).toLocaleString("zh-CN");
}

export function formatBytes(value) {
  if (!Number.isFinite(value)) return "-";
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = value;
  let unit = "B";
  for (const nextUnit of units) {
    amount /= 1024;
    unit = nextUnit;
    if (amount < 1024) break;
  }
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${unit}`;
}

export function getErrorMessage(error) {
  const serverMessage = error?.response?.data?.message;
  const serverCode = error?.response?.data?.error;
  if (serverMessage === "username already exists") return "该账户已存在，请直接登录或更换用户名。";
  if (serverMessage === "username must be at least 3 characters") return "用户名至少需要 3 个字符。";
  if (serverMessage === "password must be at least 6 characters") return "密码至少需要 6 个字符。";
  if (serverMessage === "invalid username or password") return "用户名或密码不正确，请检查后重试。";
  if (serverCode === "invalid_registration") return "注册信息无效，请检查后重试。";
  if (serverCode === "invalid_login") return "登录失败，请检查账号和密码。";
  return serverMessage || serverCode || error?.message || "请求失败";
}

export function statusTone(value) {
  if (["loaded", "validated", "ready", "ok", "gpu", "cpu"].includes(value)) return "good";
  if (["error", "failed", "unavailable"].includes(value)) return "bad";
  if (["building", "loading", "pending"].includes(value)) return "warm";
  return "neutral";
}
