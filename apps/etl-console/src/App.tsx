import { ClockCounterClockwise, FlowArrow, Play, SquaresFour, Stack } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";
import { useEffect, useState } from "react";
import { ACCESO_DENEGADO, LIVE, clearToken, fetchHistory, getToken, todayIso } from "./api";
import { ToastProvider } from "./components/shared";
import Acceso from "./screens/Acceso";
import Catalogo from "./screens/Catalogo";
import DetalleCorrida from "./screens/DetalleCorrida";
import Historial from "./screens/Historial";
import Lanzador from "./screens/Lanzador";
import Tablero from "./screens/Tablero";

function Sidebar() {
  const runs = useQuery({
    queryKey: ["runs-today"],
    queryFn: () => fetchHistory({ business_date: todayIso(), page_size: 200 }),
    refetchInterval: 5000,
  });
  const liveCount = (runs.data?.items ?? []).filter((run) => LIVE.includes(run.status)).length;
  // NavLink ya emite aria-current="page" en la ruta activa, que es de donde la hoja
  // toma el estado (.nav-item[aria-current="page"]): no hace falta clase "active".
  return (
    <aside className="sidebar">
      <div className="sidebar__brand"><FlowArrow size={17} color="var(--brand-base)" /> Consola ETL</div>
      <nav className="sidebar__nav">
        <NavLink to="/" end className="nav-item">
          <SquaresFour size={15} /> Tablero
          {liveCount > 0 && <span className="nav-item__pill">{liveCount}</span>}
        </NavLink>
        <NavLink to="/catalogo" className="nav-item">
          <Stack size={15} /> Catálogo
        </NavLink>
        <NavLink to="/lanzar" className="nav-item">
          <Play size={15} /> Lanzar corrida
        </NavLink>
        <NavLink to="/historial" className="nav-item">
          <ClockCounterClockwise size={15} /> Historial
        </NavLink>
      </nav>
      <div className="sidebar__user">
        <span className="sidebar__avatar">OS</span>
        <span>Operaciones SOHO<br />Red interna · sin sesión</span>
      </div>
    </aside>
  );
}

export default function App() {
  // Sin token no se dispara ni un pedido: mostrar cuatro pantallas con "No se pudo
  // cargar" cuando lo que falta es la credencial es indistinguible de un servidor caido.
  const [acceso, setAcceso] = useState<{ status: number; detalle?: string } | null>(
    () => (getToken() ? null : { status: 401 }),
  );

  useEffect(() => {
    const alDenegar = (evento: Event) => {
      const { status, detalle } = (evento as CustomEvent).detail ?? {};
      // Un token rechazado no sirve para el proximo pedido: se descarta.
      if (status === 401) clearToken();
      setAcceso({ status, detalle });
    };
    window.addEventListener(ACCESO_DENEGADO, alDenegar);
    return () => window.removeEventListener(ACCESO_DENEGADO, alDenegar);
  }, []);

  if (acceso) return <Acceso status={acceso.status} detalle={acceso.detalle} />;

  return (
    <ToastProvider>
      <div className="shell">
        <Sidebar />
        <main className="content">
          <Routes>
            <Route path="/" element={<Tablero />} />
            <Route path="/catalogo" element={<Catalogo />} />
            <Route path="/lanzar" element={<Lanzador />} />
            <Route path="/lanzar/:etlId" element={<Lanzador />} />
            <Route path="/runs/:runId" element={<DetalleCorrida />} />
            <Route path="/historial" element={<Historial />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  );
}
