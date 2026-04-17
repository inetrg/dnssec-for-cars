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

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tqdm import tqdm

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

    def add_specific_args(self, parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
        """Add specific arguments for this scenario."""
        parser.add_argument('--pubs', type=int, metavar='N', required=True, choices=range(1, 0xffff + 1), help='Specify the number of publishers. (between 1 (inclusive) and 65536 (exclusive))')
        parser.add_argument('--onesubhost', dest='onesubhost', action='store_true', help='Use only one subscriber host for all subscribers')
        parser.add_argument('--subsperpub', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of subscribers per publisher. (between 1 (inclusive) and 65536 (exclusive))')
        parser.add_argument('--pubsperhost', type=int, metavar='N', required=False, default=1, choices=range(1, 0xffff + 1), help='Specify the number of publishers to be placed on one host. (between 1 (inclusive) and 65536 (exclusive))')
        return parser

    def handle_specific_args(self, args):
        """Handle specific scenario arguments."""
        self.pub_count = args.pubs
        self.sub_count = args.subsperpub
        self.pubs_per_host = args.pubsperhost
        self.one_sub_host = args.onesubhost

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

    def _get_host_count(self):
        host_count = self._get_publisher_host_id(self.pub_count)
        if self.one_sub_host:
            host_count += self.sub_count
        else:
            host_count += self.pub_count * self.sub_count
        return host_count

    def get_statistics_result_path(self):
        return f"{self.SCENARIO_PATH}/statistic-results/{self.evaluation_option}-series/p{self.pub_count}_s{self.sub_count}/run-{self.current_run}"
    
    # ========== CONFIGURATION CREATION ==========

    # ========== MANAGER/APP STARTUP ==========

    # ========== EVALUATION SUPPORT ==========

    # ========== PUBLISHER/SUBSCRIBER SETUP ==========

    def create_publishers(self):
        """Create all publisher configurations and certificates."""
        with tqdm(total=self.pub_count, desc="Creating publishers", unit="pub") as pbar:
            for i in range(1, self.pub_count + 1):
                host_id = self._get_publisher_host_id(i)
                host = self.net[f'h{host_id}']
                self.create_publisher_config(host, i)
                self.create_publisher_certificate(host, i)
                pbar.update(1)

    def create_subscribers(self):
        """Create all subscriber configurations and certificates."""
        client_id = 1 # we need a unique client id for each subscriber
        total_subs = self.pub_count * self.sub_count
        with tqdm(total=total_subs, desc="Creating subscribers", unit="sub") as pbar:
            for i in range(1, self.pub_count + 1):
                for j in range(1, self.sub_count + 1):
                    sub_host_id = self._get_subscriber_host_id(i, j)
                    sub_host = self.net[f'h{sub_host_id}']
                    self.create_subscriber_config(sub_host, i, client_id)
                    self.create_subscriber_certificate(sub_host, i, client_id)
                    client_id += 1
                    pbar.update(1)

if __name__ == '__main__':
    scenario = ScalabilityScenario()
    parser = scenario.get_parser_with_common_args()
    parser = scenario.add_specific_args(parser)
    args = parser.parse_args()
    scenario.handle_common_args(args)
    scenario.handle_specific_args(args)

    host_count = scenario._get_host_count()
    print("Host count: ", host_count)
    dns_host_name = ""
    if scenario.WITH_DNSSEC in scenario.add_compile_definitions:
        host_count += 1
        dns_host_name = "h" + str(host_count)

    scenario.setup_evaluation(args, simple_topo(n=host_count), dns_host_name)
    scenario.run_evaluation()
