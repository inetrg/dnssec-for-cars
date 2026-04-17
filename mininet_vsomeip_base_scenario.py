#!/usr/bin/python

"""Common base class for SOME/IP evaluation scenarios.

This module provides a reusable foundation for SOME/IP topology scenarios,
extracting common functionality and providing a well-organized interface
for scenario-specific implementations.
"""

import argparse
import subprocess
import json
import os
import time
from datetime import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from subprocess import TimeoutExpired, Popen
from itertools import combinations
from collections import defaultdict
import re

from tqdm import tqdm

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections, dumpNetConnections

class CaptureUtils:
    """Utility class for managing network captures using dumpcap."""

    # Capture settings
    CAPTURE_BUFSIZE_MB = 100
    CAPTURE_FILTER = "udp port 30490 or udp port 53 or tcp port 53" # filter SOME/IP Discovery (udp port 30490) and DNS traffic (udp port 53, tcp port 53)

    def __init__(self):
        start_time = time.time()
        self.tmp_path = f"/tmp/capture-{datetime.fromtimestamp(start_time).strftime('%Y%m%d-%H%M%S')}"
        Path(self.tmp_path).mkdir(parents=True, exist_ok=True)
        self.processes = []

    def launch_dumpcap(self, node: Node, interface: str):
        filename = f"{self.tmp_path}/{node.name}.pcapng"
        cmd = [
            "dumpcap",
            "-i",
            interface,
            "-f",
            f"{self.CAPTURE_FILTER}",
            "-w",
            filename,
            "-B",
            f"{self.CAPTURE_BUFSIZE_MB}",
        ]
        process = node.popen(cmd)
        # check if process started successfully
        time.sleep(0.1)  # give it a moment to start
        if process.poll() is not None:
            raise RuntimeError(f"Failed to start dumpcap on {node.name} interface {interface}. Command: {' '.join(cmd)}")
        self.processes.append(process)

    def start_dumpcap_on_hosts(self, net: Mininet):
        with tqdm(total=len(net.hosts), desc="Starting dumpcap on hosts", unit="hosts") as pbar:
            for host in net.hosts:
                # list interfaces on host and launch dumpcap on all of them
                interfaces = host.intfs.values()
                for interface in interfaces:
                    self.launch_dumpcap(host, interface.name)
                pbar.update(1)

    def start_dumpcap_on_switches(self, net: Mininet):
        with tqdm(total=len(net.switches), desc="Starting dumpcap on switches", unit="switches") as pbar:
            for switch in net.switches:
                # list interfaces on switch and launch dumpcap on all of them
                interfaces = switch.intfs.values()
                for interface in interfaces:
                    self.launch_dumpcap(switch, interface.name)
                pbar.update(1)

    def stop_all_dumpcap_processes(self):
        for process in self.processes:
            process.terminate()
        for process in self.processes:
            try:   
                process.wait(timeout=1)
            except TimeoutExpired:
                process.kill()

    def finalize_captures(self, capture_path):
        self.stop_all_dumpcap_processes()
        time.sleep(0.1)
        # copy from tmp to final location
        Path(capture_path).mkdir(parents=True, exist_ok=True)
        subprocess.run(f"mv {self.tmp_path}/*.pcapng {capture_path}/", shell=True, check=True)
        subprocess.run(f"chown -R vm-user:vm-user {capture_path}", shell=True, check=True)

