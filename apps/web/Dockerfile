# syntax=docker/dockerfile:1

FROM node:20-bullseye-slim AS BUILDER

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.12.1 --activate

# Copy only what is needed for build (context should be repo root)
COPY apps/web ./apps/web
COPY apps/api ./apps/api
COPY scripts ./scripts

WORKDIR /app/apps/web

RUN pnpm install --frozen-lockfile

ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN pnpm build
RUN pnpm prune --prod


FROM node:20-bullseye-slim AS RUNNER

WORKDIR /app/apps/web

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=builder /app/apps/web/.next ./.next
COPY --from=builder /app/apps/web/public ./public
COPY --from=builder /app/apps/web/package.json ./package.json
COPY --from=builder /app/apps/web/next.config.ts ./next.config.ts
COPY --from=builder /app/apps/web/node_modules ./node_modules

EXPOSE 3000

CMD ["node_modules/.bin/next", "start", "-p", "3000"]
