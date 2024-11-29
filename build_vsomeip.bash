#!/usr/bin/bash

cmake -B /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip/build -S /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip
$(which cmake) --build /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip/build --config Release --target all -- -j$(nproc)
$(which cmake) --build /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip/build --config Release --target examples -- -j$(nproc)
$(which cmake) --build /home/vm-user/workspace/mininet-vsomeip-evaluation/vsomeip/build --config Release --target statistics-writer -- -j$(nproc)