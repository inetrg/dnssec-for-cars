#!/usr/bin/python

"""Carnet topology scenario with predefined publisher/subscriber definitions.

Custom topology matching a car network architecture with named communication
endpoints loaded from JSON configuration files.
"""

import argparse
import subprocess
import sys
import json
import os
import time
from datetime import datetime
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mininet_vsomeip_base_scenario import VSomeIPTopologyBase, _get_parser_with_common_args
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
        """Get multicast IP from publishers.json or use default."""
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

    def create_publishers(self, net):
        """Create all publisher configurations and certificates."""
        with open(f"{self.SCENARIO_PATH}/publishers.json", "r") as service_file:
            services = json.load(service_file)
        with tqdm(total=len(services), desc="Creating publishers", unit="pub") as pbar:
            for service in services:
                net_name = services[service]["host"].lower()
                service_id = services[service]["serviceId"]
                host = net[net_name]
                if host is None:
                    print(f"Error: Host {net_name} not found in topology. Skipping publisher for service {service_id}.")
                    continue
                self.create_publisher_config(host, service_id)
                self.create_publisher_certificate(host, service_id)
                pbar.update(1)

    def create_subscribers(self, net):
        """Create all subscriber configurations and certificates."""
        with open(f"{self.SCENARIO_PATH}/subscribers.json", "r") as service_file:
            clients = json.load(service_file)
        with tqdm(total=len(clients), desc="Creating subscribers", unit="sub") as pbar:
            for client in clients:
                service_id = clients[client]["serviceId"]
                client_id = clients[client]["clientId"]
                net_name = clients[client]["host"].lower()
                host = net[net_name]
                if host is None:
                    print(f"Error: Host {net_name} not found in topology. Skipping subscriber with id {client_id} for service {service_id}.")
                    continue
                self.create_subscriber_config(host, service_id, client_id)
                self.create_subscriber_certificate(host, service_id, client_id)
                pbar.update(1)

if __name__ == '__main__':
    parser = _get_parser_with_common_args()
    
    args = parser.parse_args()
    evaluation_option = args.evaluate
    total_evaluation_runs = args.runs

    scenario = CarNetScenario()
    scenario.set_copy_logs(args.copy_logs)

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
    topo = car_topo()
    dns_host_name = DNS_HOST_NAME
    scenario.dns_host_name = dns_host_name
    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()
    scenario.make_switches_traditional(net)
    scenario.add_default_route_to_hosts(net)
    scenario.dns_host_hex_ip = scenario._get_dns_host_ip_in_hex(net, dns_host_name)
    print("Done.")

    # build vsomeip
    print("Building vsomeip ... ")
    scenario.build_vsomeip(add_compile_definitions)
    print("Done.")

    # create host configs and certificates
    
    if args.clean_start:
        print("Creating host configs and certificates ... (this may take a while)")
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
