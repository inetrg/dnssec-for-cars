#!/usr/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="${PROJECT_PATH:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$PROJECT_PATH" || exit 1
mkdir -p nsd
wget https://nlnetlabs.nl/downloads/nsd/nsd-4.8.0.tar.gz
tar xzf nsd-4.8.0.tar.gz
cd nsd-4.8.0
./configure --with-configdir=${PROJECT_PATH}/nsd --with-nsd_conf_file=${PROJECT_PATH}/nsd/nsd.conf
make -j$(nproc)
printf "\n\tExecute 'sudo make -j$(nproc) install' in nsd-4.8.0 directory and then 'nsd-control-setup'\n"