class VSomeIPTopologyBase(ABC):
    """Base class for SOME/IP evaluation scenarios.

    Subclasses should set class variables for scenario-specific configuration
    and implement abstract methods for scenario-specific behavior.
    """

    # ========== TIER 1: CORE CONSTANTS ==========

    # SOME/IP identifiers (shared across all scenarios)
    INSTANCE_ID_INT = 1
    INSTANCE_ID_HEX_STR = "0x{:04x}".format(INSTANCE_ID_INT)
    INSTANCE_ID = str(int(INSTANCE_ID_INT))
    MAJOR_VERSION = "0"
    MINOR_VERSION = "0"
    PROTOCOL = "UDP"

    # Compile definition flags
    WITH_SERVICE_AUTHENTICATION = 'WITH_SERVICE_AUTHENTICATION'
    WITH_CLIENT_AUTHENTICATION = 'WITH_CLIENT_AUTHENTICATION'
    NO_SOMEIP_SD = 'NO_SOMEIP_SD'
    WITH_DNSSEC = 'WITH_DNSSEC'
    WITH_DANE = 'WITH_DANE'
    WITH_ENCRYPTION = 'WITH_ENCRYPTION'

    # Compile definitions mapping (identical for all scenarios)
    COMPILE_DEFINITIONS = {
        'A': '',
        'B': f'{NO_SOMEIP_SD} {WITH_DNSSEC}',
        'C': f'{WITH_SERVICE_AUTHENTICATION}',
        'D': f'{NO_SOMEIP_SD} {WITH_SERVICE_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
        'E': f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION}',
        'F': f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_ENCRYPTION}',
        'G': f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
        'H': f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE} {WITH_ENCRYPTION}',
    }

    # ========== TIER 1: SCENARIO CONFIGURATION (set by subclass) ==========

    PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"
    SCENARIO_PATH = None  # Must be set by subclass
    CONFIG_PATH = None  # Must be set by subclass
    CONFIG_TEMPLATE_PATH = PROJECT_PATH + "/template-configs/vsomeip-udp-mininet-multihost.json" # May be set by subclass
    CERT_PATH = None  # Must be set by subclass
    ZONE_PATH = None  # Must be set by subclass
    SCRIPT_PATH = PROJECT_PATH + "/scripts" # May be set by subclass
    LOGS_PATH = None  # May be set by subclass
    STATISTICS_PATH = None  # May be set by subclass
    CAPTURE_PATH = None # May be set by subclass
    NSD_CONF_PATH = f"{PROJECT_PATH}/nsd/nsd.conf"

    # ========== TIER 2: CONFIGURABLE CONSTANTS ==========

    PUBLISHER_PORT = 10000
    SUBSCRIBER_PORT = 20000
    EVENT_ID_1 = 30000
    EVENT_ID_2 = 40000
    EVENT_GROUP_ID = 50000
    PUBLISHER_MCAST_PORT = 60000

    # Pkill patterns (may be overridden)
    SUBSCRIBER_PROGRAM = "my-subscriber"
    PUBLISHER_PROGRAM = "my-publisher"

    # State tracking
    STD_CONDITION = False

    def __init__(self):
        """Initialize scenario instance."""
        self.num_pubs_started = 0
        self.num_subs_started = 0
        self.hosts = []
        self.subscribers = {}
        self.publishers = {}
        self.managers = {}
        self.service_sub_counts = {}
        self.dns_host_name = ""
        self.dns_host_hex_ip = None
        self.copy_logs = False
        self.capture = CaptureUtils()
        self.capture_arg = False
        self.net = None

    def get_parser_with_common_args(self):
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
        parser.add_argument('--max-retries', type=int, metavar='N', default=0, help='Maximum number of retries for a failed run. Default is 0 = no retries.')
        parser.add_argument('--clean-start', dest='clean_start', action='store_true', help='Removes certificates and host configs causing them to be recreated')
        parser.add_argument('--copy-logs', dest='copy_logs', action='store_true', default=False, help='Copy logs to scenario folder for every evaluation run')
        parser.add_argument('--copy-logs-on-failure', dest='copy_logs_on_failure', action='store_true', default=False, help='Copy logs to scenario folder for every failed evaluation run (overrides --copy-logs)')
        parser.add_argument('--capture', dest='capture', action='store_true', help='Start capture process to record network traffic during evaluation')
        parser.add_argument('--vsomeip-no-logging', dest='vsomeip_no_logging', action='store_true', help='Disable most logging in vsomeip')
        return parser
    
    def handle_common_args(self, args):
        """Handle common command-line arguments and set up scenario accordingly."""
        self.evaluation_option = args.evaluate
        self.capture_arg = args.capture
        self.total_evaluation_runs = args.runs
        self.add_compile_definitions = self.COMPILE_DEFINITIONS[args.evaluate]
        self.copy_logs = args.copy_logs
        self.copy_logs_on_failure = args.copy_logs_on_failure
        self.vsomeip_no_logging = args.vsomeip_no_logging
        self.clean_start = args.clean_start
        self.max_retries = args.max_retries

    def scenario_dirs(self, scenario_folder):
        """Set up scenario-specific directories."""
        self.SCENARIO = scenario_folder
        self.SCENARIO_PATH = f"{self.PROJECT_PATH}/{scenario_folder}"
        self.CONFIG_PATH = f"{self.SCENARIO_PATH}/vsomeip-configs"
        self.CERT_PATH = f"{self.SCENARIO_PATH}/certificates"
        self.ZONE_PATH = f"{self.SCENARIO_PATH}/zones"
        # self.SCRIPT_PATH = f"{self.SCENARIO_PATH}/scripts"
        self.LOGS_PATH = f"{self.SCENARIO_PATH}/logs"
        self.CAPTURE_PATH = f"{self.SCENARIO_PATH}/capture"
        self.STATISTICS_PATH = f"{self.SCENARIO_PATH}/statistic-results"

        Path(self.CONFIG_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.CERT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.LOGS_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.CAPTURE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.STATISTICS_PATH).mkdir(parents=True, exist_ok=True)

    # ========== TIER 1 & 2: NETWORK UTILITIES (SHARED) ==========

    def dump_switch_information(self, switch: str):
        """Dump switch information using ovs-ofctl."""
        print("Dumping switch information w/ ovs-ofctl")
        print(self.net[switch].cmd('ovs-ofctl show {}'.format(switch)))

    def dump_switch_flows(self, switch: str):
        """Dump flow rules on a switch."""
        print("Dumping flow rules on {}".format(switch))
        print(self.net[switch].cmd('ovs-ofctl dump-flows {}'.format(switch)))

    def dump_infos(self):
        """Dump host and network connection information."""
        print("Dumping host connections")
        dumpNodeConnections(self.net.hosts)
        print("Dumping switch connections")
        dumpNodeConnections(self.net.switches)
        print("Dumping net connections")
        dumpNetConnections(self.net)

    def check_host_queue_overflows(self):
        """Check for queue overflows on host interfaces."""
        print("Checking for queue overflows on host interfaces")
        drops: dict[str, int] = {}
        for host in self.net.hosts:
            try:
                host_name = host.__str__()
                intf_name = f"{host_name}-eth0"
                output = host.cmd(f"tc -s qdisc show dev {intf_name}")
                rx_result = host.cmd(f"cat /sys/class/net/{host.name}-eth0/statistics/rx_dropped")
                tx_result = host.cmd(f"cat /sys/class/net/{host.name}-eth0/statistics/tx_dropped")
                rx_dropped = int(rx_result.strip())
                tx_dropped = int(tx_result.strip())
                overlimits_value = 0
                if "overlimits" in output:
                    lines = output.splitlines()
                    for line in lines:
                        if "overlimits" in line:
                            parts = line.strip().split()
                            overlimits_index = parts.index("overlimits")
                            if overlimits_index + 1 < len(parts):
                                overlimits_value = parts[overlimits_index + 1]
                if rx_dropped > 0 or tx_dropped > 0 or (overlimits_value.isdigit() and int(overlimits_value) > 0):
                    print(f"Host {host.name} tx_dropped: {tx_dropped} / rx_dropped: {rx_dropped} / overlimits: {overlimits_value}")
                    drops[host.name] = (rx_dropped, tx_dropped, int(overlimits_value) if overlimits_value.isdigit() else overlimits_value)
            except Exception as e:
                self.log.error(f"Failed to check drops for {host.name}: {e}")
        return drops

    def check_switch_queue_overflows(self):
        """Check for queue overflows on switch interfaces."""
        print("Checking for queue overflows on switch interfaces")
        drops: dict[str, int] = {}
        for switch in self.net.switches:
            switch_name = switch.__str__()
            # list switch interfaces
            interfaces = switch.cmd("ovs-vsctl list-ports {}".format(switch_name)).split()
            dropped: dict[str, int] = {}
            for intf in interfaces:
                output = switch.cmd(f"tc -s qdisc show dev {intf}")
                port_name: str | None = None
            for line in output.splitlines():
                port_match = re.match(r'\s*port\s+"([^"]+)":', line)
                if port_match:
                    port_name = port_match.group(1)
                    dropped[port_name] = 0  # Initialize
                elif port_name and ("rx pkts" in line or "tx pkts" in line):
                    drop_match = re.search(r"drop=(\d+)", line)
                    if drop_match:
                        dropped[port_name] += int(drop_match.group(1))
            if dropped and any(count > 0 for count in dropped.values()):
                print(f"Switch {switch_name} drops: {dropped}")
                drops[switch_name] = dropped
        return drops

    def simple_tests(self):
        """Test network connectivity and bandwidth."""
        print("Testing network connectivity")
        self.net.pingAll()
        print("Testing bandwidth between hosts")
        unique_host_tuples_set = set(combinations(self.net.hosts, 2))
        for host_tuple in unique_host_tuples_set:
            self.net.iperf(hosts=host_tuple, l4Type='TCP')
            self.net.iperf(hosts=host_tuple, l4Type='UDP')

    def add_default_route_to_hosts(self):
        """Add default route for each host."""
        for host in self.net.hosts:
            host_name = host.__str__()
            host.cmd(f'route add default gw 10.0.0.0 {host_name}-eth0')

    def make_switches_traditional(self):
        """Configure switches for traditional operation."""
        for switch in self.net.switches:
            switch_name = switch.__str__()
            self.net[switch_name].cmd('ovs-ofctl add-flow {} action=normal'.format(switch_name))

    # ========== TIER 2: INFRASTRUCTURE MANAGEMENT ==========

    def start_dns_server(self):
        """Start DNS server (NSD) on the specified host."""
        dns_host = self.net[self.dns_host_name]
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's|zonefile: \"[^\"]*zones/service\\.zone\"|zonefile: \"{self.ZONE_PATH}/service.zone\"|' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's|zonefile: \"[^\"]*zones/client\\.zone\"|zonefile: \"{self.ZONE_PATH}/client.zone\"|' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {self.ZONE_PATH}/service.zone")
        dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {self.ZONE_PATH}/client.zone")
        dns_host.cmd('nsd-control-setup')
        dns_host.cmd(f'nsd -c {self.NSD_CONF_PATH}')

    def stop_dns_server(self):
        """Stop DNS server (NSD)."""
        dns_host = self.net[self.dns_host_name]
        dns_host.cmd('nsd-control stop')
        dns_host.cmd('pkill nsd')

    def get_dns_host_ip_in_hex(self):
        if self.dns_host_hex_ip is not None and self.dns_host_hex_ip != "":
            return self.dns_host_hex_ip
        dns_host_ip_in_hex = None
        if self.dns_host_name is not None and self.dns_host_name != "":
            dns_host_obj = self.net[self.dns_host_name]
            dns_host_ip = dns_host_obj.IP(intf=dns_host_obj.defaultIntf())
            dns_host_ip_in_hex = self.convert_ip_to_hex(dns_host_ip)
        return dns_host_ip_in_hex

    def reset_zone_files(self):
        """Reset zone files to default state."""
        subprocess.run(["su", "-", "vm-user", "-c", f"{self.SCRIPT_PATH}/reset-zone-files.bash --zones-folder {self.ZONE_PATH} --zone-file client.zone --zone-file service.zone"], check=True)

    def build_vsomeip(self):
        """Build vsomeip project."""
        print("Building vsomeip ... ")
        # set compile opts
        subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({self.add_compile_definitions}\)/' {self.PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)

        subprocess.run(f'su - vm-user -c "cmake -B {self.PROJECT_PATH}/vsomeip/build -S {self.PROJECT_PATH}/vsomeip"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target all -- -j$(nproc)"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target examples -- -j$(nproc)"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target statistics-writer -- -j$(nproc)"', shell=True)
        print("Done.")

    def cleanup(self):
        """Clean up temporary files."""
        subprocess.run(["pkill", "statistics-writ"])
        subprocess.run(f"rm -f {self.PROJECT_PATH}/vsomeip-*", shell=True)
        subprocess.run(f"rm -f {self.PROJECT_PATH}/publisher-initialized*", shell=True)
        subprocess.run(f"rm -f {self.PROJECT_PATH}/subscriber-initialized*", shell=True)
        subprocess.run(f"rm -f {self.LOGS_PATH}/*.log", shell=True)
        subprocess.run(f"rm -f {self.LOGS_PATH}/*.std", shell=True)

    def delete_configs_and_certs(self):
        """Delete all generated configurations and certificates."""
        subprocess.run(f"rm -f {self.CONFIG_PATH}/*.json", shell=True)
        subprocess.run(f"rm -f {self.CERT_PATH}/*.pem", shell=True)
        self.reset_zone_files()

    def stop_subscriber_app(self, host):
        """Stop subscriber application on host."""
        host.cmd(f"pkill -f {self.SUBSCRIBER_PROGRAM}")

    def stop_publisher_app(self, host):
        """Stop publisher application on host."""
        host.cmd(f"pkill -f {self.PUBLISHER_PROGRAM}")

    # ========== TIER 2: PATH HELPERS (GENERIC) ==========

    def get_host_config_path(self, host_name):
        """Get host configuration file path."""
        return f"{self.CONFIG_PATH}/{host_name}.json"

    def get_publisher_app_name(self, host_name, service_id):
        """Get publisher application name."""
        return f"{host_name}-{service_id}"

    def get_subscriber_app_name(self, host_name, service_id, client_id):
        """Get subscriber application name."""
        return f"{host_name}-{service_id}-{client_id}"

    def get_publisher_app_id(self, host_name, service_id):
        """Get publisher app id."""
        return f"0x{int(service_id):04x}"

    def get_subscriber_app_id(self, host_name, service_id, client_id):
        """Get subscriber app id."""
        return f"0x{int(client_id):04x}"

    def get_publisher_cert_name(self, host_name, service_id):
        """Get publisher certificate name (without extension)."""
        return f'{host_name}_{service_id}'

    def get_subscriber_cert_name(self, host_name, service_id, client_id):
        """Get subscriber certificate name (without extension)."""
        return f'{host_name}_{client_id}'

    def get_cert_path(self, cert_name, cert_type):
        """Get full certificate path. cert_type should be 'service' or 'client'."""
        return f'{self.CERT_PATH}/{cert_name}.{cert_type}.cert.pem'

    def get_key_path(self, cert_name, cert_type):
        """Get full private key path. cert_type should be 'service' or 'client'."""
        return f'{self.CERT_PATH}/{cert_name}.{cert_type}.key.pem'

    def convert_ip_to_hex(self, ip_address: str) -> str:
        """Convert dotted decimal IP address to hex format (0xAABBCCDD)."""
        ip_bytes = ip_address.split(".")
        ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
        return f"0x{''.join(ip_bytes_in_hex)}"

    def reset_state(self):
        """Reset instance state counters for a new evaluation run."""
        self.num_pubs_started = 0
        self.num_subs_started = 0

    def get_publisher_multicast_ip(self, service_id):
        """Calculate multicast IP for publisher. Default implementation, override as needed"""
        lowerTwoDigetsServiceId = service_id % 256
        upperTwoDigetsServiceId = service_id // 256
        return "224.225." + str(upperTwoDigetsServiceId) + "." + str(lowerTwoDigetsServiceId)

    # ========== TIER 2: CONFIGURATION MANAGEMENT ==========

    def create_host_config(self, host, host_config: str, app_name):
        """Check if host config exists, if yes return, else create new.

        This is a generic implementation used by both publishers and subscribers.
        """
        if Path(host_config).is_file():
            # Config already exists, don't overwrite
            return False

        host.cmd(f'cp {self.CONFIG_TEMPLATE_PATH} {host_config}')
        host_name = host.__str__()
        unicast_ip = host.IP(intf=host.defaultIntf())

        with open(host_config, 'r') as file:
            config = json.load(file)

        config['network'] = f'-{host_name}'
        config['unicast'] = unicast_ip
        config['logging']['console'] = 'false'
        if self.vsomeip_no_logging:
            config['logging']['level'] = 'warning'
            config['logging']['file']['enable'] = 'false'
        else:
            config['logging']['level'] = 'trace'
            config['logging']['file']['enable'] = 'true'
        if self.LOGS_PATH:
            config['logging']['file']['path'] = f'{self.LOGS_PATH}/{host_name}.log'
        config['routing'] = app_name

        if self.dns_host_hex_ip is not None:
            config['dns-server-ip'] = f'{self.dns_host_hex_ip}'

        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

        # Update global condition
        VSomeIPTopologyBase.STD_CONDITION = ((config['logging']['console'] == 'true') or
                                              (config['logging']['file']['enable'] == 'true'))
        
        self.hosts.append(host_name)
        return True

    def create_publisher_config(self, host, service_id):
        """Create publisher app configuration."""
        host_name = host.__str__()
        host_config = self.get_host_config_path(host_name)
        app_name = self.get_publisher_app_name(host_name, service_id)
        app_id = self.get_publisher_app_id(host_name, service_id)

        # check if config already exists, else create.
        created = self.create_host_config(host, host_config, app_name)
        
        if service_id not in self.publishers:
            self.publishers[service_id] = {'app_name': app_name, 'app_id': app_id, 'host_name': host_name, 'clients': []}

        with open(host_config, 'r') as file:
            config = json.load(file)

        # add app if not exists
        if 'applications' not in config:
            config['applications'] = []
        if not any(app['name'] == app_name for app in config['applications']):
            config['applications'].append({
                'name': app_name,
                'id': app_id
            })

        # Add service configuration if not exists
        if 'services' not in config:
            config['services'] = []
        if not any(service['service'] == f"0x{int(service_id):04x}" for service in config['services']):
            mcast_ip = self.get_publisher_multicast_ip(service_id)
            config['services'].append({
                'service': f"0x{int(service_id):04x}",
                'instance': self.INSTANCE_ID_HEX_STR,
                'unreliable': str(self.PUBLISHER_PORT + service_id),
                'events': [
                    {"events": f"0x{int(self.EVENT_ID_1 + service_id):04x}", "is_field": "true", "update-cycle": 0},
                    {"events": f"0x{int(self.EVENT_ID_2 + service_id):04x}", "is_field": "true"}
                ],
                'eventgroups': [
                    {
                        "eventgroup": f"0x{int(self.EVENT_GROUP_ID + service_id):04x}",
                        "events": [f"0x{int(self.EVENT_ID_1 + service_id):04x}", f"0x{int(self.EVENT_ID_2 + service_id):04x}"],
                        "multicast": {
                            "address": mcast_ip,
                            "port": str(self.PUBLISHER_MCAST_PORT + service_id)
                        }
                    }
                ],
                'private-key-path': "",
                'client-certificates': [],
            })
        
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

    def create_subscriber_config(self, host, service_id, client_id):
        """Create subscriber configuration. """
        host_name = host.__str__()
        host_config = self.get_host_config_path(host_name)
        app_name = self.get_subscriber_app_name(host_name, service_id, client_id)
        app_id = self.get_subscriber_app_id(host_name, service_id, client_id)

        # check if config already exists, else create.
        created = self.create_host_config(host, host_config, app_name)
        if client_id not in self.subscribers:
            self.subscribers[client_id] = {'service_id': service_id, 'app_name': app_name, 'app_id': app_id, 'host_name': host_name}

        with open(host_config, 'r') as file:
            config = json.load(file)

        # add app if not exists
        if 'applications' not in config:
            config['applications'] = []
        if not any(app['name'] == app_name for app in config['applications']):
            config['applications'].append({
                'name': app_name,
                'id': app_id
            })

        # Add client configuration if not exists
        if 'clients' not in config:
            config['clients'] = []
        if not any((client['client-id'] == f"0x{client_id:04x}" 
                   and client['service'] == f"0x{service_id:04x}")
                   for client in config['clients']):
            config['clients'].append({
                'service': "0x{:04x}".format(service_id),
                'instance': self.INSTANCE_ID_HEX_STR,
                'unreliable': [str(self.SUBSCRIBER_PORT + client_id)],
                'client-id': f"0x{int(client_id):04x}",
                'private-key-path': "",
                'service-certificate-path': "",
            })
        
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

    def create_publisher_certificate(self, host, service_id):
        """Create publisher certificate. """
        host_name = host.__str__()
        certname = self.get_publisher_cert_name(host_name, service_id)
        certificate = self.get_cert_path(certname, 'service')
        private_key = self.get_key_path(certname, 'service')

        if not (Path(certificate).is_file() and Path(private_key).is_file()):
            host_ip = host.IP(intf=host.defaultIntf())
            port = self.PUBLISHER_PORT + service_id
            host.cmd(f"{self.SCRIPT_PATH}/gen_service_dns_and_cert.bash --service {service_id} --ip {host_ip} --port {port} --file-name {certname} --scenario {self.SCENARIO} --major-version {self.MAJOR_VERSION} --minor-version {self.MINOR_VERSION} --instance {self.INSTANCE_ID} --protocol {self.PROTOCOL}")
                     
        # update key in own host config
        host_config = self.get_host_config_path(host_name)
        with open(host_config, 'r') as file:
            config = json.load(file)

        # find service_id in config['services']
        service_str = f"0x{service_id:04x}"
        for service in config['services']:
            if service['service'] == service_str:
                service['private-key-path'] = private_key
                break

        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4) 

    def create_subscriber_certificate(self, host, service_id, client_id):
        """Create subscriber certificate."""
        host_name = host.__str__()
        certname = self.get_subscriber_cert_name(host_name, service_id, client_id)
        certificate = self.get_cert_path(certname, 'client')
        private_key = self.get_key_path(certname, 'client')
        if not (Path(certificate).is_file() and Path(private_key).is_file()):
            host_ip = host.IP(intf=host.defaultIntf())
            port = self.SUBSCRIBER_PORT + int(client_id)
            host.cmd(f"{self.SCRIPT_PATH}/gen_client_dns_and_cert.bash --client {client_id} --service {service_id} --ip {host_ip} --port {port} --file-name {certname} --scenario {self.SCENARIO} --major-version {self.MAJOR_VERSION} --instance {self.INSTANCE_ID} --protocol {self.PROTOCOL}")

        # update key in own host config
        host_config = self.get_host_config_path(host_name)
        with open(host_config, 'r') as file:
            config = json.load(file)

        # find client_id in config['clients']
        client_id_str = f"0x{int(client_id):04x}"
        service_id_str = f"0x{service_id:04x}"
        for client in config['clients']:
            if client['client-id'] == client_id_str and client['service'] == service_id_str:
                client['private-key-path'] = private_key
                break

        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

    def reference_certificates(self):
        """Reference certificates in configurations. """
        for host_name in self.hosts:
            host_config = self.get_host_config_path(host_name)
            with open(host_config, "r") as config_file:
                config = json.load(config_file)
            
            for service in config['services']:
                service_id = int(service['service'], 16)
                client_certs = service['client-certificates']
                for client_id in self.subscribers:
                    if self.subscribers[client_id]['service_id'] == service_id:
                        cert_name = self.get_subscriber_cert_name(self.subscribers[client_id]['host_name'], service_id, client_id)
                        cert_path = self.get_cert_path(cert_name, 'client')
                        if not any(cert['id'] == f"0x{client_id:04x}" for cert in client_certs):
                            client_certs.append({
                                "id": f"0x{client_id:04x}",
                                "certificate-path": cert_path
                            })
            
            for client in config['clients']:
                service_id = int(client['service'], 16)
                client_id = int(client['client-id'], 16)
                cert_name = self.get_publisher_cert_name(self.publishers[service_id]['host_name'], service_id)
                cert_path = self.get_cert_path(cert_name, 'service')
                client['service-certificate-path'] = cert_path 

            with open(host_config, "w") as config_file:
                json.dump(config, config_file, indent=4)

    def initialize_publishers_from_config(self):
        """Initialize publishers and managers from existing configs."""
        for host_name in self.hosts:
            host_config = self.get_host_config_path(host_name)
            with open(host_config, "r") as config_file:
                config = json.load(config_file)
            manager = config['routing']

            for service in config['services']:
                service_id = int(service['service'], 16)
                app_name = self.get_publisher_app_name(host_name, service_id)
                app_id = self.get_publisher_app_id(host_name, service_id)
                if app_name == manager and host_name not in self.managers:
                    print(f"Manager {manager} on host {host_name} is publisher {app_name} for service {service_id}")
                    self.managers[host_name] = {'app_name': app_name, 'app_id': app_id, 'service_id': service_id, 'class': 'publisher'}
                if service_id not in self.publishers:
                    self.publishers[service_id] = {'app_name': app_name, 'app_id': app_id, 'host_name': host_name, 'clients': []}

    def initialize_subscribers_from_config(self):
        """Initialize subscribers from existing configs. Requires publishers to be initialized first since it maintains client service relationships.""" 
        for host_name in self.hosts:
            host_config = self.get_host_config_path(host_name)
            with open(host_config, "r") as config_file:
                config = json.load(config_file)
            manager = config['routing']

            for client in config['clients']:
                service_id = int(client['service'], 16)
                client_id = int(client['client-id'], 16)
                app_name = self.get_subscriber_app_name(host_name, service_id, client_id)
                app_id = self.get_subscriber_app_id(host_name, service_id, client_id)
                if app_name == manager and host_name not in self.managers:
                    print(f"Manager {manager} on host {host_name} is subscriber {app_name} for service {service_id} client {client_id}")
                    self.managers[host_name] = {'service_id': service_id, 'app_name': app_name, 'app_id': app_id, 'client_id': client_id, 'class': 'subscriber'}
                if client_id not in self.subscribers:
                    self.subscribers[client_id] = {'service_id': service_id, 'app_name': app_name, 'app_id': app_id, 'host_name': host_name}
                if service_id not in self.publishers:
                    print(self.publishers)
                    raise ValueError(f"Config error: client {client_id} on host {host_name} references service {service_id} which has no publisher defined")
                if client_id not in self.publishers[service_id]['clients']:
                    self.publishers[service_id]['clients'].append(client_id)
            
    def initialize_missing_from_config(self):
        for host in self.net.hosts:
            host_name = host.__str__()
            if host_name == self.dns_host_name:
                continue
            if host_name not in self.hosts:
                self.hosts.append(host_name)

        self.initialize_publishers_from_config()
        self.initialize_subscribers_from_config()

        for service_id, info in self.publishers.items():
            count = len(info['clients'])
            self.service_sub_counts[service_id] = count

    # ========== TIER 2: SOME/IP COMMAND BUILDERS ==========

    def build_publisher_launch_cmd(self, host_name, service_id, app_name):
        """Build publisher launch command."""
        config_path = self.get_host_config_path(host_name)
        launch_cmd = f"env VSOMEIP_CONFIGURATION={config_path} VSOMEIP_APPLICATION_NAME={app_name} {self.PROJECT_PATH}/vsomeip/build/examples/{self.PUBLISHER_PROGRAM} --serviceid {service_id} --instanceid {self.INSTANCE_ID} --eventgroupid {self.EVENT_GROUP_ID + service_id} --eventid {self.EVENT_ID_1 + service_id} "
        return launch_cmd

    def build_subscriber_launch_cmd(self, host_name, service_id, client_id, app_name):
        """Build subscriber launch command."""
        config_path = self.get_host_config_path(host_name)
        launch_cmd = f"env VSOMEIP_CONFIGURATION={config_path} VSOMEIP_APPLICATION_NAME={app_name} {self.PROJECT_PATH}/vsomeip/build/examples/{self.SUBSCRIBER_PROGRAM} --serviceid {service_id} --instanceid {self.INSTANCE_ID} --eventgroupid {self.EVENT_GROUP_ID + service_id} --eventid {self.EVENT_ID_1 + service_id} --clientid {client_id} "
        return launch_cmd

    def start_someip_publisher_app(self, host, service_id):
        """Start SOME/IP publisher application on host."""
        host_name = host.__str__()
        app_name = self.get_publisher_app_name(host, service_id)
        launch_cmd = self.build_publisher_launch_cmd(host_name, service_id, app_name)

        if VSomeIPTopologyBase.STD_CONDITION:
            host.cmd(f"{launch_cmd}> {self.LOGS_PATH}/{host_name}.std &" if self.LOGS_PATH else f"{launch_cmd} &")
        else:
            host.cmd(f"{launch_cmd} &")

        self.num_pubs_started += 1

    def start_someip_subscriber_app(self, host, service_id, client_id):
        """Start SOME/IP subscriber application on host."""
        host_name = host.__str__()
        app_name = self.get_subscriber_app_name(host_name, service_id, client_id)
        launch_cmd = self.build_subscriber_launch_cmd(host_name, service_id, client_id, app_name)

        if VSomeIPTopologyBase.STD_CONDITION:
            host.cmd(f"{launch_cmd}> {self.LOGS_PATH}/{host_name}.std &" if self.LOGS_PATH else f"{launch_cmd} &")
        else:
            host.cmd(f"{launch_cmd} &")
            
        self.num_subs_started += 1

    # ========== TIER 3: MANAGER/INITIALIZATION ==========

    def start_captures(self):
        """Start tcpdump captures on all hosts."""
        if not self.capture_arg:
            return
        self.capture.start_dumpcap_on_hosts(self.net)

    def start_managers(self):
        """Start manager applications. """
        # check for any non 'publisher' or 'subscriber' managers and raise error if found since current implementation relies on this classification to determine startup order. 
        for host_name, info in self.managers.items():
            if info['class'] not in ['publisher', 'subscriber']:
                raise ValueError(f"Manager {info['app_name']} on host {host_name} has invalid class {info['class']}. Must be 'publisher' or 'subscriber'.")
        # first only subscriber managers
        sub_managers = {host_name: info for host_name, info in self.managers.items() if info['class'] == 'subscriber'}
        pub_managers = {host_name: info for host_name, info in self.managers.items() if info['class'] == 'publisher'}
        total_managers = len(self.managers)
        with tqdm(total=total_managers, desc="Starting managers", unit="manager") as pbar:
            for host_name, manager_info in sub_managers.items():
                host = self.net[host_name]
                self.start_someip_subscriber_app(host, manager_info['service_id'], manager_info['client_id'])
                pbar.update(1)
            for host_name, manager_info in pub_managers.items():
                host = self.net[host_name]
                self.start_someip_publisher_app(host, manager_info['service_id'])
                pbar.update(1)

    def start_publishers(self):
        """Start publisher applications. """
        with tqdm(total=len(self.publishers), desc="Starting publishers", unit="publisher") as pbar:
            for service_id, info in self.publishers.items():
                host = self.net[info['host_name']]
                manager = self.managers[info['host_name']]
                if manager['class'] == 'publisher' and manager['service_id'] == service_id:
                    pbar.update(1)
                    continue
                self.start_someip_publisher_app(host, service_id)
                pbar.update(1)

    def start_subscribers(self):
        """Start subscriber applications."""
        with tqdm(total=len(self.subscribers), desc="Starting subscribers", unit="subscriber") as pbar:
            for client_id, info in self.subscribers.items():
                host = self.net[info['host_name']]
                manager = self.managers[info['host_name']]
                if manager['class'] == 'subscriber' and manager['client_id'] == client_id:
                    pbar.update(1)
                    continue
                self.start_someip_subscriber_app(host, info['service_id'], client_id)
                pbar.update(1)

    def wait_for_initialized_files(self, poll_interval=0.001):
        """Wait for all started apps to be initialized by polling for marker files."""
        manager_initialized_path = Path(f"{self.PROJECT_PATH}/")
        total = self.num_pubs_started + self.num_subs_started
        with tqdm(total=total, desc="Waiting for initialization", unit="app") as pbar:
            last_count = 0
            while True:
                num_pubs_initialized = len(list(manager_initialized_path.glob("publisher-initialized-*")))
                num_subs_initialized = len(list(manager_initialized_path.glob("subscriber-initialized-*")))
                current_count = num_pubs_initialized + num_subs_initialized
                pbar.update(current_count - last_count)
                pbar.set_postfix(pubs=f"{num_pubs_initialized}/{self.num_pubs_started}", subs=f"{num_subs_initialized}/{self.num_subs_started}")
                last_count = current_count
                if current_count == total:
                    break
                time.sleep(poll_interval)

    def get_statistics_result_path(self):
        return f"{self.SCENARIO_PATH}/statistic-results/{self.evaluation_option}-series/run-{self.current_run}"

    def start_statistics_writer(self):
        out_path = self.get_statistics_result_path()
        Path(out_path).mkdir(parents=True, exist_ok=True)
        services = "[" + ",".join(str(service_id) for service_id in self.service_sub_counts.keys()) + "]"
        member_counts = "[" + ",".join(str(count) for count in self.service_sub_counts.values()) + "]"
        result_filename = f"{self.evaluation_option}"
        print(f"services: {services}")
        print(f"member_counts: {member_counts}")
        return subprocess.Popen([f"{self.PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", services, member_counts, out_path, result_filename ])

    # ========== TIER 3: EVALUATION SUPPORT ==========

    def prepare_network(self, topo: Topo, dns_host_name: str):
        print("Building mininet network ... ")
        self.dns_host_name = dns_host_name
        setLogLevel('critical')
        self.net = Mininet(topo=topo, controller=None, link=TCLink)
        self.net.start()
        self.make_switches_traditional()
        self.add_default_route_to_hosts()
        self.dns_host_hex_ip = self.get_dns_host_ip_in_hex()
        print("Done.")

    def clean_before_evaluation(self):
        print("Cleaning up mininet interfaces ... ")
        subprocess.run(['mn', '-c'])
        self.cleanup()
        if self.clean_start:
            print("Removing configs and certificates ... ")
            self.delete_configs_and_certs()
        print("Done.")

    @abstractmethod
    def create_publishers(self):
        """Abstract method to create publishers. To be implemented by subclass based on specific scenario needs."""
        pass

    @abstractmethod
    def create_subscribers(self):
        """Abstract method to create subscribers. To be implemented by subclass based on specific scenario needs."""
        pass

    def get_out_path_for_run(self, run: int, return_code: int):
        """Get output path for logs of a specific evaluation run."""
        time_stamp = datetime.fromtimestamp(self.eval_start).strftime("%Y%m%d-%H%M%S")
        out_suffix = f"{self.evaluation_option}-series/{time_stamp}_p{len(self.publishers)}_s{len(self.subscribers)}/run-{run}-"
        if return_code == 0:
            out_suffix += "success"
        else:
            out_suffix += "failure"
        return out_suffix

    def copy_logs_to_scenario_folder(self, run: int, return_code: int, move_logs: bool = True):
        """Copy or move logs to scenario folder."""
        out_path = self.LOGS_PATH + "/" + self.get_out_path_for_run(run, return_code)
        if return_code == 0 and self.copy_logs_on_failure:
            # abort because we only want logs for failed runs, but this run was successful
            return

        subprocess.run(f"rm -rf {out_path}*", shell=True, check=True)

        os.makedirs(out_path, exist_ok=True)

        if move_logs:
            subprocess.run(f"mv {self.LOGS_PATH}/*.log {out_path}/", shell=True, check=True)
        else:
            subprocess.run(f"cp {self.LOGS_PATH}/*.log {out_path}/", shell=True, check=True)

        # own everything below log/
        subprocess.run(f"chown -R vm-user:vm-user {self.LOGS_PATH}", shell=True, check=True)
    
    # ========== TIER 4: EVALUATION EXECUTION ==========
    def setup_evaluation(self, args, topo: Topo, dns_host_name: str = None):
        """Set up the evaluation environment including scenario args, topology and building vsomeip."""
        self.handle_common_args(args)
        self.clean_before_evaluation()
        self.prepare_network(topo, dns_host_name)
        self.build_vsomeip()
        # create host configs and certificates
        if self.clean_start:
            print("Creating host configs and certificates ... (this may take a while)")
            self.create_subscribers()
            self.create_publishers()
            self.reference_certificates()
            print("Done.")
        else:
            print("Reusing existing host configs and certificates ... ")
        self.initialize_missing_from_config()

    def launch_components(self):
        """Launch SOME/IP apps, DNS server and tcpdump captures (if enabled) for the evaluation run."""
        if self.capture_arg:
            print("Starting tcpdump captures ... ")
            self.start_captures()
            print("Done.")
            time.sleep(0.1)

        # Start statistics writer
        print("Starting statistics-writer ...")
        statistics_writer_process = self.start_statistics_writer()
        print("Done.")
        time.sleep(0.1)

        # Start DNS server if needed
        if self.WITH_DNSSEC in self.add_compile_definitions:
            print("Starting DNS server ... ")
            self.start_dns_server()
            print("Done.")
            time.sleep(0.1)

        start_apps_begin = time.time()

        # Start SOME/IP apps
        managers_start = time.time()
        self.start_managers()
        self.wait_for_initialized_files()
        managers_end = time.time()
        # time.sleep(0.01)

        subscribers_start = time.time()
        self.start_subscribers()
        self.wait_for_initialized_files()
        subscribers_end = time.time()

        publishers_start = time.time()
        self.start_publishers()
        self.wait_for_initialized_files()
        publishers_end = time.time()

        start_apps_end = time.time()

        print(f"Total initialization time: {start_apps_end-start_apps_begin}s (managers: {managers_end-managers_start}s, publishers: {publishers_end-publishers_start}s, subscribers: {subscribers_end-subscribers_start}s)")
        return statistics_writer_process
    
    def stop_run(self, return_code):
        """Stop the current evaluation run (e.g., if it is taking too long)."""
        print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
        for host in self.net.hosts:
            self.stop_subscriber_app(host)
            self.stop_publisher_app(host)
        print ("Done.")

        if self.WITH_DNSSEC in self.add_compile_definitions:
            self.stop_dns_server()

        if self.capture_arg:
            out_path = self.CAPTURE_PATH + "/" + self.get_out_path_for_run(self.current_run, return_code)
            self.capture.finalize_captures(out_path)

        time.sleep(1)

    def shutdown_evaluation(self):
        print("Stopping mininet network")
        self.net.stop()
        subprocess.run(f"chown -R vm-user:vm-user {self.STATISTICS_PATH}", shell=True, check=True)
        self.cleanup()
        print("Done.")

    def process_evaluation_run(self, return_code):
        """Process evaluation run results (e.g., copy logs). Hook for subclass customization."""
        drops = self.check_host_queue_overflows()
        drops.update(self.check_switch_queue_overflows())
        if drops:
            print(f"WARNING: Detected queue overflows on {', '.join(drops.keys())} during evaluation run {self.current_run}/{self.total_evaluation_runs} for option {self.evaluation_option}. This may indicate that the network was a bottleneck and results may be affected.")
        else:
            print(f"No queue overflows detected during evaluation run {self.current_run}/{self.total_evaluation_runs} for option {self.evaluation_option}.")
        if self.copy_logs or self.copy_logs_on_failure:
            self.copy_logs_to_scenario_folder(self.current_run, return_code)

    def run_evaluation(self):
        """Run evaluation with given parameters."""
        entire_evaluation_start = time.time()
        self.eval_start = entire_evaluation_start
        self.current_run = 1
        reruns = 0

        with tqdm(total=self.total_evaluation_runs, desc=f"Evaluation runs for option {self.evaluation_option}", unit="run") as pbar:
            while self.current_run <= self.total_evaluation_runs:
                self.reset_state()
                evaluation_run_start = time.time()
                print(f"Starting {self.current_run}/{self.total_evaluation_runs} evaluation run {self.evaluation_option} ... ")

                statistics_writer_process = self.launch_components()

                # Wait for statistics writer
                print("Waiting until all statistics are contributed ... ")
                try:
                    return_code = statistics_writer_process.wait(timeout=5)
                except TimeoutExpired:
                    print("statistics writer did not finish in time. Killing it ...")
                    statistics_writer_process.kill()
                    return_code = 1

                if return_code == 0:
                    print("Done.")
                    evaluation_run_end = time.time()
                    print(f"RUN ({self.evaluation_option}): {self.current_run}/{self.total_evaluation_runs} ({evaluation_run_end-evaluation_run_start}s)")
                    reruns = 0
                else:
                    # print(f"statistics writer failed with return code {return_code}")
                    if reruns < self.max_retries:
                        reruns += 1
                        print(f"{self.current_run}/{self.total_evaluation_runs} evaluation run {self.evaluation_option} failed with return code {return_code} and will be repeated")
                    else:
                        if self.max_retries > 0:
                            print(f"{self.current_run}/{self.total_evaluation_runs} evaluation run {self.evaluation_option} failed with return code {return_code} -- maximum retries ({self.max_retries}) reached for run {self.current_run}/{self.total_evaluation_runs}")
                        reruns = 0

                time.sleep(1)

                self.stop_run(return_code)

                self.process_evaluation_run(return_code)
                
                self.cleanup()
                
                if reruns == 0:
                    self.current_run += 1
                    pbar.update(1)

        entire_evaluation_end = time.time()
        print(f"TOTAL TIME FOR OPTION {self.evaluation_option} in {self.total_evaluation_runs} RUN/S: {entire_evaluation_end - entire_evaluation_start}s")

        self.shutdown_evaluation()
