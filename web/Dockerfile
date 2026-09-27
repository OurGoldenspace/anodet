FROM node:22-alpine

WORKDIR /app

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web ./

ARG API_PROXY_URL=http://127.0.0.1:8000
ENV API_PROXY_URL=$API_PROXY_URL

RUN npm run build

EXPOSE 3000

CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
