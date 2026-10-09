FROM node:20-slim AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Número do WhatsApp de vendas da página inicial (ver src/lib/site.ts) —
# variáveis NEXT_PUBLIC_* entram no bundle na hora do build.
ARG NEXT_PUBLIC_WHATSAPP_VENDAS=""
ENV NEXT_PUBLIC_WHATSAPP_VENDAS=$NEXT_PUBLIC_WHATSAPP_VENDAS
RUN npm run build

# output: "standalone" (next.config.ts) empacota só o necessário pra rodar
# (server.js + node_modules mínimos) — imagem final bem menor que copiar o
# projeto inteiro com todas as devDependencies.
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
