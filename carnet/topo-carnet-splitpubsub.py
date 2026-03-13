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
num_pubs_started = 0
service_sub_counts = dict()
managers = dict()

INSTANCE_ID_INT = 1
INSTANCE_ID_HEX_STR = "0x{:04x}".format(INSTANCE_ID_INT)
INSTANCE_ID = str(int(INSTANCE_ID_INT))
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PROTOCOL = "UDP"
PUBLISHER_PORT = 10000
SUBSCRIBER_PORT = 20000
EVENT_ID_1 = 30000
EVENT_ID_2 = 40000
EVENT_GROUP_ID = 50000
# compile definitions
WITH_SERVICE_AUTHENTICATION = 'WITH_SERVICE_AUTHENTICATION'
WITH_CLIENT_AUTHENTICATION = 'WITH_CLIENT_AUTHENTICATION'
NO_SOMEIP_SD = 'NO_SOMEIP_SD'
WITH_DNSSEC = 'WITH_DNSSEC'
WITH_DANE = 'WITH_DANE'
WITH_ENCRYPTION = 'WITH_ENCRYPTION'

apps_per_host = dict()
hosts = dict()
sub_apps = dict()
pub_apps = dict()

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

        # Add links
        self.addLink(sRL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sRR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sFR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999)
        self.addLink(sC, dns, bw=1000, delay='0ms', loss=0, max_queue_size=99999)

        # add hosts (names must be lower case!)
        for pubsub in ["p", "s"]:
            zcRl = self.addHost('zcrl'+pubsub)
            zcFl = self.addHost('zcfl'+pubsub)
            zcRr = self.addHost('zcrr'+pubsub)
            zcFr = self.addHost('zcfr'+pubsub)
            lRL = self.addHost('lrl'+pubsub)
            lFL = self.addHost('lfl'+pubsub)
            lRR = self.addHost('lrr'+pubsub)
            lFR = self.addHost('lfr'+pubsub)
            cR = self.addHost('cr'+pubsub)
            cF = self.addHost('cf'+pubsub)
            adas = self.addHost('adas'+pubsub)
            inf = self.addHost('inf'+pubsub)
            con = self.addHost('con'+pubsub)
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
    dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {PROJECT_PATH}/nsd/nsd.conf")
    dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/service.zone")
    dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/client.zone")
    dns_host.cmd('nsd-control-setup')
    dns_host.cmd(f'nsd -c {PROJECT_PATH}/nsd/nsd.conf')

def stop_dns_server(dns_host):
    dns_host.cmd('nsd-control stop')
    dns_host.cmd('pkill nsd')

def get_net_name(host, is_publisher):
    if is_publisher:
        return host.lower() + "p"
    return host.lower() + "s"

def get_subscriber_config_path(host, service_id, client_id):
    host_name = host.__str__()
    return f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"

def get_subscriber_app_name(host, service_id, client_id):
    host_name = host.__str__()
    return f"{host_name}-{service_id}-{client_id}"

def get_subscriber_cert_name(host, service_id, client_id):
    host_name = host.__str__()
    return f'{host_name}_{client_id}'

def get_publisher_config_path(host, service_id):
    host_name = host.__str__()
    return f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"

def get_publisher_app_name(host, service_id):
    host_name = host.__str__()
    return f"{host_name}-{service_id}"

