import { AlertCircle, X } from "lucide-react";

import { statusTone } from "../constants";

export function StatusBadge({ value, tone = statusTone(value), dot = true }) {
  return (
    <span className={`status-badge ${tone}`}>
      {dot ? <span className="status-dot" /> : null}
      {value || "-"}
    </span>
  );
}

export function IconButton({ label, children, className = "", ...props }) {
  return (
    <button className={`icon-button ${className}`} title={label} aria-label={label} {...props}>
      {children}
    </button>
  );
}

export function EmptyState({ title, description }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      {description ? <span>{description}</span> : null}
    </div>
  );
}

export function AccessNotice({ children = "当前账户没有执行此操作的权限。请登录或切换具有相应权限的账户。" }) {
  return <p className="access-notice">{children}</p>;
}

export function ErrorBanner({ error, onClose }) {
  if (!error) return null;
  return (
    <div className="error-banner">
      <AlertCircle size={17} />
      <span>{error}</span>
      <button className="banner-close" title="关闭提示" aria-label="关闭提示" onClick={onClose}>
        <X size={16} />
      </button>
    </div>
  );
}

export function Field({ label, children, hint, className = "" }) {
  return (
    <label className={`field ${className}`}>
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}
