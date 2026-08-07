import { File as FileIcon, Info, UploadSimple, X } from "@phosphor-icons/react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { DragEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchCatalog, formatBytes, launchRun, todayIso } from "../api";
import type { CatalogEntry, InputSpec } from "../api";
import { useToast } from "../components/shared";

function Dropzone({ spec, file, onFile, onClear, onError }: {
  spec: InputSpec; file: File | undefined;
  onFile: (file: File) => void; onClear: () => void; onError: (message: string) => void;
}) {
  const [over, setOver] = useState(false);
  const accept = spec.extensions.join(",");

  const take = (candidate: File | undefined) => {
    if (!candidate) return;
    const suffix = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!spec.extensions.map((ext) => ext.toLowerCase()).includes(suffix)) {
      onError(`Extensión inválida para ${spec.role}: se espera ${spec.extensions.join(", ")}`);
      return;
    }
    onFile(candidate);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setOver(false);
    take(event.dataTransfer.files?.[0]);
  };

  if (file) {
    return (
      <div className="filerow">
        <FileIcon size={15} />
        <span className="mono">{file.name}</span>
        <span className="size">{formatBytes(file.size)}</span>
        <button className="btn-ghost" onClick={onClear} aria-label={`Quitar ${spec.role}`}><X size={12} /></button>
      </div>
    );
  }
  return (
    <label className={`dropzone${over ? " over" : ""}`}
           onDragOver={(event) => { event.preventDefault(); setOver(true); }}
           onDragLeave={() => setOver(false)} onDrop={onDrop}>
      <input type="file" accept={accept} style={{ display: "none" }}
             onChange={(event) => take(event.target.files?.[0] ?? undefined)} />
      <div className="row" style={{ justifyContent: "center" }}>
        <UploadSimple size={16} />
        <span className="role">{spec.role}</span>
        <span className={spec.required ? "req" : "opt"}>{spec.required ? "requerido" : "opcional"}</span>
        <span className="mono">{spec.extensions.join(" ")}</span>
      </div>
      <div style={{ marginTop: 6, fontSize: 12 }}>Arrastrá el archivo acá o hacé click para elegirlo</div>
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

  return (
    <div className="two-col">
      <div className="stack">
        <div>
          <span className="field-label">Fecha de negocio</span>
          <div className="row">
            <input type="text" disabled value={`${todayIso()} (hoy)`} />
            <span className="tag accent">Fija en HOY</span>
          </div>
          <div className="note-info" style={{ marginTop: 8 }}>
            <Info size={13} style={{ verticalAlign: "-2px" }} /> Regla del sistema: solo se acepta la
            fecha de negocio de hoy. Los nombres de los archivos de salida se generan con la fecha del sistema.
          </div>
        </div>
        {entry.inputs.map((spec) => (
          <Dropzone key={spec.role} spec={spec} file={files[spec.role]}
                    onFile={(file) => { setInlineError(null); setFiles((c) => ({ ...c, [spec.role]: file })); }}
                    onClear={() => setFiles(({ [spec.role]: _omit, ...rest }) => rest)}
                    onError={setInlineError} />
        ))}
        {entry.params.includes("no_planes_today") && (
          <label className="row" style={{ fontSize: 12.5 }}>
            <input type="checkbox" checked={noPlanes} onChange={(e) => setNoPlanes(e.target.checked)} />
            <span>
              <strong>Hoy no hay archivo de PLANES.</strong>{" "}
              Ejecuta sin cruce de planes. Queda registrado en la evidencia de la corrida.
            </span>
          </label>
        )}
        {inlineError && <div className="banner-error">{inlineError}</div>}
        <div className="row">
          <button className="btn-primary" disabled={missing.length > 0 || launch.isPending}
                  onClick={() => launch.mutate()}>
            Ejecutar ahora
          </button>
          {missing.length > 0
            ? <span className="req">Falta el archivo requerido: {missing.map((s) => s.role).join(", ")}</span>
            : <span className="muted">Listo para ejecutar · tiempo máximo 15 min</span>}
        </div>
      </div>
      <div className="card">
        <h3>Qué va a pasar</h3>
        <div className="stack" style={{ gap: 10 }}>
          <div className="muted">La corrida tiene un tiempo máximo de 15 minutos; si lo supera, se interrumpe.</div>
          {entry.stateful && (
            <div className="note-warn">
              ETL con estado mensual: al terminar bien, promueve un snapshot del día y no permite re-ejecutar hoy.
            </div>
          )}
          <div className="muted">
            Toda la corrida queda registrada con evidencia inmutable: comando, hashes de entrada, logs y artefactos.
          </div>
          <div>
            <span className="field-label">Salidas esperadas</span>
            <div className="stack" style={{ gap: 6 }}>
              {entry.outputs.map((output) => (
                <div key={output.role} className="row">
                  <span className="tag accent">{output.role}</span>
                  <span className="mono">{resolveOutputName(output.glob, output.date_format)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Lanzador() {
  const { etlId } = useParams();
  const navigate = useNavigate();
  const catalog = useQuery({ queryKey: ["catalog"], queryFn: fetchCatalog, staleTime: 5 * 60_000 });

  if (catalog.isLoading) return <div className="page stack"><div className="skeleton" /><div className="skeleton" /></div>;
  const executables = (catalog.data ?? []).filter((entry) => entry.executable);
  const entry = executables.find((candidate) => candidate.id === etlId);

  return (
    <div className="page">
      {!entry ? (
        <>
          <header className="page-header">
            <h1>Lanzar corrida</h1>
            <div className="subtitle">Elegí el ETL a ejecutar con la fecha de negocio de hoy.</div>
          </header>
          <div className="launch-grid">
            {executables.map((candidate) => (
              <button key={candidate.id} className="launch-card"
                      onClick={() => navigate(`/lanzar/${candidate.id}`)}>
                <div className="client">{candidate.client}</div>
                <div style={{ fontWeight: 500, margin: "4px 0" }}>{candidate.name}</div>
                <div className="muted" style={{ fontSize: 11.5 }}>
                  {candidate.inputs.map((input) =>
                    `${input.role}${input.required ? "" : " (opcional)"}`).join(" · ")}
                </div>
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <header className="page-header">
            <div className="row">
              <div>
                <h1>{entry.client} — {entry.name}</h1>
                <div className="subtitle mono">{entry.id}</div>
              </div>
              <span className="spacer" />
              <Link className="btn-ghost" to="/lanzar">Cambiar ETL</Link>
            </div>
          </header>
          <Formulario entry={entry} />
        </>
      )}
    </div>
  );
}
