FROM node:24-alpine
ENV NODE_ENV=production PORT=10000
WORKDIR /app
COPY --chown=node:node docs/stock/ ./docs/stock/
COPY --chown=node:node private_dashboard/server.mjs ./private_dashboard/server.mjs
USER node
EXPOSE 10000
CMD ["node", "private_dashboard/server.mjs"]
