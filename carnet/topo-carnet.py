#!/usr/bin/python

"""Carnet Topology

implements an in-vehicle network topology with all services
"""

import argparse
import subprocess
import json
import time
from itertools import combinations
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections
from mininet.util import dumpNetConnections
from pathlib import Path

PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"
SCENARIO_PATH = f"{PROJECT_PATH}/carnet"

DNSNODENAME = 'dns'

# dummy to be replaced by car configuration file
INSTANCE_ID = "1"
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PROTOCOL = "UDP"

STD_CONDITION = False
# compile definitions
WITH_SERVICE_AUTHENTICATION = 'WITH_SERVICE_AUTHENTICATION'
WITH_CLIENT_AUTHENTICATION = 'WITH_CLIENT_AUTHENTICATION'
NO_SOMEIP_SD = 'NO_SOMEIP_SD'
WITH_DNSSEC = 'WITH_DNSSEC'
WITH_DANE = 'WITH_DANE'
WITH_ENCRYPTION = 'WITH_ENCRYPTION'
compile_definitions = {'A':'',
                        'B':f'{NO_SOMEIP_SD} {WITH_DNSSEC}',
                        'C':f'{WITH_SERVICE_AUTHENTICATION}',
                        'D':f'{NO_SOMEIP_SD} {WITH_SERVICE_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
                        'E':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION}',
                        'F':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_ENCRYPTION}',
                        'G':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
                        'H':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE} {WITH_ENCRYPTION}'}

