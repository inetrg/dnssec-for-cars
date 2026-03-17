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
from subprocess import TimeoutExpired
from itertools import combinations

from mininet.net import Mininet
from mininet.util import dumpNodeConnections, dumpNetConnections


def _get_parser_with_common_args():
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
    parser.add_argument('--repeat-on-failure', dest='repeat_on_failure', action='store_true', help='Repeats a run in case of failure.')
    parser.add_argument('--clean-start', dest='clean_start', action='store_true', help='Removes certificates and host configs causing them to be recreated')
    parser.add_argument('--copy-logs', dest='copy_logs', action='store_true', default=False, help='Copy logs to scenario folder for every evaluation run')
    return parser

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

    # ========== TIER 1 & 2: NETWORK UTILITIES (SHARED) ==========

    def dump_switch_information(self, net: Mininet, switch: str):
        """Dump switch information using ovs-ofctl."""
        print("Dumping switch information w/ ovs-ofctl")
        print(net[switch].cmd('ovs-ofctl show {}'.format(switch)))

    def dump_switch_flows(self, net: Mininet, switch: str):
        """Dump flow rules on a switch."""
        print("Dumping flow rules on {}".format(switch))
        print(net[switch].cmd('ovs-ofctl dump-flows {}'.format(switch)))

    def dump_infos(self, net: Mininet):
        """Dump host and network connection information."""
        print("Dumping host connections")
        dumpNodeConnections(net.hosts)
        print("Dumping switch connections")
        dumpNodeConnections(net.switches)
        print("Dumping net connections")
        dumpNetConnections(net)

    def simple_tests(self, net: Mininet):
        """Test network connectivity and bandwidth."""
        print("Testing network connectivity")
        net.pingAll()
        print("Testing bandwidth between hosts")
        unique_host_tuples_set = set(combinations(net.hosts, 2))
        for host_tuple in unique_host_tuples_set:
            net.iperf(hosts=host_tuple, l4Type='TCP')
            net.iperf(hosts=host_tuple, l4Type='UDP')

    def add_default_route_to_hosts(self, net: Mininet):
        """Add default route for each host."""
        for host in net.hosts:
            host_name = host.__str__()
            host.cmd(f'route add default gw 10.0.0.0 {host_name}-eth0')

    def scenario_dirs(self, scenario_folder):
        """Set up scenario-specific directories."""
        self.SCENARIO = scenario_folder
        self.SCENARIO_PATH = f"{self.PROJECT_PATH}/{scenario_folder}"
        self.CONFIG_PATH = f"{self.SCENARIO_PATH}/vsomeip-configs"
        self.CERT_PATH = f"{self.SCENARIO_PATH}/certificates"
        self.ZONE_PATH = f"{self.SCENARIO_PATH}/zones"
        # self.SCRIPT_PATH = f"{self.SCENARIO_PATH}/scripts"
        self.LOGS_PATH = f"{self.SCENARIO_PATH}/logs"

        Path(self.CONFIG_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.CERT_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.ZONE_PATH).mkdir(parents=True, exist_ok=True)
        Path(self.LOGS_PATH).mkdir(parents=True, exist_ok=True)

    def make_switches_traditional(self, net):
        """Configure switches for traditional operation."""
        for switch in net.switches:
            switch_name = switch.__str__()
            net[switch_name].cmd('ovs-ofctl add-flow {} action=normal'.format(switch_name))

    def set_copy_logs(self, copy_logs):
        """Set whether to copy logs to scenario folder after each evaluation run."""
        self.copy_logs = copy_logs

    # ========== TIER 2: INFRASTRUCTURE MANAGEMENT ==========

    def start_dns_server(self, dns_host):
        """Start DNS server (NSD) on the given host."""
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's|zonefile: \"/home/vm-user/workspace/mininet-vsomeip-evaluation/zones/service.zone\"|zonefile: \"{self.ZONE_PATH}/service.zone\"|' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's|zonefile: \"/home/vm-user/workspace/mininet-vsomeip-evaluation/zones/client.zone\"|zonefile: \"{self.ZONE_PATH}/client.zone\"|' {self.NSD_CONF_PATH}")
        dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {self.ZONE_PATH}/service.zone")
        dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {self.ZONE_PATH}/client.zone")
        dns_host.cmd('nsd-control-setup')
        dns_host.cmd(f'nsd -c {self.NSD_CONF_PATH}')

    def stop_dns_server(self, dns_host):
        """Stop DNS server (NSD)."""
        dns_host.cmd('nsd-control stop')
        dns_host.cmd('pkill nsd')

    def _get_dns_host_ip_in_hex(self, net: Mininet, dns_host=None):
        if self.dns_host_hex_ip is not None:
            return self.dns_host_hex_ip
        dns_host_ip_in_hex = None
        if dns_host is not None and dns_host != "":
            dns_host_obj = net[dns_host]
            dns_host_ip = dns_host_obj.IP(intf=dns_host_obj.defaultIntf())
            dns_host_ip_in_hex = self._convert_ip_to_hex(dns_host_ip)
        return dns_host_ip_in_hex

    def reset_zone_files(self):
        """Reset zone files to default state."""
        subprocess.run(["su", "-", "vm-user", "-c", f"{self.SCENARIO_PATH}/reset-zone-file.bash"])

    def build_vsomeip(self, add_compile_definitions):
        """Build vsomeip project."""
        # set compile opts
        subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {self.PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)

        subprocess.run(f'su - vm-user -c "cmake -B {self.PROJECT_PATH}/vsomeip/build -S {self.PROJECT_PATH}/vsomeip"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target all -- -j$(nproc)"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target examples -- -j$(nproc)"', shell=True)
        subprocess.run(f'su - vm-user -c "$(which cmake) --build {self.PROJECT_PATH}/vsomeip/build --config Release --target statistics-writer -- -j$(nproc)"', shell=True)

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

    def get_publisher_app_name(self, host, service_id):
        """Get publisher application name."""
        host_name = host.__str__()
        return f"{host_name}-{service_id}"

    def get_subscriber_app_name(self, host, service_id, client_id):
        """Get subscriber application name."""
        host_name = host.__str__()
        return f"{host_name}-{service_id}-{client_id}"

    def get_publisher_app_id(self, host, service_id):
        """Get publisher app id."""
        return f"0x{int(service_id):04x}"

    def get_subscriber_app_id(self, host, service_id, client_id):
        """Get subscriber app id."""
        return f"0x{int(client_id):04x}"

    def get_publisher_cert_name(self, host, service_id):
        """Get publisher certificate name (without extension)."""
        host_name = host.__str__()
        return f'{host_name}_{service_id}'

    def get_subscriber_cert_name(self, host, service_id, client_id):
        """Get subscriber certificate name (without extension)."""
        host_name = host.__str__()
        return f'{host_name}_{client_id}'

    def _get_cert_path(self, cert_name, cert_type):
        """Get full certificate path. cert_type should be 'service' or 'client'."""
        return f'{self.CERT_PATH}/{cert_name}.{cert_type}.cert.pem'

    def _get_key_path(self, cert_name, cert_type):
        """Get full private key path. cert_type should be 'service' or 'client'."""
        return f'{self.CERT_PATH}/{cert_name}.{cert_type}.key.pem'

    def _convert_ip_to_hex(self, ip_address: str) -> str:
        """Convert dotted decimal IP address to hex format (0xAABBCCDD)."""
        ip_bytes = ip_address.split(".")
        ip_bytes_in_hex = ["{:02x}".format(int(x)) for x in ip_bytes]
        return f"0x{''.join(ip_bytes_in_hex)}"

    def _reset_state(self):
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
        config['logging']['level'] = 'trace'
        config['logging']['console'] = 'false'
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
        host_config = self.get_host_config_path(host.__str__())
        app_name = self.get_publisher_app_name(host, service_id)
        app_id = self.get_publisher_app_id(host, service_id)

        # check if config already exists, else create.
        created = self.create_host_config(host, host_config, app_name)
        host_name = host.__str__()
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
        app_name = self.get_subscriber_app_name(host, service_id, client_id)
        app_id = self.get_subscriber_app_id(host, service_id, client_id)

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
        certname = self.get_publisher_cert_name(host, service_id)
        certificate = self._get_cert_path(certname, 'service')
        private_key = self._get_key_path(certname, 'service')

        if not (Path(certificate).is_file() and Path(private_key).is_file()):
            host_ip = host.IP(intf=host.defaultIntf())
            port = self.PUBLISHER_PORT + service_id
            host.cmd(f"{self.SCRIPT_PATH}/gen_service_dns_and_cert.bash --service {service_id} --ip {host_ip} --port {port} --file-name {certname} --scenario {self.SCENARIO} --major-version {self.MAJOR_VERSION} --minor-version {self.MINOR_VERSION} --instance {self.INSTANCE_ID} --protocol {self.PROTOCOL}")
                     
        # update key in own host config
        host_config = self.get_host_config_path(host.__str__())
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
        certname = self.get_subscriber_cert_name(host, service_id, client_id)
        certificate = self._get_cert_path(certname, 'client')
        private_key = self._get_key_path(certname, 'client')
        if not (Path(certificate).is_file() and Path(private_key).is_file()):
            host_ip = host.IP(intf=host.defaultIntf())
            port = self.SUBSCRIBER_PORT + int(client_id)
            host.cmd(f"{self.SCRIPT_PATH}/gen_client_dns_and_cert.bash --client {client_id} --service {service_id} --ip {host_ip} --port {port} --file-name {certname} --scenario {self.SCENARIO} --major-version {self.MAJOR_VERSION} --instance {self.INSTANCE_ID} --protocol {self.PROTOCOL}")

        # update key in own host config
        host_config = self.get_host_config_path(host.__str__())
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
                        cert_path = self._get_cert_path(cert_name, 'client')
                        if not any(cert['id'] == f"0x{client_id:04x}" for cert in client_certs):
                            client_certs.append({
                                "id": f"0x{client_id:04x}",
                                "certificate-path": cert_path
                            })
            
            for client in config['clients']:
                service_id = int(client['service'], 16)
                client_id = int(client['client-id'], 16)
                cert_name = self.get_publisher_cert_name(self.publishers[service_id]['host_name'], service_id)
                cert_path = self._get_cert_path(cert_name, 'service')
                client['service-certificate-path'] = cert_path 

            with open(host_config, "w") as config_file:
                json.dump(config, config_file, indent=4)

    def _initialize_publishers_from_config(self, net):
        """Initialize publishers and managers from existing configs."""
        for host in net.hosts:
            host_name = host.__str__()
            if host_name == self.dns_host_name:
                continue
            host_config = self.get_host_config_path(host_name)
            with open(host_config, "r") as config_file:
                config = json.load(config_file)
            manager = config['routing']

            for service in config['services']:
                service_id = int(service['service'], 16)
                app_name = self.get_publisher_app_name(host, service_id)
                app_id = self.get_publisher_app_id(host, service_id)
                if app_name == manager and host_name not in self.managers:
                    print(f"Manager {manager} on host {host_name} is publisher {app_name} for service {service_id}")
                    self.managers[host_name] = {'app_name': app_name, 'app_id': app_id, 'service_id': service_id, 'class': 'publisher'}
                if service_id not in self.publishers:
                    self.publishers[service_id] = {'app_name': app_name, 'app_id': app_id, 'host_name': host_name, 'clients': []}

    def _initialize_subscribers_from_config(self, net):
        """Initialize subscribers from existing configs. Requires publishers to be initialized first since it maintains client service relationships.""" 
        for host in net.hosts:
            host_name = host.__str__()
            if host_name == self.dns_host_name:
                continue
            host_config = self.get_host_config_path(host_name)
            with open(host_config, "r") as config_file:
                config = json.load(config_file)
            manager = config['routing']

            for client in config['clients']:
                service_id = int(client['service'], 16)
                client_id = int(client['client-id'], 16)
                app_name = self.get_subscriber_app_name(host, service_id, client_id)
                app_id = self.get_subscriber_app_id(host, service_id, client_id)
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
            
    def initialize_missing_from_config(self, net):
        for host in net.hosts:
            host_name = host.__str__()
            if host_name == self.dns_host_name:
                continue
            if host_name not in self.hosts:
                self.hosts.append(host_name)

        self._initialize_publishers_from_config(net)
        self._initialize_subscribers_from_config(net)

        for service_id, info in self.publishers.items():
            count = len(info['clients'])
            self.service_sub_counts[service_id] = count

    # ========== TIER 2: SOME/IP COMMAND BUILDERS ==========

    def _build_publisher_launch_cmd(self, host_name, service_id, app_name):
        """Build publisher launch command."""
        config_path = self.get_host_config_path(host_name)
        launch_cmd = f"env VSOMEIP_CONFIGURATION={config_path} VSOMEIP_APPLICATION_NAME={app_name} {self.PROJECT_PATH}/vsomeip/build/examples/{self.PUBLISHER_PROGRAM} --serviceid {service_id} --instanceid {self.INSTANCE_ID} --eventgroupid {self.EVENT_GROUP_ID + service_id} --eventid {self.EVENT_ID_1 + service_id} "
        return launch_cmd

    def _build_subscriber_launch_cmd(self, host_name, service_id, client_id, app_name):
        """Build subscriber launch command."""
        config_path = self.get_host_config_path(host_name)
        launch_cmd = f"env VSOMEIP_CONFIGURATION={config_path} VSOMEIP_APPLICATION_NAME={app_name} {self.PROJECT_PATH}/vsomeip/build/examples/{self.SUBSCRIBER_PROGRAM} --serviceid {service_id} --instanceid {self.INSTANCE_ID} --eventgroupid {self.EVENT_GROUP_ID + service_id} --eventid {self.EVENT_ID_1 + service_id} --clientid {client_id} "
        return launch_cmd

    def start_someip_publisher_app(self, host, service_id):
        """Start SOME/IP publisher application on host."""
        host_name = host.__str__()
        app_name = self.get_publisher_app_name(host, service_id)
        launch_cmd = self._build_publisher_launch_cmd(host_name, service_id, app_name)

        if VSomeIPTopologyBase.STD_CONDITION:
            host.cmd(f"{launch_cmd}> {self.LOGS_PATH}/{host_name}.std &" if self.LOGS_PATH else f"{launch_cmd} &")
        else:
            host.cmd(f"{launch_cmd} &")

        self.num_pubs_started += 1

    def start_someip_subscriber_app(self, host, service_id, client_id):
        """Start SOME/IP subscriber application on host."""
        host_name = host.__str__()
        app_name = self.get_subscriber_app_name(host, service_id, client_id)
        launch_cmd = self._build_subscriber_launch_cmd(host_name, service_id, client_id, app_name)

        if VSomeIPTopologyBase.STD_CONDITION:
            host.cmd(f"{launch_cmd}> {self.LOGS_PATH}/{host_name}.std &" if self.LOGS_PATH else f"{launch_cmd} &")
        else:
            host.cmd(f"{launch_cmd} &")
            
        self.num_subs_started += 1

    # ========== TIER 3: MANAGER/INITIALIZATION ==========

    def start_managers(self, net: Mininet):
        """Start manager applications. """
        for host_name, manager_info in self.managers.items():
            host = net[host_name]
            if manager_info['class'] == 'publisher':
                self.start_someip_publisher_app(host, manager_info['service_id'])
                print(f"Started SOME/IP manager app for {manager_info['app_name']} on host {host_name} for service {manager_info['service_id']}")
            elif manager_info['class'] == 'subscriber':
                self.start_someip_subscriber_app(host, manager_info['service_id'], manager_info['client_id'])
                print(f"Started SOME/IP manager app for {manager_info['app_name']} on host {host_name} for service {manager_info['service_id']} client {manager_info['client_id']}")
            else:
                raise ValueError(f"Unknown manager class {manager_info['class']} for host {host_name} should be publisher/subscriber")

    def start_publishers(self, net: Mininet):
        """Start publisher applications. """
        for service_id, info in self.publishers.items():
            host = net[info['host_name']]
            manager = self.managers[info['host_name']]
            if manager['class'] == 'publisher' and manager['service_id'] == service_id:
                print(f"Skip publisher {service_id} on host {info['host_name']}, already launched as manager")
                continue
            self.start_someip_publisher_app(host, service_id)

    def start_subscribers(self, net: Mininet):
        """Start subscriber applications."""
        for client_id, info in self.subscribers.items():
            host = net[info['host_name']]
            manager = self.managers[info['host_name']]
            if manager['class'] == 'subscriber' and manager['client_id'] == client_id:
                print(f"Skip subscriber {client_id} for service {info['service_id']} on host {info['host_name']}, already launched as manager")
                continue
            self.start_someip_subscriber_app(host, info['service_id'], client_id)

    def _wait_for_initialized_files(self, poll_interval=0.001):
        """Wait for all started apps to be initialized by polling for marker files."""
        manager_initialized_path = Path(f"{self.PROJECT_PATH}/")
        print(f"Waiting until all launched SOME/IP apps ({self.num_pubs_started} publishers and {self.num_subs_started} subscribers) are initialized ...")
        while True:
            num_pubs_initialized = len(list(manager_initialized_path.glob("publisher-initialized-*")))
            num_subs_initialized = len(list(manager_initialized_path.glob("subscriber-initialized-*")))
            if (num_pubs_initialized == self.num_pubs_started) and (num_subs_initialized == self.num_subs_started):
                break
            print (f"Still waiting for initialization: {num_pubs_initialized}/{self.num_pubs_started} publishers and {num_subs_initialized}/{self.num_subs_started} subscribers")
            time.sleep(poll_interval)

    def start_statistics_writer(self, evaluation_option: str):
        out_path = f"{self.SCENARIO_PATH}/statistic-results/{evaluation_option}-series"
        Path(out_path).mkdir(parents=True, exist_ok=True)
        services = "[" + ",".join(str(service_id) for service_id in self.service_sub_counts.keys()) + "]"
        member_counts = "[" + ",".join(str(count) for count in self.service_sub_counts.values()) + "]"
        print(f"services: {services}")
        print(f"member_counts: {member_counts}")
        return subprocess.Popen([f"{self.PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", services, member_counts, out_path, evaluation_option])

    # ========== TIER 3: EVALUATION LOOP ==========

    def _copy_logs_to_scenario_folder(self, evaluation_option: str, run: int, return_code: int, move_logs: bool = True):
        """Copy or move logs to scenario folder."""
        time_stamp = datetime.fromtimestamp(self.eval_start).strftime("%Y%m%d-%H%M%S")
        out_path = f"{self.LOGS_PATH}/{evaluation_option}-series/{time_stamp}/run-{run}-"
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

    def _process_evaluation_run(self, evaluation_option, run, return_code):
        """Process evaluation run results (e.g., copy logs). Hook for subclass customization."""
        pass

    def start_evaluation(self, total_evaluation_runs: int, evaluation_option: str, repeat_failure: bool,
                        add_compile_definitions: str, net: Mininet):
        """Run evaluation with given parameters."""
        self.initialize_missing_from_config(net)
        entire_evaluation_start = time.time()
        current_run = 1

        while current_run <= total_evaluation_runs:
            evaluation_run_start = time.time()
            print(f"Starting {current_run}/{total_evaluation_runs} evaluation run {evaluation_option} ... ")

            # Start statistics writer
            print("Starting statistics-writer ...")
            statistics_writer_process = self.start_statistics_writer(evaluation_option)
            time.sleep(0.1)
            print("Done.")

            # Start DNS server if needed
            if self.WITH_DNSSEC in add_compile_definitions:
                print("Starting DNS server ... ")
                self.start_dns_server(net[self.dns_host_name])
                time.sleep(0.1)
                print("Done.")

            start_apps_begin = time.time()

            # Start SOME/IP apps
            print("Starting SOME/IP manager apps per host ... ")
            managers_start = time.time()
            self.start_managers(net)
            self._wait_for_initialized_files()
            managers_end = time.time()
            print("Done.")
            time.sleep(0.01)

            print("Starting SOME/IP subscribers ... ")
            subscribers_start = time.time()
            self.start_subscribers(net)
            self._wait_for_initialized_files()
            subscribers_end = time.time()
            print("Done.")

            print("Starting SOME/IP publishers ... ")
            publishers_start = time.time()
            self.start_publishers(net)
            publishers_end = time.time()
            print("Done.")

            self._wait_for_initialized_files()
            start_apps_end = time.time()

            print(f"Total initialization time: {start_apps_end-start_apps_begin}s (managers: {managers_end-managers_start}s, publishers: {publishers_end-publishers_start}s, subscribers: {subscribers_end-subscribers_start}s)")

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
                print(f"RUN ({evaluation_option}): {current_run}/{total_evaluation_runs} ({evaluation_run_end-evaluation_run_start}s)")
                current_run += 1
            else:
                print(f"statistics writer failed with return code {return_code}")
                print(f"{current_run}/{total_evaluation_runs} evaluation run {evaluation_option} failed and will be repeated")
                if not repeat_failure:
                    current_run += 1

            # Stop apps
            print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
            for host in net.hosts:
                self.stop_subscriber_app(host)
                self.stop_publisher_app(host)

            if self.WITH_DNSSEC in add_compile_definitions:
                self.stop_dns_server(net[self.dns_host_name])

            time.sleep(1)

            # Hook for subclass-specific processing
            
            if self.copy_logs:
                self._copy_logs_to_scenario_folder(evaluation_option, current_run, return_code)
            self._process_evaluation_run(evaluation_option, current_run - 1, return_code)

            self.cleanup()
            print("Done.")

        entire_evaluation_end = time.time()
        print(f"TOTAL TIME FOR OPTION {evaluation_option} in {total_evaluation_runs} RUN/S: {entire_evaluation_end - entire_evaluation_start}s")
