FROM node:20-slim AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Serve with nginx
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY infrastructure/nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
