import { Download, Play } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LIVE, downloadArtifactsZip, fetchCatalog, fetchHistory, todayIso } from "../api";
import type { RunStatus, RunSummary } from "../api";
import { StatusBadge, useToast } from "../components/shared";

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

  if (catalog.isLoading || runs.isLoading) {
    return <div className="page stack">{[1, 2, 3, 4].map((n) => <div key={n} className="skeleton" />)}</div>;
  }
  if (catalog.isError || runs.isError) {
    return (
      <div className="page">
        <div className="banner-error">
          No se pudo cargar el tablero.
          <button className="btn-secondary" onClick={() => { catalog.refetch(); runs.refetch(); }}>Reintentar</button>
        </div>
      </div>
    );
  }

  const executables = (catalog.data ?? []).filter((entry) => entry.executable);
  const latestByEtl = new Map<string, RunSummary>();
  for (const run of runs.data?.items ?? []) {
    if (!latestByEtl.has(run.etl_id)) latestByEtl.set(run.etl_id, run);
  }
  const okEtls = new Set([...latestByEtl.values()].filter((r) => r.status === "succeeded").map((r) => r.etl_id));
  const liveCount = [...latestByEtl.values()].filter((r) => LIVE.includes(r.status)).length;
  const troubleCount = [...latestByEtl.values()]
    .filter((r) => ["failed", "timed_out", "blocked"].includes(r.status)).length;
  const pendingCount = executables.filter((e) => !latestByEtl.has(e.id)).length;

  const clients = [...new Set(executables.map((entry) => entry.client))];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Tablero del día</h1>
        <div className="subtitle">{longDate()} · fecha de negocio fija en hoy</div>
      </header>
      <div className="chips">
        <div className="chip success"><span className="value">{okEtls.size}</span><span className="label">Exitosos hoy</span></div>
        <div className="chip running"><span className="value">{liveCount}</span><span className="label">En curso</span></div>
        <div className="chip trouble"><span className="value">{troubleCount}</span><span className="label">Con problemas</span></div>
        <div className="chip"><span className="value">{pendingCount}</span><span className="label">Pendientes</span></div>
      </div>
      {clients.map((client) => (
        <section key={client}>
          <div className="group-title">{client}</div>
          {executables.filter((entry) => entry.client === client).map((entry) => {
            const run = latestByEtl.get(entry.id);
            const status = run?.status ?? "pending";
            const meta = run
              ? `Última: ${run.started_at ?? "—"}${run.finished_at ? ` → ${run.finished_at}` : ""}${run.error_code ? ` · ${run.error_code}` : ""}`
              : entry.deadline_hint ?? "Sin corridas hoy";
            const runLabel = run ? (run.status === "succeeded" ? "Re-ejecutar"
              : LIVE.includes(run.status) ? null : "Reintentar") : "Ejecutar";
            return (
              <div key={entry.id} className="etl-row">
                <div>
                  <div className="name">{entry.name}</div>
                  <div className="id mono">{entry.id}</div>
                </div>
                <StatusBadge status={status} />
                <div className="meta">{meta}</div>
                <div className="actions">
                  {run && <Link className="btn-ghost" to={`/runs/${run.run_id}`}>Ver corrida</Link>}
                  {run?.status === "succeeded" && (
                    <button className="btn-secondary" onClick={() => downloadArtifactsZip(run.run_id)}>
                      <Download size={13} /> Descargar
                    </button>
                  )}
                  {runLabel && (
                    <button className="btn-primary" onClick={() => navigate(`/lanzar/${entry.id}`)}>
                      <Play size={13} /> {runLabel}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}
