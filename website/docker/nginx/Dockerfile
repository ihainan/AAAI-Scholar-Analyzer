FROM node:20-alpine AS frontend-builder

WORKDIR /app

# Copy frontend source (context is website directory)
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Nginx stage
FROM nginx:alpine

# Remove default config
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx config
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf

# Copy frontend build output
COPY --from=frontend-builder /app/dist /usr/share/nginx/html

EXPOSE 37802

CMD ["nginx", "-g", "daemon off;"]
