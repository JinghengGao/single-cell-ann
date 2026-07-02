import { useState } from "react";
import { Activity, LoaderCircle, ServerCog, ShieldAlert, ShieldOff, Trash2, UserCheck, UserRoundCog, Users } from "lucide-react";

import { ROLE_LABELS } from "../constants";
import { listUsers, updateUserRole, updateUserStatus, deleteUser, getBenchmarkLogs, getQueryLogs, getSystemStatus } from "../api/client";
import { EmptyState, StatusBadge } from "../components/ui";

export function AdminPage({ workspace }) {
  const [users, setUsers] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [editingUser, setEditingUser] = useState(null);
  const [newRole, setNewRole] = useState("");
  const [monitoring, setMonitoring] = useState(null);

  async function refreshUsers() {
    setLoading(true);
    setError("");
    try {
      const data = await listUsers();
      setUsers(data.users || []);
    } catch (e) {
      setError(e?.response?.data?.message || e.message || "加载用户列表失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdateRole(username) {
    if (!newRole) return;
    setError("");
    try {
      await updateUserRole(username, newRole);
      await refreshUsers();
      setEditingUser(null);
      setNewRole("");
    } catch (e) {
      setError(e?.response?.data?.message || e.message || "更新角色失败");
    }
  }

  async function handleDeleteUser(username) {
    if (!window.confirm(`确定删除用户 "${username}"？此操作不可撤销。`)) return;
    setError("");
    try {
      await deleteUser(username);
      await refreshUsers();
    } catch (e) {
      setError(e?.response?.data?.message || e.message || "删除用户失败");
    }
  }

  async function handleToggleStatus(user) {
    const nextStatus = user.status === "disabled" ? "active" : "disabled";
    setError("");
    try {
      await updateUserStatus(user.username, nextStatus);
      await refreshUsers();
    } catch (e) {
      setError(e?.response?.data?.message || e.message || "更新账号状态失败");
    }
  }

  async function refreshMonitoring() {
    setLoading(true);
    setError("");
    try {
      const [system, queryLogs, benchmarkLogs] = await Promise.all([
        getSystemStatus(),
        getQueryLogs(20),
        getBenchmarkLogs(20),
      ]);
      setMonitoring({ system, queryLogs: queryLogs.logs || [], benchmarkLogs: benchmarkLogs.logs || [] });
    } catch (e) {
      setError(e?.response?.data?.message || e.message || "加载运行监控失败");
    } finally {
      setLoading(false);
    }
  }

  if (workspace.role !== "admin") {
    return (
      <div className="page-content">
        <EmptyState icon={ShieldAlert} title="需要管理员权限" description="当前角色无法访问系统管理页面。" />
      </div>
    );
  }

  if (!users && !loading) {
    refreshUsers();
  }

  return (
    <div className="page-content admin-page">
      <div className="page-toolbar">
        <div className="toolbar-left">
          <h2 className="toolbar-title"><Users size={20} />用户管理</h2>
          <StatusBadge value={`${users?.length || 0} 个用户`} tone="teal" dot={false} />
        </div>
        <button className="secondary-button" onClick={refreshUsers} disabled={loading}>
          {loading ? <LoaderCircle size={15} className="spin" /> : null}
          刷新
        </button>
        <button className="secondary-button" onClick={refreshMonitoring} disabled={loading}>
          <Activity size={15} />
          运行监控
        </button>
      </div>

      {error ? <div className="error-banner"><span>{error}</span><button onClick={() => setError("")}>×</button></div> : null}

      {loading && !users ? (
        <div className="loading-center"><LoaderCircle size={24} className="spin" /></div>
      ) : users?.length ? (
        <div className="table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>角色</th>
                <th>状态</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username}>
                  <td className="mono-cell">{u.username}</td>
                  <td>
                    {editingUser === u.username ? (
                      <select value={newRole} onChange={(e) => setNewRole(e.target.value)} className="compact-select">
                        <option value="">选择角色...</option>
                        {Object.entries(ROLE_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    ) : (
                      <StatusBadge value={ROLE_LABELS[u.role] || u.role} tone={u.role === "admin" ? "warm" : "teal"} dot={false} />
                    )}
                  </td>
                  <td>
                    <StatusBadge value={u.status === "disabled" ? "禁用" : "正常"} tone={u.status === "disabled" ? "bad" : "good"} dot={false} />
                  </td>
                  <td className="mono-cell">{u.created_at?.slice(0, 10) || "-"}</td>
                  <td className="action-cell">
                    {editingUser === u.username ? (
                      <>
                        <button className="mini-button primary" onClick={() => handleUpdateRole(u.username)}>保存</button>
                        <button className="mini-button" onClick={() => { setEditingUser(null); setNewRole(""); }}>取消</button>
                      </>
                    ) : (
                      <>
                        <button
                          className="mini-button"
                          onClick={() => { setEditingUser(u.username); setNewRole(u.role); }}
                          disabled={u.username === workspace.auth.user?.username}
                          title={u.username === workspace.auth.user?.username ? "不能修改自己的角色" : "修改角色"}
                        >
                          <UserRoundCog size={14} />
                        </button>
                        <button
                          className="mini-button"
                          onClick={() => handleToggleStatus(u)}
                          disabled={u.username === workspace.auth.user?.username}
                          title={u.status === "disabled" ? "启用用户" : "禁用用户"}
                        >
                          {u.status === "disabled" ? <UserCheck size={14} /> : <ShieldOff size={14} />}
                        </button>
                        <button
                          className="mini-button danger"
                          onClick={() => handleDeleteUser(u.username)}
                          disabled={u.username === workspace.auth.user?.username}
                          title={u.username === workspace.auth.user?.username ? "不能删除自己" : "删除用户"}
                        >
                          <Trash2 size={14} />
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="暂无用户数据" description="系统尚未注册任何用户。" />
      )}

      {monitoring ? (
        <section className="admin-monitor-section">
          <div className="admin-monitor-header">
            <h3><ServerCog size={17} />运行监控</h3>
            <StatusBadge value={monitoring.system.faiss.mode?.toUpperCase() || "FAISS"} tone={monitoring.system.faiss.available ? "good" : "bad"} />
          </div>
          <div className="admin-monitor-grid">
            <div>
              <h4>系统状态</h4>
              <dl className="compact-kv">
                <div><dt>数据集</dt><dd>{monitoring.system.dataset?.name || "-"}</dd></div>
                <div><dt>索引</dt><dd>{monitoring.system.index?.index_id || "-"}</dd></div>
                <div><dt>向量数</dt><dd>{monitoring.system.index?.vector_count || 0}</dd></div>
              </dl>
            </div>
            <div>
              <h4>最近查询</h4>
              <div className="log-list">
                {monitoring.queryLogs.slice(-6).map((item, index) => (
                  <p key={index}><span>{item.query_type || "-"}</span><b>{item.latency_ms ?? "-"}ms</b><small>{item.status || "-"}</small></p>
                ))}
                {!monitoring.queryLogs.length ? <small>暂无查询日志</small> : null}
              </div>
            </div>
            <div>
              <h4>最近评测</h4>
              <div className="log-list">
                {monitoring.benchmarkLogs.slice(-6).map((item, index) => (
                  <p key={index}><span>{item.benchmark_type || "-"}</span><b>{item.qps ?? item.recall ?? "-"}</b><small>{item.top_k ? `Top-${item.top_k}` : "-"}</small></p>
                ))}
                {!monitoring.benchmarkLogs.length ? <small>暂无评测日志</small> : null}
              </div>
            </div>
          </div>
        </section>
      ) : null}
    </div>
  );
}
