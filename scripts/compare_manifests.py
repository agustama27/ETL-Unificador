"""Verifica la fidelidad de los manifiestos migrados en la Fase 3 (ADR-001).

Compara los ``registry/<cliente>.yaml`` de un ref git anterior a la migración
contra los ``etls/<cliente>/manifest.yaml`` actuales, campo por campo del
contrato (inputs, outputs con date_format, exits, timeout, arguments, adapter,
stateful). Los campos de ruta (project_path/working_dir/entrypoint/command)
cambian por diseño; ``command`` se reporta igual porque lleva la ruta del job.

Uso: ``python scripts/compare_manifests.py [ref_viejo]`` (default: f0313d6,
el tip de la Fase 2, último commit con registry/).
"""

import subprocess
import sys
from pathlib import Path

import yaml

DEFAULT_OLD_REF = "f0313d6"
CLIENTS = ["naranjax", "bancor", "petersen", "epec", "fravega", "clarouy",
           "encuestacx", "sociallearning"]
FIELDS = ["command", "fixed_arguments", "inputs", "outputs", "allowed_exits",
          "timeout_seconds", "request_date_format", "output_date_source",
          "environment_allowlist", "arguments"]
STATEFUL_ADAPTERS = {"MaChatAdapter", "MaVoiceAdapter"}


def _load_old(ref: str, client: str) -> dict:
    raw = subprocess.run(["git", "show", f"{ref}:registry/{client}.yaml"],
                         capture_output=True, text=True, check=True).stdout
    return {entry["id"]: entry for entry in yaml.safe_load(raw)["etls"]}


def _load_new(client: str) -> dict:
    raw = Path(f"etls/{client}/manifest.yaml").read_text("utf-8")
    return {entry["id"]: entry for entry in yaml.safe_load(raw)["etls"]}


def _adapter_class(reference: str | None) -> str | None:
    return reference.rsplit(":", 1)[-1] if reference else None


def main() -> int:
    old_ref = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OLD_REF
    total = differing = 0
    for client in CLIENTS:
        old, new = _load_old(old_ref, client), _load_new(client)
        if set(old) != set(new):
            print(f"!! {client}: ids difieren: {sorted(set(old) ^ set(new))}")
            differing += 1
            continue
        for etl_id in old:
            total += 1
            differences = []
            for field in FIELDS:
                if old[etl_id].get(field) != new[etl_id].get(field):
                    differences.append(
                        (field, old[etl_id].get(field), new[etl_id].get(field)))
            old_class = _adapter_class(old[etl_id].get("adapter"))
            new_class = _adapter_class(new[etl_id].get("adapter"))
            if old_class != new_class:
                differences.append(("adapter(clase)", old_class, new_class))
            if (old_class in STATEFUL_ADAPTERS) != (new_class in STATEFUL_ADAPTERS):
                differences.append(("stateful", old_class in STATEFUL_ADAPTERS,
                                    new_class in STATEFUL_ADAPTERS))
            if differences:
                differing += 1
                print(f"\nDIF {etl_id}:")
                for field, old_value, new_value in differences:
                    print(f"  {field}:\n    viejo: {old_value}\n    nuevo: {new_value}")
            else:
                formats = [f"{o['role']}:{o.get('date_format')}"
                           for o in new[etl_id].get("outputs", [])]
                print(f"OK  {etl_id:32s} outputs=[{', '.join(formats)}]")
    print(f"\n{total} ETLs comparados, {differing} con diferencias")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