def get_publisher_cert_name(host, service_id):
    host_name = host.__str__()
    return f'{host_name}_{service_id}'

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
    apps_per_host[host.__str__()] = app_idx + 1

    client_idx = len(config['clients'])
    config['clients'].append({})
    config['clients'][client_idx]['service'] = f"0x{int(service_id):04x}"
    config['clients'][client_idx]['instance'] = INSTANCE_ID_HEX_STR
    config['clients'][client_idx]['client-id'] = f"0x{int(client_id):04x}"
    port = SUBSCRIBER_PORT + int(client_id)
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
    apps_per_host[host.__str__()] = app_idx + 1

    service_idx = len(config['services'])
    config['services'].append({})
    config['services'][service_idx]['service'] = f"0x{int(service_id):04x}"
    config['services'][service_idx]['instance'] = f"0x{int(INSTANCE_ID):04x}"
    config['services'][service_idx]['unreliable'] = str(PUBLISHER_PORT+service_id)
    config['services'][service_idx]['client-certificates'] = []
    config['services'][service_idx]['events'] = [
        {"events": f"0x{int(EVENT_ID_1+service_id):04x}", "is_field" : "true", "update-cycle" : 10000},
        {"events": f"0x{int(EVENT_ID_2+service_id):04x}", "is_field" : "true"}
    ]
    config['services'][service_idx]['eventgroups'] = [
        {"eventgroup" : f"0x{int(EVENT_GROUP_ID+service_id):04x}", "events" : [ f"0x{int(EVENT_ID_1+service_id):04x}", f"0x{int(EVENT_ID_2+service_id):04x}" ], "multicast" : { "address" : mcast_ip, "port" :  str(service_id)}}
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
        port = SUBSCRIBER_PORT + int(client_id)
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
        port = PUBLISHER_PORT+service_id
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
    launch_cmd = f"env VSOMEIP_CONFIGURATION={host_config} VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-subscriber --serviceid {service_id} --instanceid {INSTANCE_ID} --eventgroupid {EVENT_GROUP_ID + service_id} --eventid {EVENT_ID_1 + service_id} --clientid {client_id} &"
    host.cmd(f"{launch_cmd}")

def start_someip_publisher_app(host, service_id):
    host_config = get_publisher_config_path(host, service_id)
    app_name = get_publisher_app_name(host, service_id)
    launch_cmd = f"env VSOMEIP_CONFIGURATION={host_config} VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-publisher --serviceid {service_id} --instanceid {INSTANCE_ID} --eventgroupid {EVENT_GROUP_ID + service_id} --eventid {EVENT_ID_1 + service_id} &"
    host.cmd(f"{launch_cmd}")

def start_managers(net):
    global num_pubs_started
    global managers
    managers = dict()
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        net_name = get_net_name(services[service]["host"],True)
        if net_name not in managers:
            service_id = services[service]["serviceId"]
            managers[net_name] = get_publisher_app_name(net[net_name], services[service]["serviceId"])
            start_someip_publisher_app(net[net_name], service_id)
            num_pubs_started += 1
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as sub_file:
        clients = json.load(sub_file)
    for client in clients:
        net_name = get_net_name(clients[client]["host"], False)
        if net_name not in managers:
            service_id = clients[client]["serviceId"]
            client_id = clients[client]["clientId"]
            managers[net_name] = get_subscriber_app_name(net[net_name], service_id, client_id)
            start_someip_subscriber_app(net[net_name], service_id, client_id)

def start_all_publishers(net):
    global num_pubs_started
    global managers
    with open (f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        service_id = services[service]["serviceId"]
        host_name = get_net_name(services[service]["host"], True)
        if managers[host_name] == get_publisher_app_name(net[host_name], service_id):
            continue
        start_someip_publisher_app(net[host_name], service_id)
        num_pubs_started += 1
        # time.sleep(0.01)

def start_all_subscribers(net):
    with open (f"{SCENARIO_PATH}/subscribers.json", "r") as service_file:
        clients = json.load(service_file)
    for client in clients:
        service_id = clients[client]["serviceId"]
        client_id = clients[client]["clientId"]
        host_name = get_net_name(clients[client]["host"], False)
        if managers[host_name] == get_subscriber_app_name(net[host_name], service_id, client_id):
            continue
        start_someip_subscriber_app(net[host_name], service_id, client_id)
        # time.sleep(0.01)

def wait_all_publishers_initialized():
    return
    # global num_pubs_started
    # publisher_initialized_file = Path(f"{PROJECT_PATH}/")
    # while True:
    #     num_pubs_initialized = len(list(publisher_initialized_file.glob("publisher-initialized-*")))
    #     if (num_pubs_initialized == num_pubs_started):
    #         break
    #     time.sleep(0.01)

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
        print("Starting SOME/IP manager apps per host ... ")
        managers_start = time.time()
        start_managers(net)
        time.sleep(0.1)
        managers_end = time.time()
        print("Done")
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
        print(f"Total initialization time: {subscribers_end-managers_start}s (managers: {managers_end-managers_start}s, publishers: {publishers_end-publishers_start}s, subscribers: {subscribers_end-subscribers_start}s)")
        evaluation_run_start = time.time()
        # Wait for statistics writer
        print("Waiting until all statistics are contributed ... ")
        try:
            return_code = statistics_writer_process.wait(timeout=10)
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
            current_run += 1
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
        net_name = get_net_name(services[service]["host"], True)
        service_id = services[service]["serviceId"]
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
        net_name = get_net_name(clients[client]["host"], False)
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
        service_host = get_net_name(services[str(service_id)]["host"], True)
        client_host = get_net_name(clients[client]["host"], False)

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

    print("Max services per host: ", max(services_per_host.values()))
    print("Max clients per host: ", max(clients_per_host.values()))

def parse_pub_and_sub_hosts(max_pubs_per_host: int, max_subs_per_host: int):
    global hosts
    global pub_apps
    global sub_apps
    hosts = dict()
    pub_apps = dict()
    sub_apps = dict()
    # first parse publisher apps and subscriber apps
    with open(f"{SCENARIO_PATH}/publishers.json", "r") as service_file:
        services = json.load(service_file)
    for service in services:
        host_name = services[service]["host"].lower() + "p"
        if host_name not in pub_apps:
            pub_apps[host_name] = []
        pub_apps[host_name].append(service)
    with open(f"{SCENARIO_PATH}/subscribers.json", "r") as sub_file:
        clients = json.load(sub_file)
    for client in clients:
        host_name = clients[client]["host"].lower() + "s"
        if host_name not in sub_apps:
            sub_apps[host_name] = []
        sub_apps[host_name].append(client)
    # then split them into hosts to honor max_pubs_per_host and max_subs_per_host
    for host_name in pub_apps:
        num_apps = len(pub_apps[host_name])
        hosts[host_name] = []
        num_hosts = (num_apps + max_pubs_per_host - 1) // max_pubs_per_host
        for i in range(num_hosts):
            new_host_name = f"{host_name}{i+1}"



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

    # parse pubs and subs json to identify hosts of apps
    parse_pub_and_sub_hosts(1000, 1000)
    pass

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    dns_host_name = DNS_HOST_NAME
    topo: car_topo = car_topo()
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
    print("Starting mininet network ... ")
    print("with hosts: ", [host.__str__() for host in net.hosts])
    print("number of apps per host: ", apps_per_host)
    # Evaluate
    if args.evaluate and args.runs:
        start_evaluation(total_evaluation_runs, evaluation_option, add_compile_definitions, net, dns_host_name)
    print("Stopping mininet network")
    net.stop()
    print("Done.")
else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-1sw-Nhosts.py --topo simple_topo
    topos = {'car_topo': (lambda: car_topo())}
