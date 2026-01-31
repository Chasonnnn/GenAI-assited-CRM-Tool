# syntax=docker/dockerfile:1

FROM node:20.20.0-bullseye-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ARG CACHE_BUST=0
RUN echo "cache_bust=${CACHE_BUST}" > /dev/null

RUN corepack enable && corepack prepare pnpm@9.12.1 --activate

# Copy package files first for better cache utilization
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./apps/web/

# Install dependencies before copying source
WORKDIR /app/apps/web

ENV NPM_CONFIG_OPTIONAL=true
ENV npm_config_optional=true
ENV PNPM_CONFIG_OPTIONAL=true

RUN rm -rf node_modules
RUN pnpm install --frozen-lockfile --config.optional=true

# Now copy remaining source files
WORKDIR /app
COPY apps/web ./apps/web
COPY apps/api ./apps/api
COPY scripts ./scripts

WORKDIR /app/apps/web

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm build
RUN pnpm prune --prod


FROM node:20.20.0-bullseye-slim AS runner

WORKDIR /app/apps/web

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user for security
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/package.json ./package.json
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/next.config.js ./next.config.js
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/node_modules ./node_modules

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', res => { if (res.statusCode !== 200) process.exit(1) }).on('error', () => process.exit(1))"

CMD ["node_modules/.bin/next", "start", "-p", "3000"]
