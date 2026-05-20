FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8080
ARG VITE_USE_MOCK_DATA=false
ARG VITE_OPENROUTER_API_KEY
ARG VITE_OPENROUTER_MODEL
ARG VITE_OPENROUTER_HTTP_REFERER
ARG VITE_OPENROUTER_APP_TITLE
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_USE_MOCK_DATA=${VITE_USE_MOCK_DATA}
ENV VITE_OPENROUTER_API_KEY=${VITE_OPENROUTER_API_KEY}
ENV VITE_OPENROUTER_MODEL=${VITE_OPENROUTER_MODEL}
ENV VITE_OPENROUTER_HTTP_REFERER=${VITE_OPENROUTER_HTTP_REFERER}
ENV VITE_OPENROUTER_APP_TITLE=${VITE_OPENROUTER_APP_TITLE}
ENV NODE_OPTIONS=--max-old-space-size=4096

COPY package*.json ./
RUN npm ci --legacy-peer-deps

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
# Arquivos podem vir do host com modo 600; o worker nginx não roda como root e precisa ler assets estáticos.
RUN chmod -R a+rX /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
