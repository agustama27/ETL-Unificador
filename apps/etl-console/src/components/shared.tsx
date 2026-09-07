import { Check, CheckCircle, CircleNotch, Info, LockSimple, Minus, Prohibit, Timer, Warning, X, XCircle } from "@phosphor-icons/react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { READINESS_LABELS, STATUS_LABELS } from "../api";
import type { CatalogEntry, RunStatus } from "../api";

// El estado define tres canales redundantes: color (la clase .st-*), glifo y forma
// del contenedor. El Record tipado por RunStatus es la garantia: si el backend suma
// un octavo estado, esto no compila hasta que se le den clase y glifo — con el mapa
// de color anterior caia en undefined y el badge salia gris sin avisar.
const STATUS_UI: Record<RunStatus | "pending", { cls: string; icon: ReactNode }> = {
  succeeded: { cls: "st-succeeded", icon: <Check className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
  running:   { cls: "st-running",   icon: <CircleNotch className="st-glyph st-spin" size={11} aria-hidden="true" /> },
  preparing: { cls: "st-preparing", icon: <CircleNotch className="st-glyph st-spin" size={11} aria-hidden="true" /> },
  failed:    { cls: "st-failed",    icon: <X className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
  timed_out: { cls: "st-timed-out", icon: <Timer className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
  blocked:   { cls: "st-blocked",   icon: <LockSimple className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
  pending:   { cls: "st-pending",   icon: <Minus className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
};

export function StatusBadge({ status, large }: { status: RunStatus | "pending"; large?: boolean }) {
  const ui = STATUS_UI[status];
  return (
    <span className={`st-badge ${ui.cls}${large ? " st-badge--lg" : ""}`}>
      {ui.icon}
      {STATUS_LABELS[status]}
    </span>
  );
}

// La preparacion de un ETL no es el estado de una corrida: normalmente es un rotulo
// tranquilo. Solo "bloqueado" escala a badge de estado, porque ahi si hay una
// condicion operativa que atender.
const READINESS_UI: Record<CatalogEntry["readiness"], { cls: string; icon: ReactNode }> = {
  ready:     { cls: "tag tag--accent", icon: null },
  candidate: { cls: "tag", icon: null },
  blocked:   { cls: "st-badge st-blocked", icon: <LockSimple className="st-glyph" size={11} weight="bold" aria-hidden="true" /> },
};

export function ReadinessBadge({ readiness }: { readiness: CatalogEntry["readiness"] }) {
  const ui = READINESS_UI[readiness];
  return (
    <span className={ui.cls}>
      {ui.icon}
      {READINESS_LABELS[readiness]}
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
            <button className="btn btn--ghost" style={{ marginLeft: "auto" }}
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
