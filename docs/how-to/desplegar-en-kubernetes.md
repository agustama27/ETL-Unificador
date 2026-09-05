# Cómo desplegar en el cluster

Publicar la imagen y el chart, y hacer el rollout con verificación. Asume acceso a ECR y
`kubectl` apuntando al cluster.

El porqué de las decisiones —réplica única, volumen, zona horaria, subprocesos en vez de
Jobs— está en [../decisions/ADR-002-alineacion-evoltis.md](../decisions/ADR-002-alineacion-evoltis.md).

## Antes de empezar

| Requisito | Verificación |
|---|---|
| `uv`, `task`, `docker`, `helm`, `aws`, `yq` en el PATH | `task check` y `helm version` |
| Credenciales de AWS con permiso sobre ECR | `aws sts get-caller-identity` |
| `AWS_ECR_REGISTRY` exportado | `echo $AWS_ECR_REGISTRY` |
| El Secret del token existe en el namespace | ver el paso 1 |

## 1. Crear el Secret del token

**Este paso no lo hace el chart, y sin él el servicio no atiende.** La API es fail-closed: sin
`ETL_CONSOLE_TOKEN` responde 503 a todo `/api`. El Secret vive en el repositorio de
infraestructura; esto es para levantarlo la primera vez o rotarlo:

```bash
kubectl -n <namespace> create secret generic etl-unificador-token \
  --from-literal=token="$(openssl rand -hex 32)"
```

El nombre y la clave se declaran en `values.yaml` bajo `services.etl-platform-api.tokenSecret`.

## 2. Publicar imagen y chart

```bash
export AWS_ECR_REGISTRY=<cuenta>.dkr.ecr.us-east-1.amazonaws.com
task publish VERSION=1.0.0 ENV=dev
```

`publish` encadena login en ECR, creación del repositorio si falta, build, push de la imagen,
y empaquetado y push del chart. El `helm:package` estampa repositorio y tag dentro de
`values.yaml`, así que el chart publicado ya apunta a la imagen correcta.

Para verificar el chart sin publicar nada:

```bash
task helm:lint
task helm:template
```

## 3. Instalar o actualizar

```bash
helm upgrade --install etl-unificador \
  oci://$AWS_ECR_REGISTRY/dev/automation/charts/etl-unificador \
  --version 1.0.0 \
  --namespace <namespace> --create-namespace \
  --wait --timeout 10m
```

`--wait` espera a que el pod pase a Ready, que es lo que `/ready` decide.

## 4. Verificar que quedó bien

```bash
kubectl -n <namespace> rollout status deploy -l app/service=etl-platform-api
kubectl -n <namespace> port-forward svc/etl-platform-api-svc-etl-unificador 8000:8000
```

Con el port-forward abierto:

```bash
curl -s localhost:8000/health          # {"status":"ok"}
curl -s localhost:8000/ready           # {"status":"ready","etls":N} con N > 0
curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/catalog   # 401 sin token
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/catalog | head -c 200
```

Las cuatro respuestas juntas confirman lo que importa: el proceso vive, el catálogo cargó y
`var/` es escribible, el fail-closed está activo, y el token configurado es el correcto.

Confirmá también la zona horaria, porque de ella dependen los nombres de los artefactos:

```bash
kubectl -n <namespace> exec deploy/<deploy> -- date
```

Tiene que decir `-03`. Si dice `UTC`, los ETLs van a escribir con la fecha equivocada después
de las 21:00 y los globs del manifiesto no van a encontrar los archivos.

## Si `/ready` devuelve 503

El cuerpo trae el motivo. Los dos casos frecuentes:

| Detalle | Causa | Qué hacer |
|---|---|---|
| `CatalogError` | `etls/` no está en la imagen o un manifiesto no parsea | Revisar que el build haya usado la raíz del repo como contexto |
| `OSError` | `var/` no es escribible | El PVC no montó, o el `fsGroup` no coincide con el UID 1000 de la imagen |

## Rollback

```bash
helm -n <namespace> rollback etl-unificador
```

El PVC **no** se toca: lleva `helm.sh/resource-policy: keep`, así que sobrevive incluso a un
`helm uninstall`. Adentro está la evidencia forense de las corridas.

## Lo que este procedimiento no cubre

- **Una corrida en curso durante el despliegue.** La estrategia es `Recreate` con una ventana
  de 3900 s, que cubre el ETL más largo del catálogo. Aun así, si el despliegue no puede
  esperar, la corrida se corta: `recover_orphans()` la marca al arrancar, pero hay que
  relanzarla a mano.
- **Escalar horizontalmente.** No se puede: el locking de estado usa lock files de filesystem.
  Subir `replicas` no da alta disponibilidad, da corrupción de estado.
