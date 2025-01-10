#!/usr/bin/bash
mkdir -p nsd
wget https://nlnetlabs.nl/downloads/nsd/nsd-4.8.0.tar.gz
tar xzf nsd-4.8.0.tar.gz
cd nsd-4.8.0
./configure --with-configdir=/home/vm-user/workspace/mininet-vsomeip-evaluation/nsd --with-nsd_conf_file=/home/vm-user/workspace/mininet-vsomeip-evaluation/nsd/nsd.conf
make -j$(nproc)
printf "\n\tExecute 'sudo make -j$(nproc) install' in nsd-4.8.0 directory and then 'nsd-control-setup'\n"