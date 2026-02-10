#!/usr/bin/bash

sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/zones/service.zone
sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/zones/client.zone