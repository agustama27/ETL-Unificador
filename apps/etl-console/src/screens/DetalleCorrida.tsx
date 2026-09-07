import { DownloadSimple, FileDashed, FileZip, HourglassHigh, LockSimpleOpen, WarningOctagon } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ERROR_COPY, FALLBACK_ERROR, LIVE, downloadArtifact, downloadArtifactsZip,
         fetchCatalog, fetchRun, formatBytes, formatDuration, formatMoment, runAction } from "../api";
import type { ErrorCopy, RunDetail } from "../api";
import { ConnectionError, Dialog, Empty, StatusBadge, TimelineIcon, useToast } from "../components/shared";

function LiveCard({ run }: { run: RunDetail }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = run.started_at ? new Date(run.started_at).getTime() : Date.now();
    const timer = setInterval(() => setElapsed(Math.max(0, Date.now() - started)), 1000);
    return () => clearInterval(timer);
  }, [run.started_at]);
  const minutes = Math.floor(elapsed / 60000);
  const seconds = Math.floor((elapsed % 60000) / 1000);
  return (
    <div className="card stack" style={{ gap: 10 }}>
      <div>{run.status === "preparing"
        ? "Preparando la corrida: validando parámetros y tomando lock…"
        : "Ejecutando el ETL. Podés quedarte mirando o volver al tablero."}</div>
      {/* El cronómetro no es una región activa: si viviera dentro de un aria-live
          anunciaría el segundero entero. El dato accesible va aparte, con
          granularidad de minuto, en el texto de arriba. */}
      <div className="mono" aria-hidden="true" style={{ color: "var(--brand-text)", fontSize: 15 }}>
        {minutes}:{String(seconds).padStart(2, "0")}
      </div>
      <div style={{ height: 4, borderRadius: 4, background: "var(--surface-sunken)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: "35%", background: "var(--brand-base)",
                      animation: "shimmer 1.4s ease-in-out infinite" }} />
      </div>
      <div className="row">
        <Link className="btn btn--secondary" to="/">Volver al tablero y seguir con otro ETL</Link>
        <span className="ink-muted">Te avisamos acá y en el tablero cuando termine.</span>
      </div>
    </div>
  );
}

// Rótulo de cada acción posible en ERROR_COPY. El texto de "retry" cambia
// cuando queda demovida (ver ACTION_CLASS): reintentar sin ser la acción
// recomendada es "de todas formas", no la salida obvia.
const ACTION_LABEL: Record<ErrorCopy["actions"][number], string> = {
  retry: "Reintentar corrida", free_lock: "Liberar lock",
  view_promoted: "Ver corrida promovida", notify: "Notificar a desarrollo",
};

function ErrorCard({ run }: { run: RunDetail }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [confirmingLock, setConfirmingLock] = useState(false);
  const copy = (run.error_code && ERROR_COPY[run.error_code]) || FALLBACK_ERROR;
  const mark = run.status === "blocked" ? "var(--status-blocked-mark)"
    : run.status === "timed_out" ? "var(--status-timed-out-mark)" : "var(--status-failed-mark)";

  const act = async (action: "free_lock" | "notify_dev") => {
    try {
      await runAction(run.run_id, action);
      toast("success", action === "free_lock" ? "Lock liberado." : "Aviso registrado para desarrollo.");
    } catch (error) {
      toast("warning", (error as Error).message);
    }
  };

  // La primera acción del array es la recomendada para este error y va como
  // botón secundario. "Reintentar" nunca es la salida obvia en una pantalla
  // de error — si aparece en segundo lugar (lock_exists) hay algo mejor para
  // hacer primero, y baja a .btn--quiet con una etiqueta que lo deja claro.
  const lead = copy.actions[0];

  return (
    <div className="card card--elevated" style={{ boxShadow: `inset 3px 0 0 ${mark}, var(--elevation-2)` }}>
      <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
        <WarningOctagon size={22} color="var(--status-failed-fg)" style={{ flex: "none", marginTop: 1 }} aria-hidden="true" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h2 style={{ marginBottom: 6 }}>{copy.title}</h2>
          <p style={{ margin: "0 0 8px", fontSize: 12.5, color: "var(--ink-secondary)", maxWidth: "88ch" }}>{copy.what}</p>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--ink-secondary)", maxWidth: "88ch" }}>
            <strong style={{ fontWeight: 500, color: "var(--ink-primary)" }}>Qué hacer:</strong> {copy.todo}
          </p>
          <div className="row" style={{ marginTop: 14 }}>
            {copy.actions.map((action) => {
              const cls = action === lead ? "btn btn--secondary" : action === "retry" ? "btn btn--quiet" : "btn btn--ghost";
              const label = action === "retry" && action !== lead ? "Reintentar de todas formas" : ACTION_LABEL[action];
              if (action === "view_promoted") return <Link key={action} className={cls} to="/historial">{label}</Link>;
              // Liberar un lock que quizá sea de otra corrida viva es irreversible
              // en la práctica (dos procesos pisándose), así que pasa por el dialog
              // en vez de ejecutarse directo.
              const onClick = action === "retry" ? () => navigate(`/lanzar/${run.etl_id}`)
                : action === "free_lock" ? () => setConfirmingLock(true) : () => act("notify_dev");
              return <button key={action} className={cls} onClick={onClick}>{label}</button>;
            })}
            <span className="mono ink-subtle" style={{ marginLeft: "auto" }}>{run.error_code ?? "desconocido"}</span>
          </div>
        </div>
      </div>
      <Dialog open={confirmingLock} tone="danger" icon={<LockSimpleOpen size={20} aria-hidden="true" />}
              title={`Liberar el lock de ${run.etl_id}`} confirmLabel="Liberar lock"
              onClose={() => setConfirmingLock(false)}
              onConfirm={() => { setConfirmingLock(false); act("free_lock"); }}>
        <p>Si otra corrida de este ETL sigue en curso, esto le puede pisar el resultado: dos
          procesos escribiendo al mismo tiempo.</p>
        <p>Revisá el Tablero antes de confirmar — si no hay ninguna corrida activa, es seguro liberarlo.</p>
      </Dialog>
    </div>
  );
}

