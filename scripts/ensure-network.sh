#!/bin/bash
# Ensure Docker network exists before deployment
# This script should be run before docker-compose up

set -e

NETWORK_NAME="stage_quidpath_network"

echo "Checking if Docker network '$NETWORK_NAME' exists..."

if docker network inspect "$NETWORK_NAME" &>/dev/null; then
    echo "✓ Network '$NETWORK_NAME' already exists"
else
    echo "Creating Docker network '$NETWORK_NAME'..."
    docker network create "$NETWORK_NAME"
    echo "✓ Network '$NETWORK_NAME' created successfully"
fi

exit 0
