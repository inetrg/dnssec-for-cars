#!/usr/bin/python

"""Scalability topology scenario with multiple publishers and subscribers.

N hosts directly connected to one switch, with configurable numbers of
publishers and subscribers per publisher.
"""

import argparse
import subprocess
import json
import time
from pathlib import Path
from math import ceil

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel

from mininet_vsomeip_base_scenario import VSomeIPTopologyBase


class simple_topo(Topo):
    """Simple topology: N hosts directly connected to one switch."""

    def build(self, n: int = 2):
        """Create custom topo."""
        # Add switch
        switch = self.addSwitch('s1')

        # Add hosts with links connecting to switch
        for i in range(n):
            host = self.addHost('h{}'.format(i + 1))
            self.addLink(host, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999)


class ScalabilityScenario(VSomeIPTopologyBase):
    """Scalability scenario with multiple publishers and subscribers."""

    SCENARIO_FOLDER = "scalability"

    def __init__(self):
        """Initialize scenario with parameters."""
        super().__init__()
        self.scenario_dirs(self.SCENARIO_FOLDER)
        self.pub_count = 0
        self.sub_count = 0
        self.pubs_per_host = 1
        self.pub_managers = {}
        self.sub_managers = {}
        self.one_sub_host = False

    # ========== SCENARIO CONFIGURATION ==========

    def set_parameters(self, pub_count, sub_count, pubs_per_host=1, one_sub_host=False):
        """Set scenario parameters."""
        self.pub_count = pub_count
        self.sub_count = sub_count
        self.pubs_per_host = pubs_per_host
        self.one_sub_host = one_sub_host

    def _get_publisher_host_id(self, pub_id):
        """Get host ID for a given publisher ID."""
        return ((pub_id - 1) // self.pubs_per_host) + 1

    def _get_subscriber_host_id(self, pub_id, sub_id):
        """Get host ID for a subscriber."""
        max_pub_host_id = self._get_publisher_host_id(self.pub_count)
        if self.one_sub_host:
            return max_pub_host_id + sub_id
        return max_pub_host_id + (pub_id - 1) * self.sub_count + sub_id

    def _get_subscriber_id(self, pub_id, sub_id):
        """Calculate unique subscriber ID."""
        return self.pub_count + (pub_id - 1) * self.sub_count + sub_id

    # ========== CONFIGURATION CREATION ==========

    # ========== MANAGER/APP STARTUP ==========

    # ========== EVALUATION SUPPORT ==========

    # ========== PUBLISHER/SUBSCRIBER SETUP ==========

    def create_publishers(self, net, dns_host=None):
        """Create all publisher configurations and certificates."""
        dns_host_ip_in_hex = None
        if dns_host is not None and dns_host != "":
            dns_host_obj = net[dns_host]
            dns_host_ip = dns_host_obj.IP(intf=dns_host_obj.defaultIntf())
            ip_bytes = dns_host_ip.split(".")
            ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
            dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"

        for i in range(1, self.pub_count + 1):
            host_id = self._get_publisher_host_id(i)
            print(f"Creating publisher {i}/{self.pub_count} on host h{host_id}")
            host = net[f'h{host_id}']
            self.create_publisher_config(host, i)
            self.create_publisher_certificate(host, i)
            if dns_host_ip_in_hex:
                self._set_dns_server_ip(host, dns_host_ip_in_hex)
            # Track as manager if first on host
            if f'h{host_id}' not in self.pub_managers:
                app_name = self.get_publisher_app_name(host, i)
                app_id = f"0x{i:04x}"
                self.pub_managers[f'h{host_id}'] = {"pub_id": i, "app_name": app_name, "app_id": app_id}

    def create_subscribers(self, net, dns_host=None):
        """Create all subscriber configurations and certificates."""
        dns_host_ip_in_hex = None
        if dns_host is not None and dns_host != "":
            dns_host_obj = net[dns_host]
            dns_host_ip = dns_host_obj.IP(intf=dns_host_obj.defaultIntf())
            ip_bytes = dns_host_ip.split(".")
            ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
            dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"

        for i in range(1, self.pub_count + 1):
            for j in range(1, self.sub_count + 1):
                sub_host_id = self._get_subscriber_host_id(i, j)
                sub_host = net[f'h{sub_host_id}']
                print(f"Creating subscriber {i}/{self.pub_count} - {j}/{self.sub_count} on host h{sub_host_id}")
                self.create_subscriber_config(sub_host, i, j)
                self.create_subscriber_certificate(sub_host, i, j)
                if dns_host_ip_in_hex:
                    self._set_dns_server_ip(sub_host, dns_host_ip_in_hex)

    def _set_dns_server_ip(self, host, dns_host_ip_in_hex):
        """Set DNS server IP in host configuration."""
        host_name = host.__str__()
        host_config = self.get_publisher_config_path(host, 1)  # Will update config
        if Path(host_config).is_file():
            with open(host_config, 'r') as file:
                config = json.load(file)
            config['dns-server-ip'] = dns_host_ip_in_hex
            with open(host_config, 'w') as file:
                json.dump(config, file, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Starts vsomeip w/ or w/o security mechanisms and collects timestamps of handshake events')
    parser.add_argument('--pubs', type=int, metavar='N', required=True, choices=range(1, 0xffff + 1), help='Specify the number of publishers. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--onesubhost', dest='onesubhost', action='store_true', help='Use only one subscriber host for all subscribers')
    parser.add_argument('--subsperpub', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of subscribers per publisher. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--pubsperhost', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of publishers to be placed on one host. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--evaluate', choices=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], required=True, help="""A: vanilla (vsomeip as it is),
                                                                                                                        B: w/ DNSSEC w/o SOME/IP SD,
                                                                                                                        C: w/ service authentication,
                                                                                                                        D: w/ service authentication + DNSSEC + DANE w/o SOME/IP SD,
                                                                                                                        E: w/ service and client authentiction,
                                                                                                                        F: w/ service and client authentiction + payload encryption,
                                                                                                                        G: w/ service and client authentication + DNSSEC + DANE,
                                                                                                                        H: w/ service and client authentication + DNSSEC + DANE + payload encryption""")
    parser.add_argument('--runs', type=int, metavar='N', required=False, help='Specify the number of runs for the evaluation or omit this parameter to start the interactive mode with mininet CLI')
    parser.add_argument('--clean-start', dest='clean_start', action='store_true', help='Removes certificates and host configs causing them to be recreated')

    args = parser.parse_args()
    pub_count = args.pubs
    sub_count = args.subsperpub
    scenario = ScalabilityScenario()
    scenario.set_parameters(pub_count, sub_count, args.pubsperhost, args.onesubhost)

    host_count = scenario._get_publisher_host_id(pub_count)
    if args.onesubhost:
        host_count += sub_count
    else:
        host_count += pub_count * sub_count

    print("Host count: ", host_count)
    evaluation_option = args.evaluate
    total_evaluation_runs = args.runs
    add_compile_definitions = scenario.COMPILE_DEFINITIONS[evaluation_option]

    print("Cleaning up mininet interfaces ... ")
    subprocess.run(['mn', '-c'])
    scenario.cleanup()
    print("Done")

    # remove configs and certificates for clean start
    if args.clean_start:
        print("Removing configs and certificates ... ")
        subprocess.run(f"rm -f {CONFIG_PATH}/h*.json", shell=True)
        subprocess.run(f"rm -f {CERT_PATH}/*", shell=True)
        scenario.reset_zone_files()
        print("Done.")

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    dns_host_name = ""
    if scenario.WITH_DNSSEC in add_compile_definitions:
        topo = simple_topo(n=host_count + 1)
        dns_host_name = "h" + str(host_count + 1)
    else:
        topo = simple_topo(n=host_count)

    net = Mininet(topo=topo, controller=None, switch=OVSBridge, link=TCLink)
    net.start()
    for host in net.hosts:
        scenario.add_default_route(host)
    print("Done.")

    # build vsomeip
    print("Building vsomeip ... ")
    subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
    scenario.build_vsomeip()
    print("Done.")

    # create host configs and certificates
    print("Creating host configs and certificates ... ")
    scenario.create_publishers(net, dns_host_name)
    scenario.create_subscribers(net, dns_host_name)
    scenario.reference_certificates(net)
    print("Done.")

    # Evaluate
    if args.evaluate and args.runs:
        scenario.start_evaluation(total_evaluation_runs, evaluation_option, add_compile_definitions, net, dns_host_name)

    print("Stopping mininet network")
    net.stop()
    scenario.cleanup()
    print("Done.")

else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-1sw-Nhosts.py --topo simple_topo
    topos = {'simple_topo': (lambda: simple_topo())}
