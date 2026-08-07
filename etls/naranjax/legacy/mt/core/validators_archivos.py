from pathlib import Path


def validar_archivo(path: str | None, extensiones: tuple[str, ...]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not path:
        issues.append({"code": "missing", "message": "Debe seleccionar un archivo."})
        return issues
    p = Path(path)
    if not p.exists():
        issues.append({"code": "not_found", "message": f"No existe: {p}"})
    if p.exists() and p.suffix.lower() not in extensiones:
        issues.append(
            {
                "code": "ext", 
                "message": f"Extension invalida ({p.suffix}). Permitidas: {', '.join(extensiones)}",
            }
        )
    return issues


def validar_estado_mensual(estado_dir: str | Path, mes_yyyymm: str) -> list[dict[str, str]]:
    p = Path(estado_dir)
    target = p / f"estado_{mes_yyyymm}.csv"
    if target.exists():
        return []
    return [
        {
            "code": "missing_estado",
            "message": f"Falta {target.name} en {p}. Puede generar estado inicial.",
        }
    ]


def aggregate_messages(issues: list[dict[str, str]]) -> str:
    return "\n".join(f"- {i['message']}" for i in issues)


def can_enable_process(path_value: str | None, issues: list[dict[str, str]]) -> bool:
    return bool(path_value) and not issues
