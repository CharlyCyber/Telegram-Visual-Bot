#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p logs run
echo "🤖 Iniciando bot con reinicio automático..."
# Las dependencias se instalan durante el build, no en cada reinicio.
exec supervisord -c supervisord.conf
