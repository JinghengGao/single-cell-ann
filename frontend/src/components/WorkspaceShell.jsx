import { Activity, Database, Dna, GitBranch, LogIn, LogOut, RefreshCw, ShieldCheck, UserRound } from "lucide-react";

import { ROLE_LABELS } from "../constants";
import { ErrorBanner, IconButton, StatusBadge } from "./ui";

const NAV_ITEMS = [
  { id: "analysis", label: "分析工作台", icon: Activity },
  { id: "datasets", label: "数据集", icon: Database },
  { id: "indexes", label: "索引管理", icon: GitBranch },
];

const PAGE_META = {
  analysis: { eyebrow: "Exploration", title: "细胞邻域分析", description: "UMAP 嵌入、元数据过滤与 ANN 邻域检索" },
  datasets: { eyebrow: "Data registry", title: "数据集", description: "维护单细胞数据源与向量准备状态" },
  indexes: { eyebrow: "Vector index", title: "索引管理", description: "构建、检查与切换 FAISS 服务索引" },
};

export function WorkspaceShell({ view, onViewChange, guestMode, onExitGuest, onLogout, workspace, children }) {
  const page = PAGE_META[view];
  const faissMode = workspace.health?.faiss?.mode || workspace.indexStatus?.mode || "unavailable";
  const accountLabel = workspace.auth.authenticated ? ROLE_LABELS[workspace.role] || workspace.role : "只读访客";
  const runtimeDetail =
    faissMode === "unavailable"
      ? "FAISS 不可用"
      : workspace.health?.faiss?.gpu_count
        ? `${workspace.health.faiss.gpu_count} 个 GPU 可用`
        : "CPU 模式";

  return (
    <div className="workspace-shell">
      <aside className="app-sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark">
            <Dna size={20} />
          </span>
          <div>
            <strong>CellScope</strong>
            <span>ANN</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="主导航">
          <span className="nav-caption">工作区</span>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`nav-item ${view === item.id ? "active" : ""}`} onClick={() => onViewChange(item.id)}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-footer">
          <div className="runtime-status">
            <div className="runtime-heading">
              <span>运行状态</span>
              <StatusBadge value={faissMode.toUpperCase()} tone={faissMode === "unavailable" ? "bad" : "good"} />
            </div>
            <small>{runtimeDetail}</small>
          </div>
          <div className="account-row">
            <span className="account-avatar">
              {workspace.auth.authenticated ? <UserRound size={17} /> : <ShieldCheck size={17} />}
            </span>
            <div className="account-copy">
              <strong>{workspace.auth.user?.username || "访客模式"}</strong>
              <span>{accountLabel}</span>
            </div>
            <IconButton
              label={workspace.auth.authenticated ? "退出登录" : "返回登录"}
              className="quiet-icon"
              onClick={workspace.auth.authenticated ? onLogout : onExitGuest}
              disabled={Boolean(workspace.busy)}
            >
              {workspace.auth.authenticated ? <LogOut size={16} /> : <LogIn size={16} />}
            </IconButton>
          </div>
        </div>
      </aside>

      <div className="workspace-main">
        <header className="workspace-header">
          <div className="workspace-heading">
            <p>{page.eyebrow}</p>
            <h1>{page.title}</h1>
            <span>{page.description}</span>
          </div>
          <div className="header-actions">
            {guestMode ? <span className="readonly-chip">只读浏览</span> : null}
            <IconButton
              label="刷新工作区"
              onClick={workspace.handleRefreshStatus}
              disabled={Boolean(workspace.busy)}
            >
              <RefreshCw size={17} className={workspace.busy === "refresh" ? "spin" : ""} />
            </IconButton>
          </div>
        </header>
        <ErrorBanner error={workspace.error} onClose={workspace.clearError} />
        <main className="workspace-content">{children}</main>
      </div>
    </div>
  );
}
