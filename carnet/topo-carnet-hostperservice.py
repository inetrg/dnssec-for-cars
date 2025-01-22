#!/usr/bin/python

"""Custom topology

N hosts directly connected to one switch

Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
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
from subprocess import TimeoutExpired

DNS_HOST_NAME = 'dns'
PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"
SCENARIO_PATH = f"{PROJECT_PATH}/carnet"
START_DELAY_MS = 10000
num_pubs_started = 0
service_sub_counts = dict()
node_index = 0
node_names = dict()

INSTANCE_ID_INT = 1
INSTANCE_ID_HEX_STR = "0x{:04x}".format(INSTANCE_ID_INT)
INSTANCE_ID = str(int(INSTANCE_ID_INT))
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PROTOCOL = "UDP"
# compile definitions
WITH_SERVICE_AUTHENTICATION = 'WITH_SERVICE_AUTHENTICATION'
WITH_CLIENT_AUTHENTICATION = 'WITH_CLIENT_AUTHENTICATION'
NO_SOMEIP_SD = 'NO_SOMEIP_SD'
WITH_DNSSEC = 'WITH_DNSSEC'
WITH_DANE = 'WITH_DANE'
WITH_ENCRYPTION = 'WITH_ENCRYPTION'

def get_node_name(host):
    global node_index
    global node_names
    host_name = host.__str__()
    if host_name in node_names:
        return node_names[host_name]
    node_index += 1
    node_name = f"h{node_index}"
    node_names[host_name] = node_name
    return node_name

class car_topo( Topo ):
    "Simple topology example."

    def build( self: Topo):
        "Create custom topo."

        # Add switch
        sFR = self.addSwitch('s1')
        sFL = self.addSwitch('s2')
        sC = self.addSwitch('s3')
        sRR = self.addSwitch('s4')
        sRL = self.addSwitch('s5')

        # add DNS node
        dns = self.addHost(DNS_HOST_NAME)

        self.addLink(sRL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sC, dns, bw=1000, delay='0ms', loss=0, max_queue_size=99999)

        files = [f"{SCENARIO_PATH}/publishers.json", f"{SCENARIO_PATH}/subscribers.json"]
        for (file) in files:
            with open(file, "r") as hosts_file:
                hosts = json.load(hosts_file)
            client_id = ""
            for host in hosts:
                host_name = hosts[host]["host"].lower()
                service_id = "-" + str(hosts[host]["serviceId"])
                if "clientId" in hosts[host]:
                    client_id = "-" + str(hosts[host]["clientId"])
                node_name = host_name + service_id + client_id
                node = self.addHost(get_node_name(node_name))
                if host_name == "zcrl":
                    self.addLink(sRL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "zcfl":
                    self.addLink(sFL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "zcrr":
                    self.addLink(sRR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "zcfr":
                    self.addLink(sFR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "lrl":
                    self.addLink(sRL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "lfl":
                    self.addLink(sFL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "lrr":
                    self.addLink(sRR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "lfr":
                    self.addLink(sFR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "adas":
                    self.addLink(sRR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "con":
                    self.addLink(sFL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "inf":
                    self.addLink(sFL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "cr":
                    self.addLink(sRL, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                elif host_name == "cf":
                    self.addLink(sFR, node, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
                else:
                    print(f"ERROR Host {host_name} not found in topology")

def make_switch_traditional(net: Mininet, switch: str):
    net[switch].cmd('ovs-ofctl add-flow {} action=normal'.format(switch))

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

def simple_tests(net: Mininet):
    print( "Testing network connectivity" )
    net.pingAll()
    print( "Testing bandwidth between hosts" )
    unique_host_tuples_set = set(combinations(net.hosts, 2))
    for host_tuple in unique_host_tuples_set:
        net.iperf(hosts=host_tuple,l4Type='TCP')
        net.iperf(hosts=host_tuple,l4Type='UDP')

def add_default_route(host):
    host_name = host.__str__()
    host.cmd(f'route add default gw 10.0.0.0 {host_name}-eth0')

def start_dns_server(dns_host):
    dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
    dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {SCENARIO_PATH}/nsd/nsd.conf")
    dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/service.zone")
    dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/client.zone")
    dns_host.cmd('nsd-control-setup')
    dns_host.cmd(f'nsd -c {SCENARIO_PATH}/nsd/nsd.conf')

def stop_dns_server(dns_host):
    dns_host.cmd('nsd-control stop')
    dns_host.cmd('pkill nsd')

def get_subscriber_config_path(host, service_id, client_id):
    host_name = host.__str__()
    return f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"

def get_subscriber_app_name(host, service_id, client_id):
    host_name = host.__str__()
    return f"{host_name}"#-{service_id}-{client_id}"

def get_subscriber_cert_name(host, service_id, client_id):
    host_name = host.__str__()
    return f'{host_name}'#_{client_id}'

def get_publisher_config_path(host, service_id):
    host_name = host.__str__()
    return f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"

def get_publisher_app_name(host, service_id):
    host_name = host.__str__()
    return f"{host_name}"#-{service_id}"

def get_publisher_cert_name(host, service_id):
    host_name = host.__str__()
    return f'{host_name}'#_{service_id}'

def create_subscriber_config(host, service_id, client_id, dns_host_ip_in_hex=None):
    host_config = get_subscriber_config_path(host, service_id, client_id)
    app_name = get_subscriber_app_name(host, service_id, client_id)
    create_host_config(host, host_config, app_name, dns_host_ip_in_hex)
    
    with open(host_config, 'r') as file:
        config = json.load(file)

    app_idx = len(config['applications'])
    config['applications'].append({})
    config['applications'][app_idx]['name'] = app_name
    config['applications'][app_idx]['id'] = "0x{:04x}".format(client_id)

    client_idx = len(config['clients'])
    config['clients'].append({})
    config['clients'][client_idx]['service'] = f"0x{int(service_id):04x}"
    config['clients'][client_idx]['instance'] = INSTANCE_ID_HEX_STR
    config['clients'][client_idx]['client-id'] = f"0x{int(client_id):04x}"
    port = 40000 + int(client_id)
    config['clients'][client_idx]['unreliable'] = [port]

    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_publisher_config(host, service_id, mcast_ip, dns_host_ip_in_hex=None):
    host_config = get_publisher_config_path(host, service_id)
    app_name = get_publisher_app_name(host, service_id)
    create_host_config(host, host_config, app_name, dns_host_ip_in_hex)
    
    with open(host_config, 'r') as file:
        config = json.load(file)

    app_idx = len(config['applications'])
    config['applications'].append({})
    config['applications'][app_idx]['name'] = app_name
    config['applications'][app_idx]['id'] = f"0x{int(service_id):04x}"

    service_idx = len(config['services'])
    config['services'].append({})
    config['services'][service_idx]['service'] = f"0x{int(service_id):04x}"
    config['services'][service_idx]['instance'] = f"0x{int(INSTANCE_ID):04x}"
    config['services'][service_idx]['unreliable'] = str(50000+service_id)
    config['services'][service_idx]['client-certificates'] = []
    config['services'][service_idx]['events'] = [
        {"events": f"0x{int(10000+service_id):04x}", "is_field" : "true", "update-cycle" : 0},
        {"events": f"0x{int(20000+service_id):04x}", "is_field" : "true"}
    ]
    config['services'][service_idx]['eventgroups'] = [
        {"eventgroup" : f"0x{int(30000+service_id):04x}", "events" : [ f"0x{int(10000+service_id):04x}", f"0x{int(20000+service_id):04x}" ], "multicast" : { "address" : mcast_ip, "port" :  str(service_id)}}
    ]
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_host_config(host, host_config: str, app_name, dns_host_ip_in_hex=None):
    config_template = f"{SCENARIO_PATH}/vsomeip-configs/vsomeip-udp-mininet-multihost.json"
    if Path(host_config).is_file():
        return
    host.cmd(f'cp {config_template} {host_config}')
    host_name = host.__str__()
    unicast_ip = host.IP(intf=host.defaultIntf())
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['network'] = f'-{host_name}'
    config['unicast'] = unicast_ip
    config['logging']['file']['path'] = f'/var/log/carnet/{host_name}.log'
    config['routing'] = app_name
    if dns_host_ip_in_hex is not None:
        config['dns-server-ip'] = f'{dns_host_ip_in_hex}'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_subscriber_certificate(host, service_id, client_id):
    certname = get_subscriber_cert_name(host, service_id, client_id)
    certificate = f'{SCENARIO_PATH}/certificates/{certname}.client.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{certname}.client.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        port = 40000 + int(client_id)
        host.cmd(f'{SCENARIO_PATH}/sub-svcb-and-tlsa-generator.bash {client_id} {service_id} {INSTANCE_ID} {MAJOR_VERSION} {host_ip} {port} {PROTOCOL} {certname}')
    host_config = get_subscriber_config_path(host, service_id, client_id)
    with open(host_config, 'r') as file:
        config = json.load(file)
    client_idx = 0
    for idx, client in enumerate(config['clients']):
        if client['service'] == f"0x{service_id:04x}":
            client_idx = idx
    config['clients'][client_idx]['private-key-path'] = private_key
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_publisher_certificate(host, service_id):
    certname = get_publisher_cert_name(host, service_id)
    certificate = f'{SCENARIO_PATH}/certificates/{certname}.service.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{certname}.service.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        port = 50000+service_id
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{SCENARIO_PATH}/pub-svcb-and-tlsa-generator.bash {service_id} {INSTANCE_ID} {MAJOR_VERSION} {MINOR_VERSION} {host_ip} {port} {PROTOCOL} {certname}')
    host_config = get_publisher_config_path(host, service_id)
    with open(host_config, 'r') as file:
        config = json.load(file)
    service_idx = 0
    for idx, service in enumerate(config['services']):
        if service['service'] == f"0x{service_id:04x}":
            service_idx = idx
    config['services'][service_idx]['private-key-path'] = private_key
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def reset_zone_files():
    subprocess.run(["su", "-", "vm-user", "-c", f"{SCENARIO_PATH}/reset-zone-files.bash"])

def start_someip_subscriber_app(host, service_id, client_id):
    host_config = get_subscriber_config_path(host, service_id, client_id)
    app_name = get_subscriber_app_name(host, service_id, client_id)
    launch_cmd = f"env VSOMEIP_CONFIGURATION={host_config} VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-subscriber --serviceid {service_id} --instanceid {INSTANCE_ID} --waitms {START_DELAY_MS} &"
    host.cmd(launch_cmd)

def start_someip_publisher_app(host, service_id):
    host_config = get_publisher_config_path(host, service_id)
    app_name = get_publisher_app_name(host, service_id)
    launch_cmd = f"env VSOMEIP_CONFIGURATION={host_config} VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-publisher --serviceid {service_id} --instanceid {INSTANCE_ID} --waitms {START_DELAY_MS} &"
    host.cmd(launch_cmd)

def start_all_publishers(net):
    global num_pubs_started
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        service_id = services[service]["serviceId"]
        host_name = get_node_name(services[service]["host"].lower() + "-" + str(service_id))
        # start_someip_publisher_app(net[host_name], service_id)
        # print (f"Starting publisher for service {service_id} on host {host_name}")
        start_someip_publisher_app(net[host_name], service_id)
        # thread = Thread(target=start_someip_publisher_app, args=(net[host_name], service_id))
        # thread.start()
        num_pubs_started += 1
        # time.sleep(0.01)

def start_all_subscribers(net):
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as service_file:
        clients = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        host_name = get_node_name(clients[client]["host"].lower() + "-" + str(service_id) + "-" + str(client_id))
        # print (f"Starting subscriber for service {service_id} and client {client_id} on host {host_name}")
        start_someip_subscriber_app(net[host_name], service_id, client_id)
        # thread = Thread(target=start_someip_subscriber_app, args=(net[host_name], service_id, client_id))
        # thread.start()
        # time.sleep(0.01)

# def wait_all_publishers_initialized():
#     global num_pubs_started
#     print(f"Waiting for all {num_pubs_started} publishers to be initialized ...")
#     publisher_initialized_file = Path(f"{PROJECT_PATH}/")
#     while True:
#         num_pubs_initialized = len(list(publisher_initialized_file.glob("publisher-initialized-*")))
#         if (num_pubs_initialized == num_pubs_started):
#             break
#         time.sleep(0.01)

def stop_all_subscriber_apps(net):
    for host in net.hosts:
        stop_subscriber_app(host)
    
def stop_all_publisher_apps(net):
    for host in net.hosts:
        stop_publisher_app(host)

def stop_subscriber_app(host):
    host.cmd("pkill -f my-subscriber")

def stop_publisher_app(host):
    host.cmd("pkill -f my-publisher")

def switch_someip_branch(branch_name: str):
    result = subprocess.run(f"cd {PROJECT_PATH}/vsomeip && git checkout {branch_name}", shell=True)
    return result.returncode

def build_vsomeip():
    # subprocess.run(["su", "-", "vm-user", "-c", f"{PROJECT_PATH}/build_vsomeip.bash"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f'su - vm-user -c "cmake -B {PROJECT_PATH}/vsomeip/build -S {PROJECT_PATH}/vsomeip"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target all -- -j$(nproc)"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target examples -- -j$(nproc)"', shell=True)
    subprocess.run(f'su - vm-user -c "$(which cmake) --build {PROJECT_PATH}/vsomeip/build --config Release --target statistics-writer -- -j$(nproc)"', shell=True)

def cleanup():
    subprocess.run(["pkill", "statistics-writ"])
    subprocess.run(f"rm -f {PROJECT_PATH}/vsomeip-*", shell=True)
    subprocess.run(f"rm -f {PROJECT_PATH}/publisher-initialized*", shell=True)

def start_statistics_writer(evaluation_option: str):
    global service_sub_counts
    print("Starting statistics-writer ...")
    # check if result dir exists and create it if not
    out_path = f"{SCENARIO_PATH}/statistic-results/{evaluation_option}-series"
    if not Path(out_path).is_dir():
        subprocess.run(f"mkdir -p {out_path}", shell = True) 
    services = "[" + ",".join(str(service_id) for service_id in service_sub_counts.keys()) + "]"
    member_counts = "[" + ",".join(str(count) for count in service_sub_counts.values()) + "]"
    print(f"services: {services}")
    print(f"member_counts: {member_counts}")
    statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", services, member_counts, out_path, evaluation_option])
    print("Done.")
    return statistics_writer_process

def start_evaluation(total_evaluation_runs: int, evaluation_option: str, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    entire_evaluation_start = time.time()
    current_run = 1
    while current_run <= total_evaluation_runs:
        print(f"Starting {current_run}/{total_evaluation_runs} evaluation run {evaluation_option} ... ")
        # start statistics writer
        statistics_writer_process = start_statistics_writer(evaluation_option)
        # start dns server
        if WITH_DNSSEC in add_compile_definitions:
            print("Starting DNS server ... ")
            start_dns_server(net[dns_host_name])
            print("Done.")
        # start someip publisher and subscribers
        print("Starting SOME/IP publishers ... ")
        publishers_start = time.time()
        start_all_publishers(net)
        # wait_all_publishers_initialized()
        publishers_end = time.time()
        # Give an extra second for startup
        print("Done.")
        print("Starting SOME/IP subscribers ... ")
        subscribers_start = time.time()
        start_all_subscribers(net)
        subscribers_end = time.time()
        print("Done.")
        print(f"Total initialization time: {subscribers_end-publishers_start}s (publishers: {publishers_end-publishers_start}s, subscribers: {subscribers_end-subscribers_start}s)")
        evaluation_run_start = time.time()
        # Wait for statistics writer
        print("Waiting until all statistics are contributed ... ")
        try:
            return_code = statistics_writer_process.wait(timeout=30)
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
        # stop someip publisher, subscribers and dns server
        print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
        stop_all_subscriber_apps(net)
        stop_all_publisher_apps(net)
        if WITH_DNSSEC in add_compile_definitions:
            stop_dns_server(net[dns_host_name])
        cleanup()
        print("Done.")
        # Give an extra second for remaining transmissions
        time.sleep(1)
    entire_evaluation_end = time.time()
    print(f"TOTAL TIME FOR OPTION {evaluation_option} in {total_evaluation_runs} RUN/S: {entire_evaluation_end - entire_evaluation_start}s")

def create_publishers(net, dns_host_name = None):
    dns_host_ip_in_hex = None
    if dns_host_name is not None:
        dns_host = net[dns_host_name]
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        ip_bytes = dns_host_ip.split(".")
        ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
        dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
        
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        service_id = services[service]["serviceId"]
        net_name = get_node_name(services[service]["host"].lower() + "-" + str(service_id))
        mcast_ip = services[service]["mcast"]
        if mcast_ip is None:
            lowerTwoDigetsServiceId = service_id % 256
            upperTwoDigetsServiceId = service_id // 256
            mcast_ip = "224.1." + str(upperTwoDigetsServiceId) + "." + str(lowerTwoDigetsServiceId)
            print (f"Service {service_id} on host {net_name} has no multicast IP. Selecting {mcast_ip} as multicast IP.")
        create_publisher_config(net[net_name], service_id, mcast_ip, dns_host_ip_in_hex)
        create_publisher_certificate(net[net_name], service_id)

def create_subscribers(net, dns_host = None):
    dns_host_ip_in_hex = None
    if dns_host_name is not None:
        dns_host = net[dns_host_name]
        dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
        ip_bytes = dns_host_ip.split(".")
        ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
        dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as service_file:
        clients = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        net_name = get_node_name(clients[client]["host"].lower() + "-" + str(service_id) + "-" + str(client_id))
        create_subscriber_config(net[net_name], service_id, client_id, dns_host_ip_in_hex)
        create_subscriber_certificate(net[net_name], service_id, client_id)

def reference_certificates():
    global service_sub_counts
    services_per_host = dict()
    clients_per_host = dict()
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as client_file:
        clients = json.load(client_file)
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        service_host_name = services[str(service_id)]["host"].lower() + "-" + str(service_id)
        service_host = get_node_name(service_host_name)
        client_host_name = clients[client]["host"].lower() + "-" + str(service_id) + "-" + str(client_id)
        client_host = get_node_name(client_host_name)

        if service_host in services_per_host:
            services_per_host[service_host] += 1
        else:
            services_per_host[service_host] = 1
        if client_host in clients_per_host:
            clients_per_host[client_host] += 1
        else:
            clients_per_host[client_host] = 1

        service_config_path = get_publisher_config_path(net[service_host], service_id)
        client_config_path = get_subscriber_config_path(net[client_host], service_id, client_id)
        service_cert_path = f"{SCENARIO_PATH}/certificates/{get_publisher_cert_name(net[service_host], service_id)}.service.cert.pem"
        client_cert_path = f"{SCENARIO_PATH}/certificates/{get_subscriber_cert_name(net[client_host], service_id, client_id)}.client.cert.pem"

        with open(service_config_path, 'r') as file:
            service_config = json.load(file)
        with open(client_config_path, 'r') as file:
            client_config = json.load(file)

        client_idx = 0
        for i in range(0, len(client_config['clients'])):
            if client_config['clients'][i]['service'] == f"0x{service_id:04x}":
                client_idx = i
        client_config['clients'][client_idx]['service-certificate-path'] = service_cert_path
        service_idx = 0
        for i in range(0, len(service_config['services'])):
            if service_config['services'][i]['service'] == f"0x{service_id:04x}":
                service_idx = i
        exists = False
        for cert in service_config['services'][service_idx]['client-certificates']:
            if cert['id'] == f"0x{client_id:04x}":
                # print(f"Client certificate for client {client_id} of service {service_id} already exists.")
                exists = True
                break;
        if not exists:
            service_config['services'][service_idx]['client-certificates'].append({"id": f"0x{client_id:04x}", "certificate-path": client_cert_path})

        with open(service_config_path, 'w') as file:
            json.dump(service_config, file, indent=4)
        with open(client_config_path, 'w') as file:
            json.dump(client_config, file, indent=4)

        if service_id in service_sub_counts:
            service_sub_counts[service_id] += 1
        else:
            service_sub_counts[service_id] = 1

    print("Num Service hosts: ", len(services_per_host))
    print("Num Client hosts: ", len(clients_per_host))
    print("Max clients per publisher: ", max(services_per_host.values()))

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

    args = parser.parse_args()
    evaluation_option: str = args.evaluate
    total_evaluation_runs: int = args.runs
    compile_definitions = {'A':'',
                           'B':f'{NO_SOMEIP_SD} {WITH_DNSSEC}',
                           'C':f'{WITH_SERVICE_AUTHENTICATION}',
                           'D':f'{NO_SOMEIP_SD} {WITH_SERVICE_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
                           'E':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION}',
                           'F':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_ENCRYPTION}',
                           'G':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE}',
                           'H':f'{WITH_SERVICE_AUTHENTICATION} {WITH_CLIENT_AUTHENTICATION} {WITH_DNSSEC} {WITH_DANE} {WITH_ENCRYPTION}'}
    add_compile_definitions = compile_definitions[evaluation_option]

    print("Cleaning up mininet interfaces ... ")
    subprocess.run(['mn', '-c'])
    cleanup()
    subprocess.run(f"rm -f /var/log/carnet/*", shell=True)
    print("Done")

    # remove configs and certificates for clean start
    if args.clean_start:
        print("Removing configs and certificates ... ")
        # rm all host configs except the templates vsomeip-udp-mininet-publisher.json and vsomeip-udp-mininet-subscriber.json
        for file in Path(f"{SCENARIO_PATH}/vsomeip-configs").glob("*.json"):
            if not file.name.startswith("vsomeip-udp-mininet"):
                subprocess.run(f"rm -f {file}", shell=True)
        subprocess.run(f"rm -f {SCENARIO_PATH}/certificates/*", shell=True)
        reset_zone_files()
        print("Done.")

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    topo: car_topo = car_topo()
    dns_host_name = DNS_HOST_NAME
    net: Mininet = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()
    for switch in net.switches:
        make_switch_traditional(net, switch.__str__())
    for host in net.hosts:
        add_default_route(host)
    print("Done.")
    # build vsomeip
    print("Building vsomeip ... ")
    # set compile definitions
    subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
    build_vsomeip()
    print("Done.")
    
    # create host configs and certificates
    print("Creating host configs and certificates ... (this may take a while)")
    if args.clean_start:
        create_publishers(net, dns_host_name)    
        create_subscribers(net, dns_host_name)
    reference_certificates()
    print("Done.")
    # Evaluate
    if args.evaluate and args.runs:
        start_evaluation(total_evaluation_runs, evaluation_option, add_compile_definitions, net, dns_host_name)
    print("Stopping mininet network")
    net.stop()
    print("Done.")
else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-1sw-Nhosts.py --topo simple_topo
    topos = {'car_topo': (lambda: car_topo())}
