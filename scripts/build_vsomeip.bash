#!/usr/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="${PROJECT_PATH:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cmake -B "$PROJECT_PATH/vsomeip/build" -S "$PROJECT_PATH/vsomeip"
$(which cmake) --build "$PROJECT_PATH/vsomeip/build" --config Release --target all -- -j$(nproc)
$(which cmake) --build "$PROJECT_PATH/vsomeip/build" --config Release --target examples -- -j$(nproc)
$(which cmake) --build "$PROJECT_PATH/vsomeip/build" --config Release --target statistics-writer -- -j$(nproc)