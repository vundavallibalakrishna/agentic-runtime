FROM node:24.22.0-bookworm-slim AS build
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@12.14.0 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web apps/web
COPY packages packages
RUN pnpm install --frozen-lockfile \
    && pnpm --filter @ar/web build

FROM node:24.22.0-bookworm-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
USER 10001
ENV HOSTNAME=0.0.0.0 PORT=3000 NODE_ENV=production
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
