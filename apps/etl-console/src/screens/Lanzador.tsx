import { Check, Database, File as FileIcon, Info, UploadSimple, X } from "@phosphor-icons/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchCatalog, formatBytes, launchRun, todayIso } from "../api";
import type { CatalogEntry, InputSpec } from "../api";
import { Dialog, useToast } from "../components/shared";

function Dropzone({ spec, file, onFile, onClear, onError }: {
  spec: InputSpec; file: File | undefined;
  onFile: (file: File) => void; onClear: () => void; onError: (message: string) => void;
}) {
  const [over, setOver] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const accept = spec.extensions.join(",");

  const take = (candidate: File | undefined) => {
    if (!candidate) return;
    const suffix = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!spec.extensions.map((ext) => ext.toLowerCase()).includes(suffix)) {
      setInvalid(true);
      onError(`Extensión inválida para ${spec.role}: se espera ${spec.extensions.join(", ")}`);
      return;
    }
    setInvalid(false);
    onFile(candidate);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    take(event.dataTransfer.files?.[0]);
  };

  if (file) {
    return (
      <div className="file-row">
        <FileIcon size={15} aria-hidden="true" />
        <span className="mono">{file.name}</span>
        <span className="file-row__size">{formatBytes(file.size)}</span>
        <button className="btn btn--ghost btn--icon btn--sm" onClick={onClear} aria-label={`Quitar ${spec.role}`}>
          <X size={12} aria-hidden="true" />
        </button>
      </div>
    );
  }
  return (
    // El input real queda oculto con .sr-only, no display:none: el drop sigue
    // funcionando sobre el label, y el click y el foco los da el input nativo.
    <label className="dropzone" data-over={over} data-error={invalid}
           onDragOver={(event) => { event.preventDefault(); setOver(true); }}
           onDragLeave={() => setOver(false)} onDrop={onDrop}>
      <input type="file" accept={accept} className="sr-only"
             onChange={(event) => take(event.target.files?.[0] ?? undefined)} />
      <UploadSimple size={22} className="dropzone__icon" aria-hidden="true" />
      <span className="dropzone__role">{spec.role}</span>
      <span className="dropzone__req">{spec.required ? "Obligatorio" : "Opcional"} · {spec.extensions.join(" ")}</span>
      <span className="dropzone__hint">Arrastrá el archivo acá o hacé clic para elegirlo</span>
    </label>
  );
}

function resolveOutputName(glob: string, dateFormat: string | null) {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const yyyy = now.getFullYear(), mm = pad(now.getMonth() + 1), dd = pad(now.getDate());
  const stamp = dateFormat === "YYMMDD" ? `${String(yyyy).slice(2)}${mm}${dd}`
    : dateFormat === "DDMMYYYY" ? `${dd}${mm}${yyyy}` : `${yyyy}${mm}${dd}`;
  return glob.replace("*", dateFormat ? stamp : "").replace(/_$/, "");
}

