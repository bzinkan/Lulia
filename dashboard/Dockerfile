FROM node:20-slim

WORKDIR /app

COPY package.json .
# No dependencies yet — skip install

# Placeholder: serve a simple health endpoint until Next.js is scaffolded
RUN npm install --save express@4

COPY . .

EXPOSE 3000

CMD ["node", "-e", "\
const express = require('express'); \
const app = express(); \
app.get('/health', (_, res) => res.json({status: 'healthy', service: 'dashboard'})); \
app.get('/', (_, res) => res.send('<h1>Lulia Dashboard</h1><p>Next.js scaffold coming soon.</p>')); \
app.listen(3000, '0.0.0.0', () => console.log('Dashboard placeholder on :3000')); \
"]
