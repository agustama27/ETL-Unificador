import { Download, Play, SunHorizon, WarningOctagon } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LIVE, downloadArtifactsZip, fetchCatalog, fetchHistory, todayIso } from "../api";
import type { RunStatus, RunSummary } from "../api";
import { ConnectionError, Empty, StatusBadge, useToast } from "../components/shared";

// Tinta de .etl-row__meta en una fila con problema: el error_code se lee sin
// abrir la corrida. Sólo estos tres estados cuentan como "con problemas".
const TROUBLE_TINT: Partial<Record<RunStatus, string>> = {
  failed: "var(--status-failed-fg)",
  timed_out: "var(--status-timed-out-fg)",
  blocked: "var(--status-blocked-fg)",
};

const longDate = () => {
  const text = new Date().toLocaleDateString("es-AR",
    { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
};

export default function Tablero() {
  const navigate = useNavigate();
  const toast = useToast();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });
  const runs = useQuery({
    queryKey: ["runs-today"],
    queryFn: () => fetchHistory({ business_date: todayIso(), page_size: 200 }),
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => LIVE.includes(run.status)) ? 5000 : false,
  });

  const seen = useRef(new Map<string, RunStatus>());
  useEffect(() => {
    for (const run of runs.data?.items ?? []) {
      const before = seen.current.get(run.run_id);
      if (before && LIVE.includes(before) && !LIVE.includes(run.status)) {
        toast(run.status === "succeeded" ? "success" : "warning",
              run.status === "succeeded"
                ? `${run.etl_id}: corrida exitosa.`
                : `${run.etl_id}: la corrida terminó ${run.status === "blocked" ? "bloqueada" : "con problemas"}.`,
              run.run_id);
      }
      seen.current.set(run.run_id, run.status);
    }
  }, [runs.data, toast]);

  // El skeleton copia la geometría de lo que reemplaza: título+subtítulo, la
  // grilla de métricas con el líder más grande, y dos grupos de filas — si la
  // página salta cuando llegan los datos, el skeleton está mal.
  if (catalog.isLoading || runs.isLoading) {
    return (
      <div className="page">
        <div className="skel skel--title" style={{ width: 180, marginBottom: 8 }} />
        <div className="skel skel--text" style={{ width: 280, marginBottom: 24 }} />
        <div className="metric-row" style={{ gridTemplateColumns: "1.35fr 1fr 1fr 1fr", marginBottom: 28 }}>
          <div className="skel skel--metric" style={{ height: 86 }} />
          <div className="skel skel--metric" />
          <div className="skel skel--metric" />
          <div className="skel skel--metric" />
        </div>
        <div className="skel skel--text" style={{ width: 90, marginBottom: 12 }} />
        <div className="etl-list" style={{ marginBottom: 24 }}>
          <div className="skel skel--row" />
          <div className="skel skel--row" style={{ opacity: 0.75 }} />
          <div className="skel skel--row" style={{ opacity: 0.5 }} />
        </div>
        <div className="skel skel--text" style={{ width: 70, marginBottom: 12 }} />
        <div className="etl-list">
          <div className="skel skel--row" style={{ opacity: 0.4 }} />
          <div className="skel skel--row" style={{ opacity: 0.28 }} />
        </div>
      </div>
    );
  }
  if (catalog.isError || runs.isError) {
    return (
      <div className="page">
        <ConnectionError
          endpoint={[catalog.isError && "/api/catalog", runs.isError && "/api/runs"].filter(Boolean).join(", ")}
          onRetry={() => { catalog.refetch(); runs.refetch(); }}
        />
      </div>
    );
  }

  const executables = (catalog.data ?? []).filter((entry) => entry.executable);
  if (executables.length === 0) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Tablero del día</h1>
          <div className="page-header__sub">{longDate()} · fecha de negocio fija en hoy</div>
        </header>
        <Empty
          icon={<SunHorizon size={32} aria-hidden="true" />}
          title="Todavía no corrió nada hoy"
          body="El catálogo no tiene ningún ETL ejecutable programado para hoy."
          actions={<Link className="btn btn--ghost" to="/catalogo">Ver el catálogo</Link>}
        />
      </div>
    );
  }
  const latestByEtl = new Map<string, RunSummary>();
  for (const run of runs.data?.items ?? []) {
    if (!latestByEtl.has(run.etl_id)) latestByEtl.set(run.etl_id, run);
  }
  const okEtls = new Set([...latestByEtl.values()].filter((r) => r.status === "succeeded").map((r) => r.etl_id));
  const runningRuns = [...latestByEtl.values()].filter((r) => LIVE.includes(r.status));
  const troubleRuns = [...latestByEtl.values()]
    .filter((r) => ["failed", "timed_out", "blocked"].includes(r.status));
  const liveCount = runningRuns.length;
  const troubleCount = troubleRuns.length;
  const pendingEtls = executables.filter((e) => !latestByEtl.has(e.id));
  const pendingCount = pendingEtls.length;

  const clients = [...new Set(executables.map((entry) => entry.client))];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Tablero del día</h1>
        <div className="page-header__sub">{longDate()} · fecha de negocio fija en hoy</div>
      </header>

      {/* Máximo un .metric--lead por pantalla: "Con problemas" es la única cifra
          que dispara una acción, y va primero en la grilla 1.35fr 1fr 1fr 1fr. */}
      <div className="metric-row" style={{ gridTemplateColumns: "1.35fr 1fr 1fr 1fr" }}>
        <div className="metric metric--lead" data-status={troubleCount > 0 ? "trouble" : "pending"}>
          <span className="metric__label">Con problemas</span>
          <span className="metric__value">{troubleCount}</span>
          <span className="metric__foot">
            {troubleCount > 0 ? troubleRuns.map((r) => r.etl_id).join(" · ") : "nada que atender"}
          </span>
        </div>
        <div className="metric" data-status="succeeded">
          <span className="metric__label">Exitosos hoy</span>
          <span className="metric__value">{okEtls.size}</span>
          <span className="metric__foot">de {executables.length} programados</span>
        </div>
        <div className="metric" data-status="running">
          <span className="metric__label">En curso</span>
          <span className="metric__value">{liveCount}</span>
          <span className="metric__foot">
            {liveCount > 0 ? runningRuns.map((r) => r.etl_id).join(" · ") : "sin corridas en curso"}
          </span>
        </div>
        <div className="metric" data-status="pending">
          <span className="metric__label">Pendientes</span>
          <span className="metric__value">{pendingCount}</span>
          <span className="metric__foot">
            {pendingCount > 0 ? pendingEtls.map((e) => e.id).join(" · ") : "todo lanzado hoy"}
          </span>
        </div>
      </div>

      {troubleCount > 0 && (
        <div className="notice notice--danger" style={{ marginTop: 16 }}>
          <WarningOctagon size={17} className="notice__icon" aria-hidden="true" />
          <div style={{ flex: 1 }}>
            <div className="notice__title">
              {troubleCount} {troubleCount === 1 ? "ETL necesita" : "ETL necesitan"} tu atención
            </div>
            <span className="ink-muted">
              {troubleRuns.map((r) => `${r.etl_id}${r.error_code ? ` · ${r.error_code}` : ""}`).join("  —  ")}
            </span>
          </div>
          <Link className="btn btn--secondary" to={`/runs/${troubleRuns[0].run_id}`}>Ver detalle</Link>
        </div>
      )}

      {clients.map((client) => {
        const group = executables.filter((entry) => entry.client === client);
        return (
          <section key={client}>
            <div className="section-head">
              <span className="section-head__label">{client}</span>
              <span className="section-head__count">{group.length} ETL</span>
              <span className="section-head__rule" />
            </div>
            <div className="etl-list">
              {group.map((entry) => {
                const run = latestByEtl.get(entry.id);
                const status = run?.status ?? "pending";
                const meta = run
                  ? `Última: ${run.started_at ?? "—"}${run.finished_at ? ` → ${run.finished_at}` : ""}${run.error_code ? ` · ${run.error_code}` : ""}`
                  : entry.deadline_hint ?? "Sin corridas hoy";
                const runLabel = run ? (run.status === "succeeded" ? "Re-ejecutar"
                  : LIVE.includes(run.status) ? null : "Reintentar") : "Ejecutar";
                const tint = run && TROUBLE_TINT[run.status];
                return (
                  <div key={entry.id} className="etl-row" data-status={status}>
                    <div>
                      <div className="etl-row__name">{entry.name}</div>
                      <div className="etl-row__id mono">{entry.id}</div>
                    </div>
                    <StatusBadge status={status} />
                    <div className="etl-row__meta" style={tint ? { color: tint } : undefined}>{meta}</div>
                    <div className="etl-row__actions">
                      {run && <Link className="btn btn--ghost" to={`/runs/${run.run_id}`}>Ver corrida</Link>}
                      {run?.status === "succeeded" && (
                        <button className="btn btn--secondary" onClick={() => downloadArtifactsZip(run.run_id)}>
                          <Download size={13} /> Descargar
                        </button>
                      )}
                      {runLabel && (
                        <button className="btn btn--primary" onClick={() => navigate(`/lanzar/${entry.id}`)}>
                          <Play size={13} /> {runLabel}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
