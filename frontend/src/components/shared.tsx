import { CheckCircle, CircleNotch, Info, Prohibit, Warning, X, XCircle } from "@phosphor-icons/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { READINESS_LABELS, STATUS_LABELS } from "../api";
import type { CatalogEntry, RunStatus } from "../api";

const STATUS_COLOR: Record<RunStatus | "pending", string> = {
  preparing: "var(--status-running)", running: "var(--status-running)",
  succeeded: "var(--status-success)", failed: "var(--status-failed)",
  timed_out: "var(--status-timeout)", blocked: "var(--status-blocked)",
  pending: "var(--status-pending)",
};

export function StatusBadge({ status, large }: { status: RunStatus | "pending"; large?: boolean }) {
  const live = status === "preparing" || status === "running";
  return (
    <span className={`badge${large ? " lg" : ""}`} style={{ "--badge-color": STATUS_COLOR[status] } as never}>
      {live ? <span className="spin"><CircleNotch size={large ? 14 : 11} /></span> : <span className="dot" />}
      {STATUS_LABELS[status]}
    </span>
  );
}

const READINESS_COLOR = {
  ready: "var(--status-success)", candidate: "var(--status-pending)", blocked: "var(--status-blocked)",
} as const;

export function ReadinessBadge({ readiness }: { readiness: CatalogEntry["readiness"] }) {
  return (
    <span className="badge" style={{ "--badge-color": READINESS_COLOR[readiness] } as never}>
      <span className="dot" />{READINESS_LABELS[readiness]}
    </span>
  );
}

interface Toast { id: number; kind: "info" | "success" | "warning"; text: string; runId?: string }
const ToastContext = createContext<(kind: Toast["kind"], text: string, runId?: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const push = useCallback((kind: Toast["kind"], text: string, runId?: string) => {
    const id = next.current++;
    setToasts((current) => [...current, { id, kind, text, runId }]);
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 7000);
  }, []);
  const icons = { info: <Info size={16} color="var(--color-accent)" />,
                  success: <CheckCircle size={16} color="var(--status-success)" />,
                  warning: <Warning size={16} color="var(--status-timeout)" /> };
  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toasts">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast ${toast.kind}`}>
            {icons[toast.kind]}
            <div>
              <div>{toast.text}</div>
              {toast.runId && <Link to={`/runs/${toast.runId}`}>Ver corrida →</Link>}
            </div>
            <button className="btn-ghost" style={{ marginLeft: "auto" }}
                    onClick={() => setToasts((c) => c.filter((t) => t.id !== toast.id))}
                    aria-label="Cerrar"><X size={12} /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function InertRow({ entry }: { entry: CatalogEntry }) {
  return (
    <div className="row muted" style={{ fontSize: 12 }}>
      <Prohibit size={14} color="var(--status-blocked)" />
      <span>{entry.reason}</span>
    </div>
  );
}

export function TimelineIcon({ state }: { state: "done" | "active" | "fail" | "idle" }) {
  const icon = useMemo(() => {
    if (state === "done") return <CheckCircle size={14} weight="bold" />;
    if (state === "fail") return <XCircle size={14} weight="bold" />;
    if (state === "active") return <CircleNotch size={14} className="spin" />;
    return null;
  }, [state]);
  return <span className={`dot ${state === "idle" ? "" : state}`}>{icon}</span>;
}
