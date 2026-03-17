#!/usr/bin/python

"""Scalability topology scenario with multiple publishers and subscribers.

N hosts directly connected to one switch, with configurable numbers of
publishers and subscribers per publisher.
"""

import argparse
import subprocess
import sys
import os
import time
from datetime import datetime
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tqdm import tqdm

from mininet_vsomeip_base_scenario import VSomeIPTopologyBase, _get_parser_with_common_args


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

    def create_publishers(self, net):
        """Create all publisher configurations and certificates."""
        for i in tqdm(range(1, self.pub_count + 1), desc="Creating publishers", unit="pub"):
            host_id = self._get_publisher_host_id(i)
            host = net[f'h{host_id}']
            self.create_publisher_config(host, i)
            self.create_publisher_certificate(host, i)

    def create_subscribers(self, net):
        """Create all subscriber configurations and certificates."""
        client_id = 1 # we need a unique client id for each subscriber
        total_subs = self.pub_count * self.sub_count
        with tqdm(total=total_subs, desc="Creating subscribers", unit="sub") as pbar:
            for i in range(1, self.pub_count + 1):
                for j in range(1, self.sub_count + 1):
                    sub_host_id = self._get_subscriber_host_id(i, j)
                    sub_host = net[f'h{sub_host_id}']
                    self.create_subscriber_config(sub_host, i, client_id)
                    self.create_subscriber_certificate(sub_host, i, client_id)
                    client_id += 1
                    pbar.update(1)

if __name__ == '__main__':
    parser = _get_parser_with_common_args()
    parser.add_argument('--pubs', type=int, metavar='N', required=True, choices=range(1, 0xffff + 1), help='Specify the number of publishers. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--onesubhost', dest='onesubhost', action='store_true', help='Use only one subscriber host for all subscribers')
    parser.add_argument('--subsperpub', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of subscribers per publisher. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--pubsperhost', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of publishers to be placed on one host. (between 1 (inclusive) and 65536 (exclusive))')

    args = parser.parse_args()
    pub_count = args.pubs
    sub_count = args.subsperpub
    scenario = ScalabilityScenario()
    scenario.set_copy_logs(args.copy_logs)
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
        scenario.delete_configs_and_certs()
        print("Done.")

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    dns_host_name = ""
    if scenario.WITH_DNSSEC in add_compile_definitions:
        topo = simple_topo(n=host_count + 1)
        dns_host_name = "h" + str(host_count + 1)
        scenario.dns_host_name = dns_host_name
    else:
        topo = simple_topo(n=host_count)

    net = Mininet(topo=topo, controller=None, switch=OVSBridge, link=TCLink)
    net.start()
    scenario.make_switches_traditional(net)
    scenario.add_default_route_to_hosts(net)
    if scenario.WITH_DNSSEC in add_compile_definitions:
        scenario.dns_host_hex_ip = scenario._get_dns_host_ip_in_hex(net, dns_host_name)
    print("Done.")

    # build vsomeip
    print("Building vsomeip ... ")
    scenario.build_vsomeip(add_compile_definitions)
    print("Done.")

    # create host configs and certificates
    if args.clean_start:
        print("Creating host configs and certificates ... ")
        scenario.create_subscribers(net)
        scenario.create_publishers(net)
        scenario.reference_certificates()
        print("Done.")
    else:
        print("Reusing existing host configs and certificates ... ")

    # Evaluate
    if args.evaluate and args.runs:
        scenario.start_evaluation(total_evaluation_runs, evaluation_option, args.repeat_on_failure, add_compile_definitions, net)

    print("Stopping mininet network")
    net.stop()
    scenario.cleanup()
    print("Done.")
