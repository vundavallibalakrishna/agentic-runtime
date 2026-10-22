FROM node:24.22.0-bookworm-slim AS build
WORKDIR /app
RUN corepack enable \
    && for attempt in 1 2 3 4; do \
         corepack prepare pnpm@12.14.0 --activate && break; \
         if [ "$attempt" = 4 ]; then exit 1; fi; \
         sleep $((attempt * 15)); \
       done
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web apps/web
COPY packages packages
RUN set -eu; \
    ok=0; \
    for attempt in 1 2 3 4; do \
      if pnpm install --frozen-lockfile; then ok=1; break; fi; \
      echo "pnpm install failed (attempt ${attempt})"; \
      sleep $((attempt * 15)); \
    done; \
    test "$ok" = 1; \
    pnpm --filter @ar/web build

FROM node:24.22.0-bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
USER 10001
ENV HOSTNAME=0.0.0.0 PORT=3000 NODE_ENV=production
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
