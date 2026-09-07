import { CaretLeft, CaretRight } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
        <div className="page-header__sub">Todas las corridas registradas, de la más nueva a la más vieja.</div>
      </header>
      <div className="row" style={{ marginBottom: 14 }}>
        <select className="select" value={client} onChange={(event) => { setClient(event.target.value); setPage(1); }}>
          <option value="">Todos los clientes</option>
          {clients.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <select className="select" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
          {STATUS_FILTERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <span className="spacer" />
        <span className="ink-muted">{history.data?.total ?? "…"} corridas</span>
      </div>

      {history.isLoading ? (
        <div className="stack">{[1, 2, 3].map((n) => <div key={n} className="skeleton" />)}</div>
      ) : history.isError ? (
        <div className="banner-error">
          No se pudo cargar el historial.
          <button className="btn btn--secondary" onClick={() => history.refetch()}>Reintentar</button>
        </div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th><th>ETL</th><th>Cliente</th><th>Estado</th><th>Error</th>
                <th className="num">Duración</th><th className="num"># Artefactos</th><th />
              </tr>
            </thead>
            <tbody>
              {history.data!.items.map((run) => (
                // La fila navega por comodidad del mouse (onClick + data-clickable), pero el
                // enlace real está en la primera celda: es lo único alcanzable por teclado y
                // anunciado por un lector de pantalla — hoy el <tr> con onClick no lo era.
                <tr key={run.run_id} data-status={run.status} data-clickable
                    onClick={() => navigate(`/runs/${run.run_id}`)}>
                  <td className="mono">
                    <Link to={`/runs/${run.run_id}`} className="row-link">{formatMoment(run.started_at)}</Link>
                  </td>
                  <td>{run.etl_id}</td>
                  <td className="ink-muted">{run.client}</td>
                  <td><StatusBadge status={run.status} /></td>
                  <td className="mono ink-muted">{run.error_code ?? "—"}</td>
                  <td className="num mono">{formatDuration(run.started_at, run.finished_at)}</td>
                  <td className="num">{run.artifacts_count}</td>
                  <td className="num"><CaretRight size={13} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
            <button className="btn btn--ghost" disabled={page <= 1}
                    onClick={() => setPage((current) => current - 1)} aria-label="Anterior">
              <CaretLeft size={13} />
            </button>
            <span className="ink-muted">Página {history.data!.page} de {history.data!.pages}</span>
            <button className="btn btn--ghost" disabled={page >= history.data!.pages}
                    onClick={() => setPage((current) => current + 1)} aria-label="Siguiente">
              <CaretRight size={13} />
            </button>
          </div>
        </>
      )}
    </div>
  );
}
