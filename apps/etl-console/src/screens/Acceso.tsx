import { Copy, Info, Key, Warning, WarningOctagon } from "@phosphor-icons/react";
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
  const [copied, setCopied] = useState(false);

  // 503 no se arregla desde el navegador: el servidor arranca sin ETL_CONSOLE_TOKEN
  // y rechaza todo /api. Quien ve esta pantalla no es quien la puede arreglar — lo
  // único útil es pasar el diagnóstico exacto a quien sí puede.
  if (status === 503) {
    const diagnostic = `503 · ETL_CONSOLE_TOKEN no configurado${detalle ? ` · ${detalle}` : ""}`;
    return (
      <div className="page stack">
        <div className="card" style={{ boxShadow: "inset 3px 0 0 var(--status-failed-mark), var(--elevation-2)" }}>
          <div className="card__head">
            <WarningOctagon size={18} color="var(--status-failed-fg)" aria-hidden="true" />
            <span className="card__title">El servidor no tiene autenticación configurada</span>
          </div>
          <p className="ink-secondary">
            La API responde 503 a todo <span className="mono">/api</span> porque arrancó sin
            <span className="mono"> ETL_CONSOLE_TOKEN</span>. Es fail-closed a propósito: no se
            resuelve desde el navegador.
          </p>
          <p className="ink-secondary">
            Quien administre el despliegue tiene que definir la variable en el
            <span className="mono"> .env</span> del stack y reiniciar el servicio.
          </p>
          <pre className="log" style={{ marginTop: 12 }}>{diagnostic}</pre>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn btn--quiet" onClick={() => {
              navigator.clipboard?.writeText(diagnostic).then(() => {
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              });
            }}>
              <Copy size={13} aria-hidden="true" /> {copied ? "Copiado" : "Copiar diagnóstico"}
            </button>
          </div>
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
  const sinToken = !valor.trim();

  return (
    <div className="page stack">
      <div className="card">
        <div className="card__head">
          <Key size={18} aria-hidden="true" />
          <span className="card__title">Acceso a la consola</span>
        </div>
        <p className="ink-secondary">
          La API pide un token. Se guarda en este navegador y se envía en cada pedido.
        </p>

        {detalle && (
          <div className="notice notice--warning" style={{ marginBottom: 12 }}>
            <Warning size={16} className="notice__icon" aria-hidden="true" />
            <div>El servidor rechazó el token anterior: <span className="mono">{detalle}</span></div>
          </div>
        )}

        <form onSubmit={guardar} className="stack">
          <div>
            <label className="field__label" htmlFor="token">Token de acceso</label>
            <input
              id="token"
              type="text"
              className="input mono"
              autoComplete="off"
              spellCheck={false}
              placeholder="Pegar el token"
              value={valor}
              onChange={(e) => setValor(e.target.value)}
            />
          </div>
          <div className="row">
            {/* disabled real saldría del orden de tabulación: el motivo tiene que
                llegar también a quien navega con teclado. */}
            <button type="submit" className="btn btn--primary"
                    aria-disabled={sinToken} aria-describedby={sinToken ? "token-hint" : undefined}>
              Guardar y entrar
            </button>
            {sinToken && <span id="token-hint" className="ink-subtle" style={{ fontSize: 12 }}>Pegá el token para continuar</span>}
          </div>
        </form>

        <div className="notice notice--info" style={{ marginTop: 12 }}>
          <Info size={16} className="notice__icon" aria-hidden="true" />
          <div>El token lo genera el despliegue. Si no lo tenés, pedíselo a quien administre el
            servidor; está en el <span className="mono">.env</span> del stack.</div>
        </div>
      </div>
    </div>
  );
}
