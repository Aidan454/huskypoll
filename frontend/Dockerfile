FROM node:22-alpine

# Set working directory in the container
WORKDIR /app

# Copy dependencies
COPY package*.json ./

# Install dependencies (clean install)
RUN npm ci

# Copy DockerFile's directory to WORKDIR
COPY . .

# Start the React app
RUN npm run build

# Labels which ports to expose
EXPOSE 80 443
