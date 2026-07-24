# syntax=docker/dockerfile:1
# Violet web-client: build the Vite SPA, then serve it with nginx (which also
# reverse-proxies /api + /health to the assistant-core container).
# Build context = repo root.

FROM node:20-alpine AS build
WORKDIR /app
COPY apps/web-client/package.json apps/web-client/package-lock.json ./
RUN npm ci
COPY apps/web-client/ ./
# Empty base URL => the client uses same-origin relative paths (/api/...),
# which nginx proxies to the backend. Keeps the image portable to any host.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:alpine AS runtime
RUN rm -f /etc/nginx/conf.d/default.conf
COPY apps/web-client/nginx.conf /etc/nginx/conf.d/violet.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
