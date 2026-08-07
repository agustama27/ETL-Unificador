export interface InputSpec { role: string; extensions: string[]; required: boolean }
export interface OutputSpec { role: string; glob: string; date_format: string | null }

export interface CatalogEntry {
  id: string; name: string; client: string;
  readiness: "ready" | "candidate" | "blocked";
  executable: boolean; reason: string | null;
  stateful: boolean; params: string[];
  inputs: InputSpec[]; outputs: OutputSpec[];
  timeout_seconds: number | null; deadline_hint: string | null;
}

export type RunStatus = "preparing" | "running" | "succeeded" | "failed" | "timed_out" | "blocked";
export type ErrorCode = "validation_error" | "snapshot_exists" | "lock_exists" | "timeout"
  | "postcondition_failed" | "recovery_required" | string;

export interface RunSummary {
  run_id: string; etl_id: string; client: string;
  business_date: string; status: RunStatus; error_code: ErrorCode | null;
  started_at: string | null; finished_at: string | null; artifacts_count: number;
}

export interface RunDetail extends RunSummary {
  command: string[]; exit_code: number | null; timed_out: boolean | null;
  inputs: { role: string; name: string; size: number; sha256: string }[];
  artifacts: { role: string; name: string; size: number; path: string }[];
  logs: { stdout_tail: string; stderr: string };
  postconditions: { outputs: string; state: string } | null;
  state: { scope: string; status: string } | null;
}

export interface HistoryPage { items: RunSummary[]; total: number; page: number; pages: number }

const json = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof body.detail === "string" ? body.detail : response.statusText);
  }
  return response.json() as Promise<T>;
};

export const fetchCatalog = () => fetch("/api/catalog").then((r) => json<CatalogEntry[]>(r));
export const fetchRun = (runId: string) => fetch(`/api/runs/${runId}`).then((r) => json<RunDetail>(r));

export const fetchHistory = (params: Record<string, string | number>) => {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "").map(([k, v]) => [k, String(v)]),
  );
  return fetch(`/api/runs?${query}`).then((r) => json<HistoryPage>(r));
};

export const launchRun = (etlId: string, businessDate: string,
                          files: Record<string, File>,
                          params: Record<string, string | boolean> = {}) => {
  const form = new FormData();
  form.append("etl_id", etlId);
  form.append("business_date", businessDate);
  form.append("params", JSON.stringify(params));
  for (const [role, file] of Object.entries(files)) form.append(role, file);
  return fetch("/api/runs", { method: "POST", body: form })
    .then((r) => json<{ run_id: string; status: RunStatus }>(r));
};

export const runAction = (runId: string, action: "free_lock" | "notify_dev") =>
  fetch(`/api/runs/${runId}/actions/${action}`, { method: "POST" })
    .then((r) => json<{ ok: boolean }>(r));

export const artifactUrl = (runId: string, role: string) => `/api/runs/${runId}/artifacts/${role}`;
export const artifactsZipUrl = (runId: string) => `/api/runs/${runId}/artifacts.zip`;

export const LIVE: RunStatus[] = ["preparing", "running"];
export const todayIso = () => new Date().toISOString().slice(0, 10);

export const STATUS_LABELS: Record<RunStatus | "pending", string> = {
  preparing: "Preparando", running: "En curso", succeeded: "Exitosa",
  failed: "Fallida", timed_out: "Timeout", blocked: "Bloqueada", pending: "Pendiente",
};

export const READINESS_LABELS = { ready: "Listo", candidate: "Candidato", blocked: "Bloqueado" } as const;

export interface ErrorCopy {
  title: string; what: string; todo: string;
  actions: ("retry" | "notify" | "free_lock" | "view_promoted")[];
}

export const ERROR_COPY: Record<string, ErrorCopy> = {
  validation_error: {
    title: "Los datos de entrada no pasaron la validación",
    what: "Antes de procesar, el ETL revisó el archivo y encontró un problema: columnas faltantes, formato inesperado o datos que no corresponden a la fecha de hoy.",
    todo: "Verificá que hayas subido el archivo correcto del día (no uno viejo ni de otro cliente) y volvé a ejecutar. Si el archivo es el correcto, notificá a desarrollo.",
    actions: ["retry", "notify"],
  },
  snapshot_exists: {
    title: "Este ETL ya se ejecutó y promovió hoy",
    what: "Existe un snapshot promovido para la fecha de hoy. Para proteger el estado mensual, el sistema no permite volver a correr sobre el mismo día.",
    todo: "Si la corrida anterior fue correcta, no hace falta nada: descargá sus artefactos. Si realmente necesitás re-ejecutar, pedí a desarrollo que revierta el snapshot.",
    actions: ["view_promoted", "notify"],
  },
  lock_exists: {
    title: "Hay otra corrida en curso para este ETL",
    what: "Se encontró un lock activo: otra corrida del mismo ETL está corriendo ahora, o una corrida anterior terminó mal y dejó el lock tomado.",
    todo: "Esperá a que la corrida en curso termine. Si en el tablero no hay ninguna corrida activa de este ETL, liberá el lock y reintentá.",
    actions: ["free_lock", "retry"],
  },
  timeout: {
    title: "La corrida superó el tiempo máximo (15 minutos)",
    what: "El proceso no terminó dentro de los 15 minutos permitidos y fue interrumpido. No se promovió ningún resultado ni se generaron artefactos.",
    todo: "Revisá que el archivo de entrada no sea inusualmente grande y reintentá. Si vuelve a pasar, notificá a desarrollo con el ID de esta corrida.",
    actions: ["retry", "notify"],
  },
  postcondition_failed: {
    title: "Terminó, pero no generó los archivos esperados",
    what: "El proceso finalizó sin error aparente, pero falta alguno de los artefactos declarados o su nombre no cumple el patrón esperado.",
    todo: "No entregues nada al cliente. Notificá a desarrollo con el ID de esta corrida; la evidencia técnica de abajo tiene el detalle.",
    actions: ["notify"],
  },
  recovery_required: {
    title: "El estado mensual quedó inconsistente",
    what: "Una corrida anterior falló en medio de la promoción de estado y el linaje mensual necesita una recuperación manual antes de aceptar corridas nuevas.",
    todo: "No reintentes. Notificá a desarrollo: tienen que ejecutar la recuperación del estado. El ETL se rehabilita cuando esté resuelto.",
    actions: ["notify"],
  },
};

export const FALLBACK_ERROR: ErrorCopy = {
  title: "La corrida terminó con un problema",
  what: "El proceso no finalizó correctamente. La evidencia técnica de abajo tiene el detalle.",
  todo: "Reintentá la corrida; si vuelve a fallar, notificá a desarrollo con el ID de esta corrida.",
  actions: ["retry", "notify"],
};

export const formatBytes = (size: number) => {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
};

export const formatMoment = (iso: string | null) => {
  if (!iso) return "—";
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : parsed.toLocaleString("es-AR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
};

export const formatDuration = (start: string | null, end: string | null) => {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const seconds = Math.round(ms / 1000);
  return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
};
