import { DownloadSimple, FileZip } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ERROR_COPY, FALLBACK_ERROR, LIVE, artifactUrl, artifactsZipUrl,
         fetchRun, formatBytes, formatDuration, formatMoment, runAction } from "../api";
import type { RunDetail } from "../api";
import { StatusBadge, TimelineIcon, useToast } from "../components/shared";

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
      <div className="mono" style={{ color: "var(--color-accent-300)", fontSize: 15 }}>
        {minutes}:{String(seconds).padStart(2, "0")}
      </div>
      <div style={{ height: 4, borderRadius: 4, background: "var(--color-neutral-900)", overflow: "hidden" }}>
        <div style={{ height: "100%", width: "35%", background: "var(--color-accent)",
                      animation: "shimmer 1.4s ease-in-out infinite" }} />
      </div>
      <div className="row">
        <Link className="btn-secondary" to="/">Volver al tablero y seguir con otro ETL</Link>
        <span className="muted">Te avisamos acá y en el tablero cuando termine.</span>
      </div>
    </div>
  );
}

function ErrorCard({ run }: { run: RunDetail }) {
  const navigate = useNavigate();
  const toast = useToast();
  const copy = (run.error_code && ERROR_COPY[run.error_code]) || FALLBACK_ERROR;
  const tone = run.status === "blocked" ? "blocked" : run.status === "timed_out" ? "timeout" : "";

  const act = async (action: "free_lock" | "notify_dev") => {
    try {
      await runAction(run.run_id, action);
      toast("success", action === "free_lock" ? "Lock liberado." : "Aviso registrado para desarrollo.");
    } catch (error) {
      toast("warning", (error as Error).message);
    }
  };

  return (
    <div className={`card error-card ${tone}`}>
      <h3>{copy.title}</h3>
      <p>{copy.what}</p>
      <p><strong>Qué hacer:</strong> {copy.todo}</p>
      <div className="row">
        {copy.actions.includes("retry") && (
          <button className="btn-primary" onClick={() => navigate(`/lanzar/${run.etl_id}`)}>Reintentar corrida</button>
        )}
        {copy.actions.includes("free_lock") && (
          <button className="btn-secondary" onClick={() => act("free_lock")}>Liberar lock</button>
        )}
        {copy.actions.includes("view_promoted") && (
          <Link className="btn-secondary" to={`/historial`}>Ver corrida promovida</Link>
        )}
        {copy.actions.includes("notify") && (
          <button className="btn-ghost" onClick={() => act("notify_dev")}>Notificar a desarrollo</button>
        )}
      </div>
      <div className="code mono">código: {run.error_code ?? "desconocido"}</div>
    </div>
  );
}

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

  const outputsLabel = { passed: "Salidas verificadas ✓", failed: "Salidas con problemas",
                         not_run: "Salidas no evaluadas" } as Record<string, string>;
  const stateLabel = { promoted: "Estado promovido", not_applicable: "Sin efecto de estado (stateless)",
                       failed: "Estado: requiere recuperación", not_started: "—",
                       staged: "Estado preparado (no promovido)" } as Record<string, string>;

  return (
    <div className="card">
      <h3>Ciclo de vida</h3>
      <div className="timeline">
        {steps.map((step, index) => (
          <div key={step.title} className="step">
            <div className="rail">
              <TimelineIcon state={step.state} />
              {index < steps.length - 1 && <span className="line" />}
            </div>
            <div className="body">
              <div className="title">{step.title}</div>
              <div className="note">{step.note}</div>
              {step.when && <div className="when mono">{formatMoment(step.when)}</div>}
            </div>
          </div>
        ))}
      </div>
      <h3 style={{ marginTop: 6 }}>Postcondiciones</h3>
      <div className="stack" style={{ gap: 6, fontSize: 12.5 }}>
        <div>{outputsLabel[run.postconditions?.outputs ?? "not_run"] ?? "Pendiente"}</div>
        <div>{stateLabel[run.postconditions?.state ?? "not_started"] ?? "—"}</div>
      </div>
    </div>
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
  useEffect(() =>

    () => { queryClient.invalidateQueries({ queryKey: ["runs-today"] }); }, [queryClient]);

  if (run.isLoading) return <div className="page stack"><div className="skeleton" /><div className="skeleton" /></div>;
  if (run.isError || !run.data) {
    return <div className="page"><div className="banner-error">No se pudo cargar la corrida. <button className="btn-secondary" onClick={() => run.refetch()}>Reintentar</button></div></div>;
  }
  const data = run.data;
  const live = LIVE.includes(data.status);
  const ended = !live && data.status !== "succeeded";

  return (
    <div className="page stack" style={{ gap: 18 }}>
      <header className="page-header" style={{ marginBottom: 0 }}>
        <div className="row" style={{ marginBottom: 8 }}>
          <Link className="btn-ghost" to="/">Tablero</Link>
          <Link className="btn-ghost" to="/historial">Historial</Link>
        </div>
        <div className="row">
          <h1>{data.client} — {data.etl_id}</h1>
          <StatusBadge status={data.status} large />
          <span className="mono muted">{data.run_id}</span>
        </div>
        <div className="subtitle">
          Fecha de negocio {data.business_date} · inicio {formatMoment(data.started_at)} ·
          fin {formatMoment(data.finished_at)} · duración {formatDuration(data.started_at, data.finished_at)} ·
          <span className="mono"> {data.etl_id}</span>
        </div>
      </header>

      {live && <LiveCard run={data} />}
      {ended && <ErrorCard run={data} />}

      <div className="two-col">
        <Lifecycle run={data} />
        <div className="card">
          <h3>Artefactos</h3>
          {data.artifacts.length === 0 ? (
            <div className="muted">
              {live ? "Los artefactos aparecen cuando la corrida termina bien."
                    : "Esta corrida no generó artefactos."}
            </div>
          ) : (
            <div className="stack" style={{ gap: 8 }}>
              <a className="btn-primary" href={artifactsZipUrl(data.run_id)} download>
                <FileZip size={14} /> Descargar todo (.zip)
              </a>
              {data.artifacts.map((artifact) => (
                <div key={artifact.role} className="filerow">
                  <span className="tag accent">{artifact.role}</span>
                  <span className="mono">{artifact.name}</span>
                  <span className="size">{formatBytes(artifact.size)}</span>
                  <a className="btn-ghost" href={artifactUrl(data.run_id, artifact.role)} download
                     aria-label={`Descargar ${artifact.role}`}>
                    <DownloadSimple size={14} />
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <details className="evidence card">
        <summary>Evidencia técnica (run.json)</summary>
        <div className="stack" style={{ gap: 12, marginTop: 12 }}>
          <div>
            <span className="field-label">Comando</span>
            <pre className="log">{data.command.join(" ") || "—"}</pre>
          </div>
          <div className="row" style={{ gap: 24 }}>
            <span>Exit code:{" "}
              <strong style={{ color: data.exit_code === 0 ? "var(--status-success)"
                : data.exit_code == null ? "inherit" : "var(--status-failed)" }}>
                {data.exit_code ?? "—"}
              </strong>
            </span>
            <span>Duración: {formatDuration(data.started_at, data.finished_at)}</span>
            <span>Timeout: 900 s</span>
          </div>
          <div>
            <span className="field-label">Entradas</span>
            <table className="history">
              <thead><tr><th>Rol</th><th>Archivo</th><th className="right">Tamaño</th><th>SHA-256</th></tr></thead>
              <tbody>
                {data.inputs.map((input) => (
                  <tr key={input.role} style={{ cursor: "default" }}>
                    <td>{input.role}</td>
                    <td className="mono">{input.name}</td>
                    <td className="right">{formatBytes(input.size)}</td>
                    <td className="mono">{input.sha256.slice(0, 16)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <span className="field-label">STDOUT (últimas líneas)</span>
            <pre className="log">{data.logs.stdout_tail || "—"}</pre>
          </div>
          {data.logs.stderr && (
            <div>
              <span className="field-label">STDERR</span>
              <pre className="log err">{data.logs.stderr}</pre>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