const STEP_STATE_LABEL: Record<string, string> = {
  done: "completado", active: "en curso", fail: "falló", idle: "pendiente",
};

function Lifecycle({ run }: { run: RunDetail }) {
  const failedAtRun = ["failed", "timed_out"].includes(run.status);
  const blockedEarly = run.status === "blocked";
  const steps = [
    {
      title: "Preparación",
      note: "Validación de parámetros, staging de archivos y lock del ETL.",
      state: blockedEarly && !run.command.length ? "fail"
        : run.status === "preparing" ? "active" : "done",
      when: run.started_at,
    },
    {
      title: "Ejecución",
      note: "El proceso legacy corre aislado en el sandbox de la corrida.",
      state: run.status === "running" ? "active"
        : run.status === "preparing" || (blockedEarly && !run.command.length) ? "idle"
        : failedAtRun ? "fail" : "done",
      when: null,
    },
    {
      title: "Resultado",
      note: "Verificación de artefactos y cierre de la evidencia.",
      state: run.status === "succeeded" ? "done"
        : LIVE.includes(run.status) ? "idle" : "fail",
      when: run.finished_at,
    },
  ] as const;

  // La causa concreta de la falla se muestra en el paso que falló, no en otra
  // card: es donde el ojo ya está. Un resumen corto, no el ErrorCard completo
  // (que sigue arriba de la página con las acciones).
  const copy = failedAtRun || blockedEarly ? (run.error_code && ERROR_COPY[run.error_code]) || FALLBACK_ERROR : null;

  const outputsLabel = { passed: "Salidas verificadas ✓", failed: "Salidas con problemas",
                         not_run: "Salidas no evaluadas" } as Record<string, string>;
  const stateLabel = { promoted: "Estado promovido", not_applicable: "Sin efecto de estado (stateless)",
                       failed: "Estado: requiere recuperación", not_started: "—",
                       staged: "Estado preparado (no promovido)" } as Record<string, string>;

  return (
    <div className="card">
      <div className="card__head"><span className="card__title">Ciclo de vida</span></div>
      <ol className="timeline" style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {steps.map((step, index) => (
          <li key={step.title} className="tl-step" data-state={step.state}>
            <div className="tl-rail">
              <TimelineIcon state={step.state} />
              {index < steps.length - 1 && <span className="tl-line" />}
            </div>
            <div className="tl-body">
              <div className="tl-head">
                <span className="tl-title">{step.title}</span>
                <span className="sr-only">{STEP_STATE_LABEL[step.state]}</span>
              </div>
              <div className="tl-note">{step.note}</div>
              {step.when && <div className="tl-when mono">{formatMoment(step.when)}</div>}
              {step.state === "fail" && copy && (
                <div className="notice notice--danger" style={{ marginTop: 10, fontSize: 12 }}>
                  <WarningOctagon size={15} className="notice__icon" aria-hidden="true" />
                  <div><div className="notice__title" style={{ fontSize: 12.5 }}>{copy.title}</div>{copy.what}</div>
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      <h3 style={{ marginTop: 6 }}>Postcondiciones</h3>
      <div className="stack" style={{ gap: 6, fontSize: 12.5 }}>
        <div>{outputsLabel[run.postconditions?.outputs ?? "not_run"] ?? "Pendiente"}</div>
        <div>{stateLabel[run.postconditions?.state ?? "not_started"] ?? "—"}</div>
      </div>
    </div>
  );
}

// Divide un tail de log en líneas y colorea por nivel detectado en el texto
// (INFO/WARN/ERROR ya vienen así de los procesos legacy). No inventa
// estructura que el backend no da — sólo lee el nivel que el texto ya trae.
function LogLines({ text }: { text: string }) {
  return (
    <>
      {text.split("\n").map((line, index) => {
        const cls = /\bERROR\b/.test(line) ? "log__line log__line--err"
          : /\bWARN\b/.test(line) ? "log__line log__line--warn" : "log__line";
        return <span key={index} className={cls}>{line}{"\n"}</span>;
      })}
    </>
  );
}

export default function DetalleCorrida() {
  const { runId = "" } = useParams();
  const queryClient = useQueryClient();
  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => fetchRun(runId),
    refetchInterval: (query) =>
      query.state.data && LIVE.includes(query.state.data.status) ? 2500 : false,
  });
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });
  useEffect(() =>

    () => { queryClient.invalidateQueries({ queryKey: ["runs-today"] }); }, [queryClient]);

  if (run.isLoading) {
    return (
      <div className="page">
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <div className="skel skel--title" style={{ width: 210 }} />
          <div className="skel" style={{ width: 82, height: 22, borderRadius: 999 }} />
        </div>
        <div className="skel skel--text" style={{ width: 340, marginBottom: 20 }} />
        <div className="split">
          <div className="card">
            <div className="skel skel--text" style={{ width: 100, marginBottom: 16 }} />
            {[110, 90, 80].map((width, index) => (
              <div key={width} style={{ display: "grid", gridTemplateColumns: "26px 1fr", gap: 12 }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div className="skel skel--node" />
                  {index < 2 && <div className="skel" style={{ width: 2, flex: 1, minHeight: 22 }} />}
                </div>
                <div style={{ paddingBottom: index < 2 ? 20 : 0 }}>
                  <div className="skel skel--text" style={{ width, marginBottom: 7 }} />
                  <div className="skel skel--text" style={{ width: "90%", height: 9 }} />
                </div>
              </div>
            ))}
          </div>
          <div className="card">
            <div className="skel skel--text" style={{ width: 80, marginBottom: 14 }} />
            <div className="skel" style={{ height: 32, borderRadius: 6, marginBottom: 8 }} />
            <div className="skel" style={{ height: 40, borderRadius: 6, marginBottom: 8 }} />
            <div className="skel" style={{ height: 40, borderRadius: 6, opacity: 0.6 }} />
          </div>
        </div>
      </div>
    );
  }
  if (run.isError || !run.data) {
    return <div className="page"><ConnectionError endpoint={`/api/runs/${runId}`} onRetry={() => run.refetch()} /></div>;
  }
  const data = run.data;
  const live = LIVE.includes(data.status);
  const ended = !live && data.status !== "succeeded";

  const entry = catalog.data?.find((candidate) => candidate.id === data.etl_id);
  const missingOutputs = entry ? entry.outputs.filter((output) =>
    !data.artifacts.some((artifact) => artifact.role === output.role)) : [];
  const declaredCount = entry?.outputs.length ?? data.artifacts.length;
  const incomplete = missingOutputs.length > 0;

  return (
    <div className="page stack" style={{ gap: 18 }}>
      <header className="page-header" style={{ marginBottom: 0 }}>
        <div className="row" style={{ marginBottom: 8 }}>
          <Link className="btn btn--ghost" to="/">Tablero</Link>
          <Link className="btn btn--ghost" to="/historial">Historial</Link>
        </div>
        <div className="row">
          <h1>{data.client} — {data.etl_id}</h1>
          {/* El polling de esta pantalla (cada 2.5s) es invisible para un lector
              de pantalla sin esto: al pasar de "En curso" a "Fallida" se
              anuncia una vez, completo. */}
          <div role="status" aria-live="polite" aria-atomic="true">
            <StatusBadge status={data.status} large />
          </div>
          <span className="mono ink-muted">{data.run_id}</span>
        </div>
        <div className="page-header__sub">
          Fecha de negocio {data.business_date} · inicio {formatMoment(data.started_at)} ·
          fin {formatMoment(data.finished_at)} · duración {formatDuration(data.started_at, data.finished_at)} ·
          <span className="mono"> {data.etl_id}</span>
        </div>
      </header>

      {live && <LiveCard run={data} />}
      {ended && <ErrorCard run={data} />}

      <div className="split">
        <Lifecycle run={data} />
        <div className="card">
          <div className="card__head">
            <span className="card__title">Artefactos</span>
            {entry && (
              <span className="tag card__tools" style={incomplete
                ? { color: "var(--status-failed-fg)", boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--status-failed-mark) 40%, transparent)" }
                : undefined}>
                {data.artifacts.length} de {declaredCount}
              </span>
            )}
          </div>
          {data.artifacts.length === 0 && !incomplete ? (
            <div className="ink-muted">
              {live ? "Los artefactos aparecen cuando la corrida termina bien."
                    : "Esta corrida no generó artefactos."}
            </div>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              {data.artifacts.map((artifact) => (
                <div key={artifact.role} className="file-row">
                  <span className="tag tag--accent">{artifact.role}</span>
                  <span className="mono">{artifact.name}</span>
                  <span className="file-row__size">{formatBytes(artifact.size)}</span>
                  <button className="btn btn--quiet btn--icon btn--sm"
                          onClick={() => downloadArtifact(data.run_id, artifact.role, artifact.name)}
                          aria-label={`Descargar ${artifact.role}`}>
                    <DownloadSimple size={14} />
                  </button>
                </div>
              ))}
              {/* El artefacto que falta se muestra como fila presente y roja, no
                  como ausencia: el rol, "no generado" y el patrón esperado. */}
              {missingOutputs.map((output) => (
                <div key={output.role} className="file-row"
                     style={{ boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--status-failed-mark) 30%, transparent)",
                              background: "color-mix(in srgb, var(--status-failed-tint) 45%, transparent)" }}>
                  <span className="tag" style={{ color: "var(--status-failed-fg)",
                    boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--status-failed-mark) 40%, transparent)" }}>{output.role}</span>
                  <span className="mono" style={{ color: "var(--status-failed-fg)" }}>no generado</span>
                  <span className="file-row__size mono">{output.glob}</span>
                </div>
              ))}
              {data.artifacts.length > 0 && (
                <button className={`btn btn--block ${incomplete ? "btn--secondary" : "btn--primary"}`}
                        style={{ marginTop: 4 }} onClick={() => downloadArtifactsZip(data.run_id)}>
                  <FileZip size={14} /> {incomplete ? "Descargar lo que hay (.zip)" : "Descargar todo (.zip)"}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <details className="evidence card">
        <summary className="card__title" style={{ cursor: "pointer" }}>Evidencia técnica (run.json)</summary>
        <div className="stack" style={{ gap: 12, marginTop: 12 }}>
          <div>
            <span className="field__label">Comando</span>
            <pre className="log">{data.command.join(" ") || "—"}</pre>
          </div>
          <div className="row" style={{ gap: 24 }}>
            <span>Exit code:{" "}
              <strong style={{ color: data.exit_code === 0 ? "var(--status-succeeded-fg)"
                : data.exit_code == null ? "inherit" : "var(--status-failed-fg)" }}>
                {data.exit_code ?? "—"}
              </strong>
            </span>
            <span>Duración: {formatDuration(data.started_at, data.finished_at)}</span>
            <span>Timeout: 900 s</span>
          </div>
          <div>
            <span className="field__label">Entradas</span>
            <table className="data-table">
              <thead><tr><th>Rol</th><th>Archivo</th><th className="num">Tamaño</th><th>SHA-256</th></tr></thead>
              <tbody>
                {data.inputs.map((input) => (
                  <tr key={input.role}>
                    <td>{input.role}</td>
                    <td className="mono">{input.name}</td>
                    <td className="num">{formatBytes(input.size)}</td>
                    <td className="mono">{input.sha256.slice(0, 16)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <span className="field__label">STDOUT (últimas líneas)</span>
            <pre className="log" tabIndex={0} aria-label="Salida estándar de la corrida">
              {data.logs.stdout_tail ? <LogLines text={data.logs.stdout_tail} /> : "—"}
            </pre>
          </div>
          {data.logs.stderr && (
            <div>
              <span className="field__label">STDERR</span>
              <pre className="log log--stderr" tabIndex={0} aria-label="Salida de error de la corrida">
                <LogLines text={data.logs.stderr} />
              </pre>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
