# The app as static files, served by nginx. `docker compose up` (repository root) runs it.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Where the browser finds the API. Built into the app, so set it when building.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# nginx as an ordinary user, on port 8080.
FROM nginxinc/nginx-unprivileged:1.29-alpine
# The API's origin, allowed by the Content-Security-Policy (connect-src). Filled in at start.
ENV API_ORIGIN=https:
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
