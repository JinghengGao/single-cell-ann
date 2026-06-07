import { useState } from "react";
import { ArrowLeft, ArrowRight, Database, Dna, Eye, FlaskConical, LoaderCircle, LogIn, Sparkles } from "lucide-react";

import { formatNumber } from "../constants";
import { LoginParticleOverlay } from "../components/LoginParticleOverlay";
import { UmapChart } from "../components/UmapChart";
import { Field, StatusBadge } from "../components/ui";

export function LoginPage({ workspace, onBack, onBrowse }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ username: "", password: "", role: "admin" });
  const disabled = Boolean(workspace.busy);

  function fillDemoAccount() {
    setMode("login");
    setForm({ username: "demo_admin", password: "demo_password", role: "admin" });
  }

  function submit(event) {
    event.preventDefault();
    workspace.handleAuth({ mode, ...form });
  }

  return (
    <main className="login-page">
      <section className="login-visual">
        <div className="login-grid" />
        <UmapChart points={workspace.visPoints} stats={workspace.visualStats} colorBy={workspace.appliedVisualState.colorBy} variant="backdrop" />
        <div className="login-visual-shade" />
        <LoginParticleOverlay />
        <div className="login-brand">
          <span className="login-brand-mark">
            <Dna size={25} />
          </span>
          <div>
            <strong>CellScope</strong>
            <span>ANN</span>
          </div>
        </div>
        <div className="login-story">
          <p>Single-cell neighborhood intelligence</p>
          <h1>让每一次细胞检索<br />回到真实表达空间。</h1>
          <span>在统一工作台中探索 UMAP 嵌入、筛选细胞群，并检查 ANN Top-K 邻域。</span>
        </div>
        <div className="login-proof">
          <div>
            <Database size={17} />
            <span>当前数据集</span>
            <strong>{workspace.datasets[0]?.name || "等待连接"}</strong>
          </div>
          <div>
            <FlaskConical size={17} />
            <span>可用细胞</span>
            <strong>{formatNumber(workspace.datasets[0]?.cell_count)}</strong>
          </div>
          <div>
            <Sparkles size={17} />
            <span>向量维度</span>
            <strong>{workspace.datasets[0]?.vector_dim || "-"}</strong>
          </div>
        </div>
      </section>

      <section className="login-panel">
        <button className="login-back-button" type="button" onClick={onBack}>
          <ArrowLeft size={16} />返回平台介绍
        </button>
        <div className="login-panel-inner">
          <div className="login-status">
            <StatusBadge
              value={workspace.connectionError ? "服务连接异常" : workspace.initializing ? "正在连接服务" : "服务已连接"}
              tone={workspace.connectionError ? "bad" : workspace.initializing ? "warm" : "good"}
            />
          </div>
          <div className="login-copy">
            <p>科研分析工作台</p>
            <h2>{mode === "login" ? "登录 CellScope ANN" : "创建工作区账户"}</h2>
            <span>{mode === "login" ? "进入单细胞检索与可视化分析环境。" : "注册后将使用所选角色进入工作台。"}</span>
          </div>

          {workspace.connectionError ? <p className="login-error">{workspace.connectionError}</p> : null}

          <div className="auth-tabs">
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
              登录
            </button>
            <button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}>
              注册
            </button>
          </div>

          <form className="login-form" onSubmit={submit}>
            <Field label="用户名">
              <input
                value={form.username}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                placeholder="请输入用户名"
                autoComplete="username"
              />
            </Field>
            <Field label="密码">
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                placeholder="请输入密码"
                autoComplete={mode === "register" ? "new-password" : "current-password"}
              />
            </Field>
            {mode === "register" ? (
              <Field label="账户角色">
                <select value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })}>
                  <option value="admin">管理员</option>
                  <option value="data_manager">数据维护者</option>
                  <option value="researcher">研究人员</option>
                  <option value="normal_user">普通用户</option>
                </select>
              </Field>
            ) : null}
            <button className="primary-button login-submit" type="submit" disabled={disabled || !form.username || !form.password}>
              {workspace.busy === "auth" ? <LoaderCircle size={18} className="spin" /> : <LogIn size={18} />}
              {mode === "login" ? "进入工作台" : "注册并登录"}
            </button>
          </form>

          <button className="demo-account-button" type="button" onClick={fillDemoAccount}>
            <Sparkles size={16} />
            使用演示账户
          </button>

          <div className="login-divider"><span>或</span></div>

          <button className="guest-button" type="button" onClick={onBrowse} disabled={workspace.initializing && !workspace.visPoints.length}>
            <Eye size={17} />
            只读浏览公开数据
            <ArrowRight size={17} />
          </button>
          <p className="login-footnote">访客模式可查看 UMAP 与公开状态。检索和管理操作需要登录。</p>
        </div>
      </section>
    </main>
  );
}
