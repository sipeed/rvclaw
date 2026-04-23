#!/bin/sh
find "${1:-.}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
echo "done"
