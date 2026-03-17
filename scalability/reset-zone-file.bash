#!/usr/bin/bash

sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/scalability/zones/service.zone
sed -i '/; =======================================================================/q' /home/vm-user/workspace/mininet-vsomeip-evaluation/scalability/zones/client.zone