#!/usr/bin/python

"""Scalability topology scenario with multiple publishers and subscribers.

N hosts directly connected to one switch, with configurable numbers of
publishers and subscribers per publisher.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSBridge
from mininet.link import TCLink
from mininet.log import setLogLevel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
        for i in range(1, self.pub_count + 1):
            host_id = self._get_publisher_host_id(i)
            print(f"Creating publisher {i}/{self.pub_count} on host h{host_id}")
            host = net[f'h{host_id}']
            self.create_publisher_config(host, i)
            self.create_publisher_certificate(host, i)

    def create_subscribers(self, net, dns_host=None):
        """Create all subscriber configurations and certificates."""
        for i in range(1, self.pub_count + 1):
            for j in range(1, self.sub_count + 1):
                sub_host_id = self._get_subscriber_host_id(i, j)
                sub_host = net[f'h{sub_host_id}']
                print(f"Creating subscriber {i}/{self.pub_count} - {j}/{self.sub_count} on host h{sub_host_id}")
                self.create_subscriber_config(sub_host, i, j)
                self.create_subscriber_certificate(sub_host, i, j)


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
    parser.add_argument('--repeat-on-failure', dest='repeat_on_failure', action='store_true', help='Repeats a run in case of failure.')
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
    for host in net.hosts:
        scenario.add_default_route(host)
    if scenario.WITH_DNSSEC in add_compile_definitions:
        scenario.dns_host_hex_ip = scenario._get_dns_host_ip_in_hex(net, dns_host_name)
    print("Done.")

    # build vsomeip
    print("Building vsomeip ... ")
    scenario.build_vsomeip(add_compile_definitions)
    print("Done.")

    # create host configs and certificates
    print("Creating host configs and certificates ... ")
    scenario.create_publishers(net, dns_host_name)
    scenario.create_subscribers(net, dns_host_name)
    scenario.reference_certificates()
    print("Done.")

    # Evaluate
    if args.evaluate and args.runs:
        scenario.start_evaluation(total_evaluation_runs, evaluation_option, args.repeat_on_failure, add_compile_definitions, net)

    print("Stopping mininet network")
    net.stop()
    scenario.cleanup()
    print("Done.")
