# Web preview of the LinguaSI mobile app: the Expo web build, served by nginx. Build from mobile/:
#   docker build -t linguasi-mobile-web mobile
# The phone apps themselves are built with EAS (see README.md); this image is for trying the app in a
# browser. EXPO_PUBLIC_API_URL is compiled into the bundle: it is a public address, never a secret.
ARG NODE_IMAGE=node:22-slim
ARG NGINX_IMAGE=nginx:1.27-alpine

FROM ${NODE_IMAGE} AS build
WORKDIR /app
ENV CI=1 \
    EXPO_NO_TELEMETRY=1 \
    EXPO_OFFLINE=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG EXPO_PUBLIC_API_URL=http://localhost:8000
ENV EXPO_PUBLIC_API_URL=${EXPO_PUBLIC_API_URL}
RUN npx expo export --platform web --output-dir dist

FROM ${NGINX_IMAGE}
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
