# syntax=docker/dockerfile:1

# ---- build: type-check and bundle --------------------------------------------------------
# Debian-based (glibc) rather than Alpine: the native TypeScript 7 and Rolldown binaries in
# package-lock.json target glibc.
FROM node:24-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
RUN npm run build

# ---- runtime: static files behind nginx, which also proxies /api to the backend -----------
FROM nginx:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
