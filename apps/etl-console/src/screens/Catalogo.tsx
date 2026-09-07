import { Play, Stack } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchCatalog } from "../api";
import { ConnectionError, Empty, InertRow, ReadinessBadge } from "../components/shared";

export default function Catalogo() {
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });

  // El skeleton copia la geometría de lo que reemplaza: título+subtítulo y
  // dos grupos de filas.
  if (catalog.isLoading) {
    return (
      <div className="page">
        <div className="skel skel--title" style={{ width: 160, marginBottom: 8 }} />
        <div className="skel skel--text" style={{ width: 320, marginBottom: 24 }} />
        <div className="skel skel--text" style={{ width: 90, marginBottom: 12 }} />
        <div className="etl-list" style={{ marginBottom: 24 }}>
          <div className="skel skel--row" />
          <div className="skel skel--row" style={{ opacity: 0.75 }} />
        </div>
        <div className="skel skel--text" style={{ width: 90, marginBottom: 12 }} />
        <div className="etl-list">
          <div className="skel skel--row" style={{ opacity: 0.5 }} />
        </div>
      </div>
    );
  }
  if (catalog.isError) {
    return <div className="page"><ConnectionError endpoint="/api/catalog" onRetry={() => catalog.refetch()} /></div>;
  }

  const entries = catalog.data ?? [];
  if (entries.length === 0) {
    return (
      <div className="page">
        <header className="page-header">
          <h1>Catálogo</h1>
        </header>
        <Empty icon={<Stack size={32} aria-hidden="true" />} title="El catálogo está vacío"
               body="Todavía no hay ningún ETL declarado en el unificador." />
      </div>
    );
  }
  const clients = [...new Set(entries.map((entry) => entry.client))];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Catálogo</h1>
        <div className="page-header__sub">Las {entries.length} entradas declaradas del unificador, ejecutables e inertes.</div>
      </header>
      {clients.map((client) => {
        const group = entries.filter((entry) => entry.client === client);
        return (
          <section key={client}>
            <div className="section-head">
              <span className="section-head__label">{client}</span>
              <span className="section-head__count">{group.length} entradas</span>
              <span className="section-head__rule" />
            </div>
            <div className="etl-list">
              {group.map((entry) => (
                <div key={entry.id} className="etl-row" style={entry.executable ? undefined : { opacity: 0.72 }}>
                  <div>
                    <div className="etl-row__name">{entry.name}</div>
                    <div className="etl-row__id mono">{entry.id}</div>
                  </div>
                  <ReadinessBadge readiness={entry.readiness} />
                  <div className="etl-row__meta">
                    {entry.executable ? (
                      <>
                        <div>
                          Entradas: {entry.inputs.map((input) =>
                            `${input.role} (${input.extensions.join(", ")}${input.required ? "" : ", opcional"})`).join(", ")}
                        </div>
                        <div>Salidas: {entry.outputs.map((output) => output.role.toUpperCase()).join(", ")}</div>
                      </>
                    ) : (
                      <InertRow entry={entry} />
                    )}
                  </div>
                  <div className="etl-row__actions">
                    {entry.executable ? (
                      <button className="btn btn--primary" onClick={() => navigate(`/lanzar/${entry.id}`)}>
                        <Play size={13} /> Ejecutar
                      </button>
                    ) : (
                      <span className="tag">No ejecutable</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
