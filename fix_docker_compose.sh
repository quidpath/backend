#!/bin/bash
set -e

echo "---- Fixing Docker Compose installation ----"

# Clean apt sources and ensure docker repo is enabled
sudo apt-get update -y
sudo apt-get install ca-certificates curl gnupg -y

# Add Docker’s official GPG key if missing
sudo install -m 0755 -d /etc/apt/keyrings
if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
fi

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
| sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y

# Install or fix Docker and Compose plugin
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

# Verify Compose command
docker compose version

echo "✅ Docker Compose fixed successfully!"
