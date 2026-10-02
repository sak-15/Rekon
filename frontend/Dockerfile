# ==============================================================================
# Rekon Production Frontend Dockerfile
# Multi-stage build: Node.js 20 build -> Nginx Alpine runtime
# ==============================================================================

# Stage 1: Build static bundle
FROM node:20-alpine as builder

WORKDIR /app

# Cache dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy sources
COPY . .

# Pass build-time API URL if needed
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build optimized production bundle
RUN npm run build

# Stage 2: Nginx lightweight runner
FROM nginx:1.25-alpine as runner

# Remove default nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built SPA distribution
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