class car_topology (Topo):
    "Car Topology"
 
    def build (self: Topo):
        "Create car topology."

        # add switches
        sRL = self.addSwitch('s1')
        sFL = self.addSwitch('s2')
        sRR = self.addSwitch('s3')
        sFR = self.addSwitch('s4')
        sC = self.addSwitch('s5')

        # add hosts
        zcRl = self.addHost('zcRL')
        zcFl = self.addHost('zcFL')
        zcRr = self.addHost('zcRR')
        zcFr = self.addHost('zcFR')
        lRL = self.addHost('lRL')
        lFL = self.addHost('lFL')
        lRR = self.addHost('lRR')
        lFR = self.addHost('lFR')
        cR = self.addHost('cR')
        cF = self.addHost('cF')
        adas = self.addHost('adas')
        inf = self.addHost('inf')
        con = self.addHost('con')

        # add DNS node
        dns = self.addHost(DNSNODENAME)

        # add links
        self.addLink(zcRl, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(zcFl, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(zcRr, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(zcFr, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(lRL, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(lFL, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(lRR, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(lFR, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(cR, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(cF, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(adas, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(inf, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(con, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sC, dns, bw=1000, delay='0ms', loss=0, max_queue_size=99999)

def make_switch_traditional(net: Mininet, switch: str):
    net[switch].cmd('ovs-ofctl add-flow {} action=normal'.format(switch))

def add_default_route(host):
    host_name = host.__str__()
    host.cmd(f'route add default gw 10.0.0.0 {host_name}-eth0')

def dump_switch_information(net: Mininet, switch: str):
    print( "Dumping switch information w/ ovs-ofctl" )
    print(net[switch].cmd('ovs-ofctl show {}'.format(switch)))

def dump_switch_flows(net: Mininet, switch: str):
    print( "Dumping flow rules on {}".format(switch) )
    print(net[switch].cmd('ovs-ofctl dump-flows {}'.format(switch)))

def dump_infos(net: Mininet):
    print( "Dumping host connections" )
    dumpNodeConnections(net.hosts)
    print( "Dumping switch connections" )
    dumpNodeConnections(net.switches)
    print( "Dumping net connections" )
    dumpNetConnections(net)
   
def test_connectivity(net: Mininet, debug=False):
    lossPct = net.pingAll()
    if lossPct == 0:
        print("All hosts are reachable")
    else:
        print("Reachability test failed with loss percentage of {}".format(lossPct))
        # throw exception here
        raise Exception("Hosts are not reachable")

def test_bandwidth(net: Mininet):
    unique_host_tuples_set = set(combinations(net.hosts, 2))
    for host_tuple in unique_host_tuples_set:
        net.iperf(hosts=host_tuple,l4Type='TCP')
    
def build_vsomeip():
    # subprocess.run(["su", "-", "vm-user", "-c", f"{PROJECT_PATH}/build_vsomeip.bash"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f'su - vm-user -c "cmake -B {PROJECT_PATH}/vsomeip/build -S {PROJECT_PATH}/vsomeip"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target all -- -j$(nproc)"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target examples -- -j$(nproc)"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target statistics-writer -- -j$(nproc)"', shell=True)

def reset_zone_files():
    subprocess.run(["su", "-", "vm-user", "-c", f"{SCENARIO_PATH}/reset-zone-files.bash"])

def start_dns_server(dns_host):
    dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
    dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {SCENARIO_PATH}/nsd/nsd.conf")
    dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/service.zone")
    dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/client.zone")
    dns_host.cmd('nsd-control-setup')
    dns_host.cmd(f'nsd -c {SCENARIO_PATH}/nsd/nsd.conf')

def set_dns_server_ip(host, dns_host):
    host_name = host.__str__()
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"
    dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
    ip_bytes = dns_host_ip.split(".")
    ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
    dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['dns-server-ip'] = f'{dns_host_ip_in_hex}'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def stop_dns_server(dns_host):
    dns_host.cmd('nsd-control stop')
    dns_host.cmd('pkill nsd')

def create_host_config(host, host_config: str, app_name, app_id, dns_host_ip_in_hex=None):
    host_name = host.__str__()
    unicast_ip = host.IP(intf=host.defaultIntf())
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['network'] = f'-{host_name}'
    config['unicast'] = unicast_ip
    config['logging']['level'] = 'fatal'
    config['logging']['console'] = 'true'
    config['logging']['file']['enable'] = 'true'
    config['logging']['file']['path'] = f'/var/log/{host_name}.log'
    config['applications'][0]['name'] = app_name
    config['applications'][0]['id'] = app_id
    config['routing'] = f'{host_name}'
    if dns_host_ip_in_hex is not None:
        config['dns-server-ip'] = f'{dns_host_ip_in_hex}'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_publisher_config(host, serviceId, mcast_ip, dns_host_ip_in_hex=None):
    host_name = host.__str__()
    publisher_config_template = f"{SCENARIO_PATH}/vsomeip-configs/vsomeip-udp-mininet-publisher.json"
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{serviceId}_pub.json"
    exists = Path(host_config).is_file()
    if not exists:
        host.cmd(f'cp {publisher_config_template} {host_config}')
        app_id = f"0x{int(serviceId):04x}"
        app_name = host_name + "-" + str(serviceId)
        create_host_config(host, host_config, app_name, app_id, dns_host_ip_in_hex)
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['services'][0]['service'] = f"0x{int(serviceId):04x}"
        config['services'][0]['instance'] = f"0x{int(INSTANCE_ID):04x}"
        config['services'][0]['unreliable'] = str(50000+serviceId)
        config['services'][0]['eventgroups'][0]['multicast']['address'] = mcast_ip
        config['services'][0]['eventgroups'][0]['multicast']['port'] = str(serviceId)
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)
    else:
        with open(host_config, 'r') as file:
            config = json.load(file)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_subscriber_config(host, serviceId, client_id, dns_host_ip_in_hex=None):
    host_name = host.__str__()
    subscriber_config_template = f"{SCENARIO_PATH}/vsomeip-configs/vsomeip-udp-mininet-subscriber.json"
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{serviceId}_sub.json"
    exists = Path(host_config).is_file()
    if not exists:
        host.cmd(f'cp {subscriber_config_template} {host_config}')
        app_id = f"0x{int(client_id):04x}"
        app_name = host_name + "-" + str(serviceId) + "-" + str(client_id)
        create_host_config(host, host_config, app_name, app_id, dns_host_ip_in_hex)
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['clients'][0]['service'] = f"0x{int(serviceId):04x}"
        config['clients'][0]['instance'] = f"0x{int(INSTANCE_ID):04x}"
        port = 40000 + int(client_id)
        config['clients'][0]['unreliable'] = [port]
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)
    else: 
        with open(host_config, 'r') as file:
            config = json.load(file)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_publisher_certificate(host, serviceId):
    host_name = host.__str__()
    certname = f'{host_name}_{serviceId}'
    certificate = f'{SCENARIO_PATH}/certificates/{certname}.service.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{certname}.service.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        port = 50000+serviceId
        host.cmd(f'{SCENARIO_PATH}/pub-svcb-and-tlsa-generator.bash {serviceId} {INSTANCE_ID} {MAJOR_VERSION} {MINOR_VERSION} {host_ip} {port} {PROTOCOL} {certname}')
        host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{serviceId}_pub.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def create_subscriber_certificate(host, serviceId, client_id):
    host_name = host.__str__()
    certname = f'{host_name}_{client_id}'
    certificate = f'{SCENARIO_PATH}/certificates/{certname}.client.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{certname}.client.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        port = 40000 + int(client_id)
        host.cmd(f'{SCENARIO_PATH}/sub-svcb-and-tlsa-generator.bash {client_id} {serviceId} {INSTANCE_ID} {MAJOR_VERSION} {host_ip} {port} {PROTOCOL} {certname}')
        host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{serviceId}_sub.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def set_subscriber_counts_to_record():
    host_configs = Path(f"{SCENARIO_PATH}/vsomeip-configs").rglob('*pub.json')
    for host_config in host_configs:
        with open(host_config, 'r') as file:
            config = json.load(file)
        count_sub_certs = len(config['client-certificates'])
        config['subscriber-count-to-record'] = f'{count_sub_certs}'
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def start_someip_app(host, config_file, config_app_name, launch_app_name, launch_params=""):
    host_name = host.__str__()
    if STD_CONDITION:
        host.cmd(f"env VSOMEIP_CONFIGURATION={config_file}  VSOMEIP_APPLICATION_NAME={config_app_name} {PROJECT_PATH}/vsomeip/build/examples/{launch_app_name} &> /var/log/{host_name}.std &")
    else:
        host.cmd(f"env VSOMEIP_CONFIGURATION={config_file}  VSOMEIP_APPLICATION_NAME={config_app_name} {PROJECT_PATH}/vsomeip/build/examples/{launch_app_name} &")

def start_someip_subscriber_app(host, service_id, client_id):
    host_name = host.__str__()
    config_file = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{service_id}_sub.json"
    config_app_name = f"{host_name}-{service_id}-{client_id}"
    launch_params = f"--serviceid {service_id} --instanceid {INSTANCE_ID}"
    start_someip_app(host, config_file, config_app_name, "my-subscriber", launch_params)

def start_someip_publisher_app(host, service_id):
    host_name = host.__str__()
    config_file = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}_{service_id}_pub.json"
    config_app_name = f"{host_name}-{service_id}"
    launch_params = f"--serviceid {service_id} --instanceid {INSTANCE_ID}"
    start_someip_app(host, config_file, config_app_name, "my-publisher", launch_params)

def stop_subscriber_app(host):
    host.cmd("pkill my-subscriber")

def stop_publisher_app(host):
    host.cmd("pkill my-publisher")

def start_evaluation(evaluation_option: str, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    entire_evaluation_start = time.time()
    if WITH_DNSSEC in add_compile_definitions:
        print("Starting DNS server ... ")
        start_dns_server(dns_host)
        print("Done.")
    # start statistics writer
    print("Starting statistics-writer ...")
    # check if result dir exists and create it if not
    if not Path(f"{SCENARIO_PATH}/statistic-results/{evaluation_option}-series").is_dir():
        subprocess.run(f"mkdir -p {SCENARIO_PATH}/statistic-results/{evaluation_option}-series", shell = True) 
    statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(1), f"{SCENARIO_PATH}/statistic-results/{evaluation_option}-series", evaluation_option])
    # statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results", evaluation_option])
    print("Done.")
    # start someip publisher and subscribers
    print("Starting SOME/IP publisher ... ")
    start_someip_publisher_app(net['lRR'], 2114)
    publisher_initialized_file = Path(f"{PROJECT_PATH}/publisher-initialized")
    while not publisher_initialized_file.is_file():
        time.sleep(1)
    # Give an extra second for startup
    time.sleep(1) 
    print("Done.")
    print("Starting SOME/IP subscribers ... ")
    start_someip_subscriber_app(net['adas'], 2114, 301)
    print("Done.")
    evaluation_run_start = time.time()
    # Wait for statistics writer
    print("Waiting until all statistics are contributed ... ")
    return_code = statistics_writer_process.wait(timeout=10)
    # wait 
    time.sleep(10)
    if return_code == 0:
        print("Done.")
        evaluation_run_end = time.time()
        print(f"RUN ({evaluation_option}): ({evaluation_run_end-evaluation_run_start}s)")
    else:
        print(f"statistics writer failed with return code {return_code}")
        print(f"evaluation run {evaluation_option} failed ")
    # stop someip publisher, subscribers and dns server
    print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
    stop_subscriber_app(net['adas'])
    stop_publisher_app(net['lRR'])
    print("Done.")
    # Give an extra second for remaining transmissions
    time.sleep(1)
    entire_evaluation_end = time.time()
    print(f"TOTAL TIME FOR OPTION {evaluation_option}: {entire_evaluation_end - entire_evaluation_start}s")

def start_debug(evaluation_option: str, subscriber_count: int, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    # start statistics writer
    print("Starting statistics-writer ...")
    subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{SCENARIO_PATH}/statistic-results/debug", evaluation_option])
    print("Done.")
    # start dns server
    if WITH_DNSSEC in add_compile_definitions:
        print("Starting DNS server ... ")
        start_dns_server(net[dns_host_name])
        print("Done.")
    CLI(net)
    print("Done.")

def cleanup():
    subprocess.run(["pkill", "statistics-writ"])
    subprocess.run(f"rm -f {PROJECT_PATH}/vsomeip-zc*", shell=True)
    subprocess.run("rm -f /var/log/zc*.log", shell=True)
    subprocess.run(f"rm -f {PROJECT_PATH}/publisher-initialized", shell=True)
    subprocess.run(f"rm -f /var/log/zc*.std", shell=True)

def create_publishers(net, dns_host = None):
    dns_host_ip_in_hex = None
    if dns_host is not None:
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        ip_bytes = dns_host_ip.split(".")
        ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
        dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        service_id = services[service]["serviceId"]
        # publisher_port = services[service]["port"]
        mcast_ip = services[service]["mcast"]
        # ip = services[service]["ip"]
        net_name = services[service]["host"]
        if mcast_ip is None:
            lowerTwoDigestsServiceId = service_id % 256
            upperTwoDigestsServiceId = service_id // 256
            mcast_ip = "224.1." + str(upperTwoDigestsServiceId) + "." + str(lowerTwoDigestsServiceId)
            print (f"Service {service} on host {net_name} has no multicast IP. Selecting {mcast_ip} as multicast IP.")
        create_publisher_config(net[net_name], service_id, mcast_ip, dns_host_ip_in_hex)
        create_publisher_certificate(net[net_name], service_id)

def create_subscribers(net, dns_host = None):
    dns_host_ip_in_hex = None
    if dns_host is not None:
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        ip_bytes = dns_host_ip.split(".")
        ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
        dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as service_file:
        clients = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        net_name = clients[client]["host"]
        create_subscriber_config(net[net_name], service_id, client_id, dns_host_ip_in_hex)
        create_subscriber_certificate(net[net_name], service_id, client_id)

def reference_certificates():
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as client_file:
        clients = json.load(client_file)
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        client_host = clients[client]["host"]
        service_host = services[str(service_id)]["host"]
        client_cert = f"{SCENARIO_PATH}/certificates/{client_host}_{client_id}.client.cert.pem"
        client_config = f"{SCENARIO_PATH}/vsomeip-configs/{client_host}_{service_id}_sub.json"
        service_cert = f"{SCENARIO_PATH}/certificates/{service_host}_{service_id}.service.cert.pem"
        service_config = f"{SCENARIO_PATH}/vsomeip-configs/{service_host}_{service_id}_pub.json"
        with open(client_config, 'r') as file:
            client_conf = json.load(file)
        with open(service_config, 'r') as file:
            service_conf = json.load(file)
        client_conf['service-certificate-path'] = service_cert
        client_conf['client-certificates'] = ["only applies to services"]
        if "host" in service_conf['client-certificates'][0] or client_cert in service_conf['client-certificates']:
            service_conf['client-certificates'] = [client_cert]
        else:
            service_conf['client-certificates'].append(client_cert)
        service_conf['service-certificate-path'] = "only applies to clients"
        with open(client_config, 'w') as file:
            json.dump(client_conf, file, indent=4)
        with open(service_config, 'w') as file:
            json.dump(service_conf, file, indent=4)

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Starts a car network topology in mininet and runs some connection tests')
        parser.add_argument('--iperf', action='store_true', default=False, help='Run iperf tests')
        parser.add_argument('--debug', action='store_true', default=False, help='Enable debug output, such as network dumps')
        parser.add_argument('--connectivity', action='store_true', default=False, help='Test network connectivity')
        parser.add_argument('--clean', action='store_true', default=False, help='Clean up all mininet interfaces from previous runs')
        parser.add_argument('--noeval', action='store_true', default=False, help='Do not run evaluation')
        parser.add_argument('--evaluate', choices=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], default='H', help="""A: vanilla (vsomeip as it is),
                                                                                                                            B: w/ DNSSEC w/o SOME/IP SD,
                                                                                                                            C: w/ service authentication,
                                                                                                                            D: w/ service authentication + DNSSEC + DANE w/o SOME/IP SD,
                                                                                                                            E: w/ service and client authentiction,
                                                                                                                            F: w/ service and client authentiction + payload encryption,
                                                                                                                            G: w/ service and client authentication + DNSSEC + DANE,
                                                                                                                            H: w/ service and client authentication + DNSSEC + DANE + payload encryption""")
        args = parser.parse_args()

        if args.debug:
            setLogLevel('debug')
        else:
            setLogLevel('warning')

        print("Cleaning up mininet interfaces ... ")
        subprocess.run(['mn', '-c'])
        print("Done")
        if args.clean:
            print("Removing configs and certificates ... ")
            subprocess.run(f"rm -f {SCENARIO_PATH}/vsomeip-configs/*pub.json", shell=True)
            subprocess.run(f"rm -f {SCENARIO_PATH}/vsomeip-configs/*sub.json", shell=True)
            subprocess.run(f"rm -f {SCENARIO_PATH}/certificates/*.pem", shell=True)
            cleanup()
            reset_zone_files()
            print("Done.")
        else: 
            print("Reusing previous configurations and certificates ... ")

        print("Building mininet network ... ")
        topo: car_topology = car_topology()
        net = Mininet(topo=topo, controller=None, link=TCLink)
        net.start()
        for switch in net.switches:
            make_switch_traditional(net, switch.__str__())
        print("Done")

        print("Adding default routes ... ")
        for host in net.hosts:
            add_default_route(host)
        print("Done")

        if args.debug:
            dump_infos(net)

        if args.connectivity:
            print("Testing network connectivity ... ")
            test_connectivity(net)
            print("Done")

        if args.iperf:
            print( "Testing bandwidth between hosts ... " )
            test_bandwidth(net)
            print("Done")

        add_compile_definitions = compile_definitions[args.evaluate]
        print("Building vsomeip ... ")
        subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
        build_vsomeip()
        print("Done.")

        # # create host configs and certificates
        # print("Creating host configs and certificates ... (this can take some time)")
        # dns_host = None
        # if WITH_DNSSEC in add_compile_definitions:
        #     dns_host = net[DNSNODENAME]
        # create_publishers(net, dns_host)
        # create_subscribers(net, dns_host)
        # reference_certificates()
        # set_subscriber_counts_to_record()
        # print("Done.")

        # if not args.noeval:
        #     print("Starting vsomeip scenario ... ")
        #     # Evaluate
        #     start_evaluation(args.evaluate, add_compile_definitions, net, DNSNODENAME)
        #     print("Done.")
        # else:
        #     print("Starting debug mode ... ")
        #     start_debug(args.evaluate, 1, add_compile_definitions, net, DNSNODENAME)
        #     print("Done.")
        
    except KeyboardInterrupt:
        print("Caught Ctrl+C. Stopping mininet network.")
    except Exception as e:
        print("An error occurred: {}".format(e))    
    finally:
        print("Stopping mininet network, DNS and cleaning up ...")
        if 'add_compile_definitions' in locals() and WITH_DNSSEC in add_compile_definitions:
            stop_dns_server(net[DNSNODENAME])
        net.stop()
        print("Done.")

