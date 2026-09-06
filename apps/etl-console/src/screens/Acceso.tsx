import { Key, Warning } from "@phosphor-icons/react";
import { useState } from "react";
import { setToken } from "../api";

interface Props {
  /** 401: falta el token o es inválido. 503: el backend no lo tiene configurado. */
  status: number;
  detalle?: string;
}

/**
 * Pantalla de acceso.
 *
 * Existe porque el backend es fail-closed y antes la única forma de cargar el token
 * era abrir DevTools y escribir en `localStorage` a mano. Cuando faltaba, todas las
 * pantallas mostraban "No se pudo cargar", que es indistinguible de un servidor caído.
 */
export default function Acceso({ status, detalle }: Props) {
  const [valor, setValor] = useState("");

  // 503 no se arregla desde el navegador: el servidor arranca sin ETL_CONSOLE_TOKEN
  // y rechaza todo /api. Pedir un token acá sería mandar al usuario a una pared.
  if (status === 503) {
    return (
      <div className="page stack">
        <div className="error-card">
          <h2 className="row"><Warning size={18} /> El servidor no tiene autenticación configurada</h2>
          <p className="muted">
            La API responde 503 a todo <span className="mono">/api</span> porque arrancó sin
            <span className="mono"> ETL_CONSOLE_TOKEN</span>. Es fail-closed a propósito: no se
            resuelve desde el navegador.
          </p>
          <p className="muted">
            Quien administre el despliegue tiene que definir la variable en el
            <span className="mono"> .env</span> del stack y reiniciar el servicio.
          </p>
          {detalle && <p className="mono muted">{detalle}</p>}
        </div>
      </div>
    );
  }

  const guardar = (evento: React.FormEvent) => {
    evento.preventDefault();
    if (!valor.trim()) return;
    setToken(valor);
    // Recarga completa: react-query ya tiene queries fallidas cacheadas y reintentarlas
    // una por una deja la UI a medio camino.
    window.location.reload();
  };

  return (
    <div className="page stack">
      <div className="launch-card">
        <h2 className="row"><Key size={18} /> Acceso a la consola</h2>
        <p className="muted">
          La API pide un token. Se guarda en este navegador y se envía en cada pedido.
        </p>

        <form onSubmit={guardar} className="stack">
          <label className="field-label" htmlFor="token">Token de acceso</label>
          <input
            id="token"
            type="text"
            className="mono"
            autoComplete="off"
            spellCheck={false}
            placeholder="Pegar el token"
            value={valor}
            onChange={(e) => setValor(e.target.value)}
          />
          <div className="row">
            <button type="submit" className="btn-primary" disabled={!valor.trim()}>
              Guardar y entrar
            </button>
          </div>
        </form>

        {detalle && (
          <div className="note-warn">
            El servidor rechazó el token anterior: <span className="mono">{detalle}</span>
          </div>
        )}

        <div className="note-info">
          El token lo genera el despliegue. Si no lo tenés, pedíselo a quien administre el
          servidor; está en el <span className="mono">.env</span> del stack.
        </div>
      </div>
    </div>
  );
}
