#!/usr/bin/env bash
# Гарантируем, что папка для SQLite-файла существует и доступна.
set -euo pipefail

mkdir -p /app/data

exec "$@"
