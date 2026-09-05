# Contexto de build: esta carpeta (apps/etl-console).
#   docker build -f apps/etl-console/Dockerfile -t <imagen> apps/etl-console
FROM node:20-alpine AS build

WORKDIR /app

# Capa de dependencias: solo se invalida si cambia el manifiesto o el lock.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# `npm run build` corre `tsc -b` antes que vite: un error de tipos rompe el build
# en vez de llegar a produccion.
RUN npm run build


FROM nginx:1.27-alpine AS runtime

# El frontend llama a rutas relativas (/api/...), asi que nginx proxea al backend
# por la red interna de Compose. El navegador nunca ve el puerto del backend.
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
