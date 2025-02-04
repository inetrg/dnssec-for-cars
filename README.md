# mininet-vsomeip-evaluation for Ubuntu Jammy

## Dependencies
- pkg-config - sudo apt install pkg-config
- doxygen - sudo apt install doxygen

- [boost 1.83](https://launchpad.net/~mhier/+archive/ubuntu/libboost-latest)
    sudo add-apt-repository ppa:mhier/libboost-latest
    sudo apt update
    sudo apt install libboost1.83-all-dev
- [cmake](https://apt.kitware.com/)
- [libc-ares-dev](https://packages.ubuntu.com/jammy/libc-ares-dev) 
    --> Uninstalled 
    --> get tar release: https://github.com/c-ares/c-ares/releases/download/v1.34.4/c-ares-1.34.4.tar.gz
    ./configure
    make
    sudo make install
- [cryptopp](https://github.com/weidai11/cryptopp)
- [cryptopp pem pack](https://github.com/noloader/cryptopp-pem)
- [openssl](https://packages.ubuntu.com/jammy/openssl)
- [libssl-dev](https://packages.ubuntu.com/jammy/libssl-dev)
- [xxd](https://packages.ubuntu.com/jammy/xxd)
- [python](https://packages.ubuntu.com/jammy/python3)
- [mininet](https://mininet.org/download/)

## Prerequisites
1. Execute `git submodule init` first and then `git submodule update` to pull the _vsomeip_ project
2. Adjust all path specifications in every file containing `/home/vm-user/workspace` according to your project path
3. Execute the `download-and-compile-nsd.bash` script and follow the instructions at the end to setup the authoritative name server

## Evaluation
Update user in `topo-1sw-Nhosts.py` from `vm-user` to your username.
Execute `python topo-1sw-Nhosts.py --help` to get a list with which options the evaluation can be started with.

There are eight evaluation options:
- A: vanilla (vsomeip as it is)
- B: w/ DNSSEC w/o SOME/IP SD
- C: w/ service authentication
- D: w/ service authentication + DNSSEC + DANE w/o SOME/IP SD
- E: w/ service and client authentiction
- F: w/ service and client authentiction + payload encryption
- G: w/ service and client authentication + DNSSEC + DANE
- H: w/ service and client authentication + DNSSEC + DANE + payload encryption

Moreover, an interactive mode is started for debugging purposes if the `--runs` option is omitted.

## Known Issues
- Wireshark is prone to freezing when evaluation options with authentication are used
- _vsomeip_ does not work properly when file or console logging is enabled but not redirected to the terminal or to a file, which is handled by the `topo-1sw-Nhosts.py` script (see STD_CONDITION variable)
