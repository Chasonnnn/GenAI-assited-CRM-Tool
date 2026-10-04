# syntax=docker/dockerfile:1

# Cloud Build supplies an immutable reference to the previous builder image.
# The pinned Node image is an empty cache seed for local and first builds.
ARG NEXT_CACHE_IMAGE=node:24.18.0-bookworm-slim
FROM ${NEXT_CACHE_IMAGE} AS next-cache

FROM node:24.18.0-bookworm-slim AS builder

WORKDIR /app
ARG CACHE_BUST=0
RUN echo "cache_bust=${CACHE_BUST}" > /dev/null

RUN corepack enable && corepack prepare pnpm@12.9.1 --activate

# Copy package files first for better cache utilization
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./apps/web/
COPY apps/web/pnpm-workspace.yaml ./apps/web/

# Install dependencies before copying source
WORKDIR /app/apps/web

ENV NPM_CONFIG_OPTIONAL=true
ENV npm_config_optional=true
ENV PNPM_CONFIG_OPTIONAL=true

RUN rm -rf node_modules
RUN pnpm install --frozen-lockfile

# Now copy remaining source files
WORKDIR /app
COPY apps/web ./apps/web
COPY apps/api ./apps/api
COPY scripts ./scripts

WORKDIR /app/apps/web

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_DEPLOYMENT_ID
ENV NEXT_DEPLOYMENT_ID=${NEXT_DEPLOYMENT_ID}

RUN --mount=from=next-cache,target=/previous,ro \
    if [ -d /previous/app/apps/web/.next/cache ]; then \
      mkdir -p .next/cache && cp -a /previous/app/apps/web/.next/cache/. .next/cache/; \
    fi && pnpm build


FROM node:24.18.0-bookworm-slim AS runner

WORKDIR /app/apps/web

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV HOSTNAME=0.0.0.0
ENV PORT=3000

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./public

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', res => { if (res.statusCode !== 200) process.exit(1) }).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