function Formulario({ entry }: { entry: CatalogEntry }) {
  const navigate = useNavigate();
  const toast = useToast();
  const [files, setFiles] = useState<Record<string, File>>({});
  const [noPlanes, setNoPlanes] = useState(false);
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const missing = entry.inputs.filter((spec) => spec.required && !files[spec.role]);
  const launch = useMutation({
    mutationFn: () => launchRun(entry.id, todayIso(), files,
                                noPlanes ? { no_planes_today: true } : {}),
    onSuccess: (result) => {
      toast("info", `${entry.name}: corrida iniciada.`, result.run_id);
      navigate(`/runs/${result.run_id}`);
    },
    onError: (error: Error) => setInlineError(error.message),
  });
  // El dialog se gasta sólo en lo irreversible: promover estado mensual. Todo
  // ETL sin estado (la mayoría) ejecuta directo, sin interrumpir.
  const ejecutar = () => { if (entry.stateful) setConfirming(true); else launch.mutate(); };
  const mesLargo = new Date().toLocaleDateString("es-AR", { month: "long", year: "numeric" });

  return (
    <div className="split">
      <div className="stack">
        <div>
          <span className="field__label">Fecha de negocio</span>
          <div className="row">
            <input type="text" disabled className="input" value={`${todayIso()} (hoy)`} />
            <span className="tag tag--accent">Fija en HOY</span>
          </div>
          <div className="notice notice--info" style={{ marginTop: 8 }}>
            <Info size={13} className="notice__icon" aria-hidden="true" />
            <div>Regla del sistema: solo se acepta la fecha de negocio de hoy. Los nombres de los
              archivos de salida se generan con la fecha del sistema.</div>
          </div>
        </div>
        {entry.inputs.map((spec) => (
          <Dropzone key={spec.role} spec={spec} file={files[spec.role]}
                    onFile={(file) => { setInlineError(null); setFiles((c) => ({ ...c, [spec.role]: file })); }}
                    onClear={() => setFiles(({ [spec.role]: _omit, ...rest }) => rest)}
                    onError={setInlineError} />
        ))}
        {entry.params.includes("no_planes_today") && (
          <label className="check" style={{ fontSize: 12.5 }}>
            <input type="checkbox" checked={noPlanes} onChange={(e) => setNoPlanes(e.target.checked)} />
            <span className="check__box"><Check size={11} weight="bold" aria-hidden="true" /></span>
            <span>
              <strong>Hoy no hay archivo de PLANES.</strong>{" "}
              Ejecuta sin cruce de planes. Queda registrado en la evidencia de la corrida.
            </span>
          </label>
        )}
        {inlineError && (
          <div className="notice notice--danger">
            <X size={16} className="notice__icon" aria-hidden="true" />
            <div>{inlineError}</div>
          </div>
        )}
        <div className="row">
          <button className="btn btn--primary" disabled={missing.length > 0 || launch.isPending}
                  onClick={ejecutar}>
            Ejecutar ahora
          </button>
          {missing.length > 0
            ? <span style={{ fontSize: 12, color: "var(--feedback-warning-fg)" }}>
                Falta el archivo requerido: {missing.map((s) => s.role).join(", ")}
              </span>
            : <span className="ink-muted">Listo para ejecutar · tiempo máximo 15 min</span>}
        </div>
      </div>
      <div className="card">
        <div className="card__head"><span className="card__title">Qué va a pasar</span></div>
        <div className="stack" style={{ gap: 10 }}>
          <div className="ink-muted">La corrida tiene un tiempo máximo de 15 minutos; si lo supera, se interrumpe.</div>
          {entry.stateful && (
            <div className="notice notice--warning">
              <Database size={14} className="notice__icon" aria-hidden="true" />
              <div>ETL con estado mensual: al terminar bien, promueve un snapshot del día y no permite re-ejecutar hoy.</div>
            </div>
          )}
          <div className="ink-muted">
            Toda la corrida queda registrada con evidencia inmutable: comando, hashes de entrada, logs y artefactos.
          </div>
          <div>
            <span className="field__label">Salidas esperadas</span>
            <div className="stack" style={{ gap: 6 }}>
              {entry.outputs.map((output) => (
                <div key={output.role} className="row">
                  <span className="tag tag--accent">{output.role}</span>
                  <span className="mono">{resolveOutputName(output.glob, output.date_format)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Dialog open={confirming} tone="warning" icon={<Database size={20} aria-hidden="true" />}
              title={`Esto cierra ${mesLargo}`} confirmLabel="Ejecutar y promover"
              onClose={() => setConfirming(false)}
              onConfirm={() => { setConfirming(false); launch.mutate(); }}>
        <p>Si la corrida termina bien, el snapshot mensual de {entry.client} queda promovido y el
          ETL no vuelve a aceptar corridas sobre el <span className="mono">{todayIso()}</span>.</p>
        <p>Revertirlo requiere que desarrollo borre el snapshot a mano. No hay botón para eso.</p>
      </Dialog>
    </div>
  );
}

// Sin referencia en el handoff: ni el README ni los .dc.html muestran esta
// pantalla (el picker de ETL antes de elegir uno). Compuesta con las mismas
// piezas del sistema (.card, .tag--accent) en vez de inventar clases nuevas.
function LauncherTile({ entry, onClick }: { entry: CatalogEntry; onClick: () => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button className="card" onClick={onClick}
            onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
            style={{ textAlign: "left", cursor: "pointer", background: hover ? "var(--surface-hover)" : undefined }}>
      <span className="tag tag--accent">{entry.client}</span>
      <div style={{ fontWeight: 500, margin: "8px 0 4px" }}>{entry.name}</div>
      <div className="ink-subtle" style={{ fontSize: 11.5 }}>
        {entry.inputs.map((input) => `${input.role}${input.required ? "" : " (opcional)"}`).join(" · ")}
      </div>
    </button>
  );
}

export default function Lanzador() {
  const { etlId } = useParams();
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });

  if (catalog.isLoading) {
    return (
      <div className="page">
        <div className="skel skel--title" style={{ width: 180, marginBottom: 8 }} />
        <div className="skel skel--text" style={{ width: 300, marginBottom: 24 }} />
        <div className="skel skel--card" />
      </div>
    );
  }
  const executables = (catalog.data ?? []).filter((entry) => entry.executable);
  const entry = executables.find((candidate) => candidate.id === etlId);

  return (
    <div className="page">
      {!entry ? (
        <>
          <header className="page-header">
            <h1>Lanzar corrida</h1>
            <div className="page-header__sub">Elegí el ETL a ejecutar con la fecha de negocio de hoy.</div>
          </header>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-3)" }}>
            {executables.map((candidate) => (
              <LauncherTile key={candidate.id} entry={candidate} onClick={() => navigate(`/lanzar/${candidate.id}`)} />
            ))}
          </div>
        </>
      ) : (
        <>
          <header className="page-header">
            <div className="row">
              <div>
                <h1>{entry.client} — {entry.name}</h1>
                <div className="page-header__sub mono">{entry.id}</div>
              </div>
              <span className="spacer" />
              <Link className="btn btn--ghost" to="/lanzar">Cambiar ETL</Link>
            </div>
          </header>
          <Formulario entry={entry} />
        </>
      )}
    </div>
  );
}
