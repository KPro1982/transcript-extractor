FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ghostscript \
    graphicsmagick \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy app source
COPY . .

# Create necessary directories
RUN mkdir -p temp/uploads temp/images output

# Expose port (Railway sets PORT env var)
EXPOSE 3000

# Start the server
CMD ["node", "server.js"]

