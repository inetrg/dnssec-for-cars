#!/usr/bin/python

"""Carnet topology scenario with predefined publisher/subscriber definitions.

Custom topology matching a car network architecture with named communication
endpoints loaded from JSON configuration files.
"""

import argparse
import sys
import json
from pathlib import Path

from mininet.topo import Topo

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mininet_vsomeip_base_scenario import VSomeIPTopologyBase
from tqdm import tqdm

DNS_HOST_NAME = 'dns'

class car_topo(Topo):
    """CarNet topology with switches and named hosts."""

    def build(self):
        """Create custom CarNet topology."""
        # Add switches
        sFR = self.addSwitch('s1')
        sFL = self.addSwitch('s2')
        sC = self.addSwitch('s3')
        sRR = self.addSwitch('s4')
        sRL = self.addSwitch('s5')

        # Add hosts (names must be lower case!)
        zcRl = self.addHost('zcrl')
        zcFl = self.addHost('zcfl')
        zcRr = self.addHost('zcrr')
        zcFr = self.addHost('zcfr')
        lRL = self.addHost('lrl')
        lFL = self.addHost('lfl')
        lRR = self.addHost('lrr')
        lFR = self.addHost('lfr')
        cR = self.addHost('cr')
        cF = self.addHost('cf')
        adas = self.addHost('adas')
        inf = self.addHost('inf')
        con = self.addHost('con')
        dns = self.addHost(DNS_HOST_NAME)

        # Add links
        self.addLink(sRL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sC, dns, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRL, zcRl, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, zcFl, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, zcRr, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, zcFr, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRL, lRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, lFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, lRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, lFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRL, cR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, cF, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, adas, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, inf, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, con, bw=1000, delay='0ms', loss=0, max_queue_size=99999)


class CarNetScenario(VSomeIPTopologyBase):
    """CarNet scenario with JSON-defined publishers and subscribers."""

    SCENARIO_FOLDER = "carnet"

    def __init__(self):
        """Initialize scenario."""
        super().__init__()
        self.scenario_dirs(self.SCENARIO_FOLDER)

    def get_publisher_multicast_ip(self, service_id):
        """Get multicast IP from publishers.json or use default. Overrides method from base scenario."""
        with open(f"{self.SCENARIO_PATH}/publishers.json", "r") as f:
            services = json.load(f)
        for service in services:
            if services[service]["serviceId"] == service_id:
                mcast_ip = services[service]["mcast"]
                if mcast_ip is not None:
                    return mcast_ip
                break
        # Fallback calculation
        lowerTwoDigetsServiceId = service_id % 256
        upperTwoDigetsServiceId = service_id // 256
        mcast_ip =  "224.1." + str(upperTwoDigetsServiceId) + "." + str(lowerTwoDigetsServiceId)
        print (f"Service {service_id} has no multicast IP. Selecting {mcast_ip} as multicast IP.")
        return mcast_ip

    # ========== CONFIGURATION CREATION ==========

    # ========== MANAGER/APP STARTUP ==========

    # ========== EVALUATION SUPPORT ==========

    def create_publishers(self):
        """Create all publisher configurations and certificates. Overrides abstract method from base scenario."""
        with open(f"{self.SCENARIO_PATH}/publishers.json", "r") as service_file:
            services = json.load(service_file)
        with tqdm(total=len(services), desc="Creating publishers", unit="pub") as pbar:
            for service in services:
                net_name = services[service]["host"].lower()
                service_id = services[service]["serviceId"]
                host = self.net[net_name]
                if host is None:
                    print(f"Error: Host {net_name} not found in topology. Skipping publisher for service {service_id}.")
                    continue
                self.create_publisher_config(host, service_id)
                self.create_publisher_certificate(host, service_id)
                pbar.update(1)

    def create_subscribers(self):
        """Create all subscriber configurations and certificates. Overrides abstract method from base scenario."""
        with open(f"{self.SCENARIO_PATH}/subscribers.json", "r") as service_file:
            clients = json.load(service_file)
        with tqdm(total=len(clients), desc="Creating subscribers", unit="sub") as pbar:
            for client in clients:
                service_id = clients[client]["serviceId"]
                client_id = clients[client]["clientId"]
                net_name = clients[client]["host"].lower()
                host = self.net[net_name]
                if host is None:
                    print(f"Error: Host {net_name} not found in topology. Skipping subscriber with id {client_id} for service {service_id}.")
                    continue
                self.create_subscriber_config(host, service_id, client_id)
                self.create_subscriber_certificate(host, service_id, client_id)
                pbar.update(1)

if __name__ == '__main__':
    scenario = CarNetScenario()
    parser = scenario.get_parser_with_common_args()
    args = parser.parse_args()
    scenario.setup_evaluation(args, car_topo(), DNS_HOST_NAME)
    scenario.run_evaluation()
