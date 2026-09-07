import { ArrowClockwise, Check, CheckCircle, CircleNotch, Copy, Info, LockSimple, Minus,
         Plugs, Prohibit, Timer, Warning, WarningOctagon, X } from "@phosphor-icons/react";
import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from "react";
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

// "danger" es la única variante que no se auto-cierra: una corrida que falló
// es la única señal que recibe alguien que dejó el Tablero abierto en otra
// pestaña, y un auto-cierre de 7s incumple WCAG 2.2.1 para ese caso.
interface Toast { id: number; kind: "info" | "success" | "warning" | "danger"; text: string; runId?: string }
const ToastContext = createContext<(kind: Toast["kind"], text: string, runId?: string) => void>(() => {});
export const useToast = () => useContext(ToastContext);

const TOAST_ICON: Record<Toast["kind"], ReactNode> = {
  info:    <Info size={16} color="var(--feedback-info-fg)" aria-hidden="true" />,
  success: <CheckCircle size={16} color="var(--feedback-success-fg)" aria-hidden="true" />,
  warning: <Warning size={16} color="var(--feedback-warning-fg)" aria-hidden="true" />,
  danger:  <WarningOctagon size={16} color="var(--feedback-danger-fg)" aria-hidden="true" />,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const cancelTimer = (id: number) => {
    const timer = timers.current.get(id);
    if (timer) { clearTimeout(timer); timers.current.delete(id); }
  };
  const close = useCallback((id: number) => {
    cancelTimer(id);
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);
  const push = useCallback((kind: Toast["kind"], text: string, runId?: string) => {
    const id = next.current++;
    setToasts((current) => [...current, { id, kind, text, runId }]);
    if (kind !== "danger") {
      timers.current.set(id, setTimeout(() => {
        timers.current.delete(id);
        setToasts((current) => current.filter((t) => t.id !== id));
      }, 7000));
    }
  }, []);

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="toast-stack" role="region" aria-label="Notificaciones">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast--${toast.kind}`}
               role={toast.kind === "warning" || toast.kind === "danger" ? "alert" : "status"}
               // Cancela el auto-cierre mientras el operador está mirando o
               // enfocando el toast — un mínimo de WCAG 2.2.1, no una pausa que
               // se reanuda sola.
               onMouseEnter={() => cancelTimer(toast.id)} onFocus={() => cancelTimer(toast.id)}>
            <span className="toast__icon">{TOAST_ICON[toast.kind]}</span>
            <div className="toast__body">
              <div className="toast__title">{toast.text}</div>
              {toast.runId && <Link className="toast__link" to={`/runs/${toast.runId}`}>Ver corrida →</Link>}
            </div>
            <button className="btn btn--ghost btn--icon btn--sm" style={{ marginLeft: "auto" }}
                    onClick={() => close(toast.id)}
                    aria-label="Cerrar"><X size={12} aria-hidden="true" /></button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function InertRow({ entry }: { entry: CatalogEntry }) {
  return (
    <div className="row ink-muted" style={{ fontSize: 12 }}>
      <Prohibit size={14} color="var(--status-blocked-fg)" aria-hidden="true" />
      <span>{entry.reason}</span>
    </div>
  );
}

export function TimelineIcon({ state }: { state: "done" | "active" | "fail" | "idle" }) {
  const icon = useMemo(() => {
    if (state === "done") return <Check size={12} weight="bold" aria-hidden="true" />;
    if (state === "fail") return <X size={12} weight="bold" aria-hidden="true" />;
    if (state === "active") return <CircleNotch size={12} className="st-spin" aria-hidden="true" />;
    return null;
  }, [state]);
  return <span className="tl-node">{icon}</span>;
}

// Un estado vacío dice qué falta, por qué y qué hacer — "sin datos" no es un
// estado vacío. `danger` es el único tono que rompe la regla de "nunca
// rellenar con el acento": ahí el ícono va sólido en el color de falla.
export function Empty({ icon, title, body, actions, danger, diagnostic, inline }: {
  icon: ReactNode; title: string; body: ReactNode; actions?: ReactNode;
  danger?: boolean; diagnostic?: string; inline?: boolean;
}) {
  return (
    <div className={`empty${inline ? " empty--inline" : ""}`}>
      <span className="empty__icon" style={danger ? { color: "var(--status-failed-fg)", opacity: 1 } : undefined}>
        {icon}
      </span>
      <div className="empty__title">{title}</div>
      <p className="empty__body">{body}</p>
      {actions && <div className="empty__actions">{actions}</div>}
      {diagnostic && <div className="mono ink-subtle" style={{ marginTop: 16, fontSize: 10.5 }}>{diagnostic}</div>}
    </div>
  );
}

// Los cuatro .banner-error de "no se pudo cargar" repetidos por pantalla. La
// diferencia con el banner viejo: dice qué NO se rompió (las corridas en
// curso siguen en el servidor) y deja un diagnóstico copiable en vez de sólo
// "no se pudo cargar".
export function ConnectionError({ endpoint, onRetry }: { endpoint: string; onRetry: () => void }) {
  const [copied, setCopied] = useState(false);
  const diagnostic = `ERR_NETWORK · ${new Date().toLocaleString("es-AR")} · ${endpoint}`;
  return (
    <Empty
      icon={<Plugs size={32} aria-hidden="true" />}
      danger
      title="La consola no llega a la API"
      body={<>Los últimos pedidos a <span className="mono">{endpoint}</span> no tuvieron respuesta.
        Las corridas que ya están en curso siguen ejecutándose en el servidor: esto es la vista, no el motor.</>}
      actions={<>
        <button className="btn btn--primary" onClick={onRetry}>
          <ArrowClockwise size={13} aria-hidden="true" /> Reintentar
        </button>
        <button className="btn btn--quiet" onClick={() => {
          navigator.clipboard?.writeText(diagnostic).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
          });
        }}>
          <Copy size={13} aria-hidden="true" /> {copied ? "Copiado" : "Copiar diagnóstico"}
        </button>
      </>}
      diagnostic={diagnostic}
    />
  );
}

// El dialog es un recurso escaso: interrumpe, roba el foco y no se puede
// ignorar. Se gasta sólo en lo irreversible — promover estado mensual,
// liberar un lock ajeno — nunca para mostrar información (eso va en .notice).
export function Dialog({ open, onClose, onConfirm, icon, tone, title, confirmLabel, aside, children }: {
  open: boolean; onClose: () => void; onConfirm: () => void;
  icon: ReactNode; tone?: "warning" | "danger"; title: string; confirmLabel: string;
  aside?: ReactNode; children: ReactNode;
}) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>("button, [href]")?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      trigger?.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!open) return null;
  return (
    // Sin onClick en el backdrop a propósito: un clic accidental afuera no
    // puede ser lo que promueve un mes.
    <div className="dialog-backdrop">
      <div ref={dialogRef} className={`dialog${tone ? ` dialog--${tone}` : ""}`}
           role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="dialog__head">
          <span className="dialog__icon">{icon}</span>
          <div className="dialog__title" id={titleId}>{title}</div>
        </div>
        <div className="dialog__body">{children}</div>
        <div className="dialog__actions">
          {aside && <span className="dialog__aside">{aside}</span>}
          <button className="btn btn--quiet" onClick={onClose}>Cancelar</button>
          <button className="btn btn--primary" onClick={onConfirm}>{confirmLabel}</button>
        </div>
      </div>
    </div>
  );
}
