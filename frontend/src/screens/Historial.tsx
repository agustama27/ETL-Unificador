import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LIVE, fetchCatalog, fetchHistory, formatDuration, formatMoment } from "../api";
import { StatusBadge } from "../components/shared";

const STATUS_FILTERS = [
  ["", "Todos los estados"], ["succeeded", "Exitosa"], ["failed", "Fallida"],
  ["timed_out", "Timeout"], ["blocked", "Bloqueada"], ["running", "En curso"],
] as const;

export default function Historial() {
  const navigate = useNavigate();
  const [client, setClient] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);

  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });
  const history = useQuery({
    queryKey: ["history", client, status, page],
    queryFn: () => fetchHistory({ client, status, page, page_size: 10 }),
    refetchInterval: (query) =>
      query.state.data?.items.some((run) => LIVE.includes(run.status)) ? 5000 : false,
  });

  const clients = [...new Set((catalog.data ?? []).map((entry) => entry.client))];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Historial</h1>
        <div className="subtitle">Todas las corridas registradas, de la más nueva a la más vieja.</div>
      </header>
      <div className="row" style={{ marginBottom: 14 }}>
        <select value={client} onChange={(event) => { setClient(event.target.value); setPage(1); }}>
          <option value="">Todos los clientes</option>
          {clients.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
          {STATUS_FILTERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <span className="spacer" />
        <span className="muted">{history.data?.total ?? "…"} corridas</span>
      </div>

      {history.isLoading ? (
        <div className="stack">{[1, 2, 3].map((n) => <div key={n} className="skeleton" />)}</div>
      ) : history.isError ? (
        <div className="banner-error">
          No se pudo cargar el historial.
          <button className="btn-secondary" onClick={() => history.refetch()}>Reintentar</button>
        </div>
      ) : (
        <>
          <table className="history">
            <thead>
              <tr>
                <th>Fecha</th><th>ETL</th><th>Cliente</th><th>Estado</th>
                <th className="right">Duración</th><th className="right"># Artefactos</th><th />
              </tr>
            </thead>
            <tbody>
              {history.data!.items.map((run) => (
                <tr key={run.run_id} onClick={() => navigate(`/runs/${run.run_id}`)}>
                  <td className="mono">{formatMoment(run.started_at)}</td>
                  <td>{run.etl_id}</td>
                  <td className="muted">{run.client}</td>
                  <td><StatusBadge status={run.status} /></td>
                  <td className="right mono">{formatDuration(run.started_at, run.finished_at)}</td>
                  <td className="right">{run.artifacts_count}</td>
                  <td className="right"><CaretRight size={13} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
            <button className="btn-ghost" disabled={page <= 1}
                    onClick={() => setPage((current) => current - 1)} aria-label="Anterior">
              <CaretLeft size={13} />
            </button>
            <span className="muted">Página {history.data!.page} de {history.data!.pages}</span>
            <button className="btn-ghost" disabled={page >= history.data!.pages}
                    onClick={() => setPage((current) => current + 1)} aria-label="Siguiente">
              <CaretRight size={13} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
