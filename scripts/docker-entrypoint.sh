#!/usr/bin/env bash

set -e

. /app/.venv/bin/activate

exec ${@}
