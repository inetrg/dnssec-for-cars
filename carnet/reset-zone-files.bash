#!/usr/bin/bash

sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/carnet/zones/service.zone
sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/carnet/zones/client.zone
