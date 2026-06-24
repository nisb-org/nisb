FROM node:18-alpine AS builder

WORKDIR /app

COPY package*.json ./

RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .

RUN test -f /app/src/composables/editor/chat_panel/use_chat_panel_room_runtime_view_model.js

RUN NODE_OPTIONS=--max-old-space-size=4096 npm run build

FROM node:18-alpine

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder --chown=node:node /app/dist ./dist

RUN npm install -g serve@14.2.4

USER node

EXPOSE 5173

CMD ["serve", "-s", "dist", "-l", "5173"]
