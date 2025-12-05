FROM node:20-bullseye

# Install system dependencies for sharp, canvas, ghostscript
RUN apt-get update && apt-get install -y \
    ghostscript \
    graphicsmagick \
    poppler-utils \
    build-essential \
    libcairo2-dev \
    libpango1.0-dev \
    libjpeg-dev \
    libgif-dev \
    librsvg2-dev \
    libpixman-1-dev \
    libvips-dev \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (including dev for build)
RUN npm ci

# Copy app source
COPY . .

# Build TypeScript if needed
RUN npm run build || true

# Create necessary directories
RUN mkdir -p temp/uploads temp/images output

# Expose port (Railway sets PORT env var)
EXPOSE 3000

# Start the server
CMD ["node", "server.js"]

