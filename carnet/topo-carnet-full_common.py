#!/usr/bin/python

"""Carnet topology scenario with predefined publisher/subscriber definitions.

Custom topology matching a car network architecture with named communication
endpoints loaded from JSON configuration files.
"""

import argparse
import subprocess
import json
import os
import time
from datetime import datetime
from pathlib import Path

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel

from mininet_vsomeip_base_scenario import VSomeIPTopologyBase


DNS_HOST_NAME = 'dns'
PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"
SCENARIO_PATH = f"{PROJECT_PATH}/carnet"
LOGS_PATH = f"/var/log/carnet"


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

    # Scenario-specific paths
    SCENARIO_PATH = SCENARIO_PATH
    CONFIG_PATH = f"{SCENARIO_PATH}/vsomeip-configs"
    CERT_PATH = f"{SCENARIO_PATH}/certificates"
    ZONE_PATH = f"{SCENARIO_PATH}/zones"
    LOGS_PATH = LOGS_PATH

    # Scenario-specific port configuration
    PUBLISHER_PORT = 10000
    SUBSCRIBER_PORT = 20000
    EVENT_ID_1 = 30000
    EVENT_ID_2 = 40000
    EVENT_GROUP_ID = 50000

    def __init__(self):
        """Initialize scenario."""
        super().__init__()
        self.service_sub_counts = {}
        self.managers = {}
        self.eval_start = time.time()
        self.copy_logs_flag = False

    def set_copy_logs(self, copy_logs: bool):
        """Enable/disable log copying after evaluation runs."""
        self.copy_logs_flag = copy_logs

    def get_publisher_multicast_ip(self, service_id):
        """Get multicast IP from publishers.json or use default."""
        try:
            with open(f"{self.SCENARIO_PATH}/publishers.json", "r") as f:
                services = json.load(f)
            for service in services:
                if services[service]["serviceId"] == service_id:
                    mcast_ip = services[service].get("mcast")
                    if mcast_ip:
                        return mcast_ip
        except:
            pass
        # Fallback calculation
        lowerTwoDigetsServiceId = service_id % 256
        upperTwoDigetsServiceId = service_id // 256
        return "224.1." + str(upperTwoDigetsServiceId) + "." + str(lowerTwoDigetsServiceId)

    def _make_switch_traditional(self, net, switch: str):
        """Configure switch for traditional operation."""
        net[switch].cmd('ovs-ofctl add-flow {} action=normal'.format(switch))

    # ========== CONFIGURATION CREATION ==========

    # ========== MANAGER/APP STARTUP ==========

    def start_subscribers(self, net):
        """Start all subscriber applications."""
        with open(f"{self.SCENARIO_PATH}/subscribers.json", "r") as service_file:
            clients = json.load(service_file)

        for client in clients:
            service_id = clients[client]["serviceId"]
            client_id = clients[client]["clientId"]
            host_name = clients[client]["host"].lower()
            app_name = self.get_subscriber_app_name(net[host_name], service_id, client_id)

            if self.managers.get(host_name) == app_name:
                continue

            self.start_someip_subscriber_app(net[host_name], service_id, client_id)
            self.num_subs_started += 1
            time.sleep(0.01)

    # ========== EVALUATION SUPPORT ==========

    def _process_evaluation_run(self, evaluation_option, run, return_code):
        """Process evaluation run - copy logs if enabled."""
        if self.copy_logs_flag:
            self._copy_logs_to_scenario_folder(evaluation_option, run, return_code)

    def _copy_logs_to_scenario_folder(self, evaluation_option: str, run: int, return_code: int, move_logs: bool = True):
        """Copy or move logs to scenario folder."""
        time_stamp = datetime.fromtimestamp(self.eval_start).strftime("%Y%m%d-%H%M%S")
        out_path = f"{self.SCENARIO_PATH}/logs/{evaluation_option}-series/{time_stamp}/run-{run}-"
        subprocess.run(f"rm -rf {out_path}*", shell=True, check=True)

        if return_code == 0:
            out_path += "success"
        else:
            out_path += "failure"

        os.makedirs(out_path, exist_ok=True)

        if move_logs:
            subprocess.run(f"mv {self.LOGS_PATH}/*.log {out_path}/", shell=True, check=True)
        else:
            subprocess.run(f"cp {self.LOGS_PATH}/*.log {out_path}/", shell=True, check=True)

    def create_publishers(self, net, dns_host_name=None):
        """Create all publisher configurations and certificates."""
        dns_host_ip_in_hex = None
        if dns_host_name is not None:
            dns_host = net[dns_host_name]
            dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
            ip_bytes = dns_host_ip.split(".")
            ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
            dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"

        with open(f"{self.SCENARIO_PATH}/publishers.json", "r") as service_file:
            services = json.load(service_file)

        for service in services:
            net_name = services[service]["host"].lower()
            service_id = services[service]["serviceId"]
            self.create_publisher_config(net[net_name], service_id)
            self.create_publisher_certificate(net[net_name], service_id)
            if dns_host_ip_in_hex:
                self._set_dns_server_ip(net[net_name], dns_host_ip_in_hex)

    def create_subscribers(self, net, dns_host_name=None):
        """Create all subscriber configurations and certificates."""
        dns_host_ip_in_hex = None
        if dns_host_name is not None:
            dns_host = net[dns_host_name]
            dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
            ip_bytes = dns_host_ip.split(".")
            ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
            dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"

        with open(f"{self.SCENARIO_PATH}/subscribers.json", "r") as service_file:
            clients = json.load(service_file)

        for client in clients:
            service_id = clients[client]["serviceId"]
            client_id = clients[client]["clientId"]
            net_name = clients[client]["host"].lower()
            self.create_subscriber_config(net[net_name], service_id, client_id)
            self.create_subscriber_certificate(net[net_name], service_id, client_id)
            if dns_host_ip_in_hex:
                self._set_dns_server_ip(net[net_name], dns_host_ip_in_hex)

    def _set_dns_server_ip(self, host, dns_host_ip_in_hex):
        """Set DNS server IP in host configuration."""
        host_name = host.__str__()
        host_config = f"{self.CONFIG_PATH}/{host_name}.json"
        if Path(host_config).is_file():
            with open(host_config, 'r') as file:
                config = json.load(file)
            config['dns-server-ip'] = dns_host_ip_in_hex
            with open(host_config, 'w') as file:
                json.dump(config, file, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Starts vsomeip w/ or w/o security mechanisms and collects timestamps of handshake events')
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
    parser.add_argument('--copy-logs', dest='copy_logs', action='store_true', default=False, help='Copy logs to scenario folder for every evaluation run')

    args = parser.parse_args()
    evaluation_option = args.evaluate
    total_evaluation_runs = args.runs

    scenario = CarNetScenario()
    scenario.set_copy_logs(args.copy_logs)

    add_compile_definitions = scenario.COMPILE_DEFINITIONS[evaluation_option]

    print("Cleaning up mininet interfaces ... ")
    subprocess.run(['mn', '-c'])
    scenario.cleanup()
    subprocess.run(f"rm -f {LOGS_PATH}/*", shell=True)
    print("Done")

    # remove configs and certificates for clean start
    if args.clean_start:
        print("Removing configs and certificates ... ")
        for file in Path(f"{SCENARIO_PATH}/vsomeip-configs").glob("*.json"):
            if not file.name.startswith("vsomeip-udp-mininet"):
                subprocess.run(f"rm -f {file}", shell=True)
        subprocess.run(f"rm -f {SCENARIO_PATH}/certificates/*", shell=True)
        scenario.reset_zone_files()
        print("Done.")

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    topo = car_topo()
    dns_host_name = DNS_HOST_NAME
    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()

    scenario_instance = CarNetScenario()
    for switch in net.switches:
        scenario_instance._make_switch_traditional(net, switch.__str__())

    for host in net.hosts:
        scenario.add_default_route(host)

    print("Done.")

    # build vsomeip
    print("Building vsomeip ... ")
    subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
    scenario.build_vsomeip()
    print("Done.")

    # create host configs and certificates
    print("Creating host configs and certificates ... (this may take a while)")
    if args.clean_start:
        scenario.create_publishers(net, dns_host_name)
        scenario.create_subscribers(net, dns_host_name)

    scenario.reference_certificates()
    print("Done.")

    # Evaluate
    if args.evaluate and args.runs:
        scenario.start_evaluation(total_evaluation_runs, evaluation_option, add_compile_definitions, net, dns_host_name)

    print("Stopping mininet network")
    net.stop()
    print("Done.")

else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-carnet-full.py --topo car_topo
    topos = {'car_topo': (lambda: car_topo())}
