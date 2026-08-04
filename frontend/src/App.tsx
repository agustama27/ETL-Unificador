import { ClockCounterClockwise, FlowArrow, Play, SquaresFour, Stack } from "@phosphor-icons/react";
import { useQuery } from "@tanstack/react-query";
import { NavLink, Route, Routes } from "react-router-dom";
import { LIVE, fetchHistory, todayIso } from "./api";
import { ToastProvider } from "./components/shared";
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
