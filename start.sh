#!/bin/sh
set -e

echo "DEBUG: which python"
which python || echo "python not in PATH"

echo "DEBUG: which python3"
which python3 || echo "python3 not in PATH"

ls -l /usr/local/bin | grep python || echo "No python binaries here"

echo "Exiting early for debug"
exit 1
