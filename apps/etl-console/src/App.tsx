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
  const item = "";
  return (
    <aside className="sidebar">
      <div className="brand row"><FlowArrow size={17} color="var(--color-accent)" /> Consola ETL</div>
      <nav>
        <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : item)}>
          <SquaresFour size={15} /> Tablero
          {liveCount > 0 && <span className="live-pill">{liveCount}</span>}
        </NavLink>
        <NavLink to="/catalogo" className={({ isActive }) => (isActive ? "active" : item)}>
          <Stack size={15} /> Catálogo
        </NavLink>
        <NavLink to="/lanzar" className={({ isActive }) => (isActive ? "active" : item)}>
          <Play size={15} /> Lanzar corrida
        </NavLink>
        <NavLink to="/historial" className={({ isActive }) => (isActive ? "active" : item)}>
          <ClockCounterClockwise size={15} /> Historial
        </NavLink>
      </nav>
      <div className="user">
        <span className="avatar">OS</span>
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
      <div className="layout">
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
