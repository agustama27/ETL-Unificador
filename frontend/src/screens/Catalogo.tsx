import { Play } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchCatalog } from "../api";
import { InertRow, ReadinessBadge } from "../components/shared";

export default function Catalogo() {
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });

  if (catalog.isLoading) {
    return <div className="page stack">{[1, 2, 3].map((n) => <div key={n} className="skeleton" />)}</div>;
  }
  if (catalog.isError) {
    return (
      <div className="page">
        <div className="banner-error">
          No se pudo cargar el catálogo.
          <button className="btn-secondary" onClick={() => catalog.refetch()}>Reintentar</button>
        </div>
      </div>
    );
  }

  const entries = catalog.data ?? [];
  const clients = [...new Set(entries.map((entry) => entry.client))];

  return (
    <div className="page">
      <header className="page-header">
        <h1>Catálogo</h1>
        <div className="subtitle">Las {entries.length} entradas declaradas del unificador, ejecutables e inertes.</div>
      </header>
      {clients.map((client) => {
        const group = entries.filter((entry) => entry.client === client);
        return (
          <section key={client}>
            <div className="group-title">
              {client} <span className="count">{group.length} entradas</span>
            </div>
            {group.map((entry) => (
              <div key={entry.id} className={`etl-row${entry.executable ? "" : " inert"}`}>
                <div>
                  <div className="name">{entry.name}</div>
                  <div className="id mono">{entry.id}</div>
                </div>
                <ReadinessBadge readiness={entry.readiness} />
                <div className="meta">
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
                <div className="actions">
                  {entry.executable ? (
                    <button className="btn-primary" onClick={() => navigate(`/lanzar/${entry.id}`)}>
                      <Play size={13} /> Ejecutar
                    </button>
                  ) : (
                    <span className="tag">No ejecutable</span>
                  )}
                </div>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
