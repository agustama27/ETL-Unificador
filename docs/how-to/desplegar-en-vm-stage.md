# Cómo desplegar en la VM STAGE

Deploy con Docker Compose en `SRV-APP-STAGE` (`10.0.32.181`), que es una **VM compartida** con
stacks de otros equipos ya en uso.

Este destino es distinto del cluster: ahí el despliegue va por Helm y está en
[desplegar-en-kubernetes.md](desplegar-en-kubernetes.md). El chart de `deploy/package/` **no
se usa acá**.

## Antes de empezar

| Requisito | Cómo se verifica |
|---|---|
| VPN de Evoltis conectada | `ssh` a la VM responde; sin VPN da *connection timed out* |
| Clave `ia-agent-sre` con permisos `600` | `chmod 600 ia-agent-sre` |
| El hostname es el de STAGE | paso 1 |

## 1. Conectarse y confirmar que es STAGE

```bash
ssh -o IdentitiesOnly=yes -i ./ia-agent-sre ai-agent@10.0.32.181
hostname && whoami
```

Tiene que responder `srv-app-stage` y `ai-agent`. **Cualquier otro hostname: cortar.**
`SRV-APP-PROD` (`10.0.32.180`) está prohibido.

## 2. Docker se usa con `sudo`

`ai-agent` **no** está en el grupo `docker`, así que `docker ps` a secas da
`permission denied`. Sí está en el grupo `sudo` con NOPASSWD, así que todos los comandos van
con `sudo docker ...`.

No arreglar esto con `usermod -aG docker ai-agent` ni cambiando permisos del socket: son
cambios permanentes a una VM compartida, y la guía de operación los prohíbe explícitamente.

## 3. Elegir el puerto mirando, no adivinando

La VM es compartida. Antes de fijar un puerto:

```bash
ss -lnt
sudo docker ps --format "table {{.Names}}\t{{.Ports}}"
ls -la /opt/stacks
```

Al momento de escribir esto los stacks vecinos son `cora` (8081), `axis` (8088),
`cupones-bancor` (8000) y `portainer` (9443). **Ninguno se toca.** Este stack usa el **8082**.

## 4. Subir el código

El repositorio todavía no tiene la rama en Bitbucket, así que no se clona: se empaqueta lo
que git tiene trackeado y se copia. `git archive` excluye solo con eso `.venv`,
`node_modules` y `var/`, que suman 2 GB contra los ~1 MB del paquete.

```bash
git archive --format=tar.gz -o /tmp/etl-unificador.tgz HEAD
scp -o IdentitiesOnly=yes -i ./ia-agent-sre /tmp/etl-unificador.tgz \
    ai-agent@10.0.32.181:/opt/stacks/etl-unificador/
ssh ... 'cd /opt/stacks/etl-unificador && tar -xzf etl-unificador.tgz && rm etl-unificador.tgz'
```

El `.gitattributes` fuerza LF en todo lo que interpreta Linux. Sin eso el paquete sale con
CRLF desde Windows y el build del Dockerfile falla con un error que no menciona los fines de
línea.

## 5. Crear el `.env` en la VM

El `.env` real **nunca** sale del servidor ni se versiona. El token se genera ahí:

```bash
cd /opt/stacks/etl-unificador
cp .env.example .env
sed -i "s|^ETL_HOST_PORT=.*|ETL_HOST_PORT=8082|" .env
sed -i "s|^ETL_CONSOLE_TOKEN=.*|ETL_CONSOLE_TOKEN=$(openssl rand -hex 32)|" .env
chmod 600 .env
```

Para leer el token cuando haga falta (en la VM, no por acá):

```bash
grep '^ETL_CONSOLE_TOKEN=' /opt/stacks/etl-unificador/.env | cut -d= -f2
```

## 6. Validar y levantar

```bash
cd /opt/stacks/etl-unificador
sudo docker compose config --quiet     # falla si falta una variable
sudo docker compose up -d --build
```

El primer build compila la consola con node y arma la imagen del backend con `uv sync
--locked`: tarda varios minutos. Los siguientes reutilizan capas.

## 7. Verificar

```bash
sudo docker compose ps                 # los dos servicios running, backend healthy
sudo docker compose logs --tail=100
curl -I http://localhost:8082          # 200 desde la VM
curl -s http://localhost:8082/ready    # {"status":"ready","etls":N} con N > 0
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8082/api/catalog   # 401
```

Ese `401` es la señal correcta: la API es fail-closed y el token todavía no se envió.

Desde el navegador en la red corporativa: `http://10.0.32.181:8082`. La consola muestra la
pantalla de acceso y pide el token; se pega ahí una sola vez y queda guardado en ese
navegador.

Confirmar la zona horaria, de la que dependen los nombres de los archivos de salida:

```bash
sudo docker compose exec backend date   # tiene que decir -03
```

## Re-deploy

```bash
# desde local, con los cambios ya commiteados
git archive --format=tar.gz -o /tmp/etl-unificador.tgz HEAD
scp ... /tmp/etl-unificador.tgz ai-agent@10.0.32.181:/opt/stacks/etl-unificador/
ssh ... 'cd /opt/stacks/etl-unificador && tar -xzf etl-unificador.tgz && rm etl-unificador.tgz \
         && sudo docker compose up -d --build'
```

El `.env` no se pisa: no está en el paquete. El volumen `etl-unificador_etl-var` tampoco se
toca.

## Lo que no se hace acá

- `docker compose down -v` — el `-v` borra el volumen con la evidencia de corridas, el estado
  promovido y los uploads.
- `docker system prune`, `volume prune`, `network prune` — la VM es compartida y se llevarían
  puestos los stacks de otros equipos.
- Publicar en 80 o 443 — hay que averiguar antes quién administra el reverse proxy.
