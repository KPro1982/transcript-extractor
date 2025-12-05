FROM node:20-bullseye

# Install system dependencies for sharp, canvas, ghostscript, poppler
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
    && rm -rf /var/lib/apt/lists/* \
    && echo "Verifying tools..." \
    && gs --version \
    && pdftoppm -v \
    && echo "All PDF tools verified!"

# Create app directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install ALL dependencies (using npm install for flexibility)
RUN npm install --legacy-peer-deps

# Copy app source
COPY . .

# Build TypeScript if needed
RUN npm run build || true

# Create necessary directories with proper permissions
RUN mkdir -p temp/uploads temp/images output \
    && chmod -R 777 temp output

# Expose port (Railway sets PORT env var)
EXPOSE 3000

# Start the server
CMD ["node", "server.js"]

