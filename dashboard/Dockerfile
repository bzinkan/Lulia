FROM node:20-slim

WORKDIR /app

# Install deps
COPY package.json .
RUN npm install

# Copy source
COPY . .

# Build Next.js
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
