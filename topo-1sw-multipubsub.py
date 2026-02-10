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
from mininet.node import OVSBridge
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections
from mininet.util import dumpNetConnections
from pathlib import Path
from subprocess import TimeoutExpired
from math import ceil

PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"

INSTANCE_ID_INT = 1
INSTANCE_ID_HEX_STR = "0x{:04x}".format(INSTANCE_ID_INT)
INSTANCE_ID = str(int(INSTANCE_ID_INT))
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PUBLISHER_PORT = 2000
PUBLISHER_MCAST_PORT = 7000
SUBSCRIBER_PORT = 5000
PROTOCOL = "UDP"
# compile definitions
WITH_SERVICE_AUTHENTICATION = 'WITH_SERVICE_AUTHENTICATION'
WITH_CLIENT_AUTHENTICATION = 'WITH_CLIENT_AUTHENTICATION'
NO_SOMEIP_SD = 'NO_SOMEIP_SD'
WITH_DNSSEC = 'WITH_DNSSEC'
WITH_DANE = 'WITH_DANE'
WITH_ENCRYPTION = 'WITH_ENCRYPTION'

STD_CONDITION = False

class simple_topo( Topo ):
    "Simple topology example."

    def build( self: Topo, n: int = 2 ):
        "Create custom topo."

        # Add switch
        switch = self.addSwitch( 's1' )

        # Add hosts with links connecting to switch
        for i in range(n):
            host = self.addHost( 'h{}'.format(i + 1) )
            self.addLink( host, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999 )

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

def set_dns_server_ip(host, dns_host):
    host_name = host.__str__()
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
    ip_bytes = dns_host_ip.split(".")
    ip_bytes_in_hex = [ "{:02x}".format(int(x)) for x in ip_bytes ]
    dns_host_ip_in_hex = f"0x{''.join(ip_bytes_in_hex)}"
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['dns-server-ip'] = f'{dns_host_ip_in_hex}'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def start_dns_server(dns_host):
    dns_host_ip = dns_host.IP(intf=dns_host.defaultIntf())
    dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {PROJECT_PATH}/nsd/nsd.conf")
    dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {PROJECT_PATH}/zones/service.zone")
    dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {PROJECT_PATH}/zones/client.zone")
    dns_host.cmd('nsd-control-setup')
    dns_host.cmd(f'nsd -c {PROJECT_PATH}/nsd/nsd.conf')

def stop_dns_server(dns_host):
    dns_host.cmd('nsd-control stop')
    dns_host.cmd('pkill nsd')

def create_subscriber_config(host, total_pubs, total_subs, pub_id, sub_id):
    host_name = host.__str__()
    subscriber_config_template = f"{PROJECT_PATH}/vsomeip-configs/vsomeip-udp-mininet-subscriber.json"
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    client_id = get_subscriber_id(total_pubs, total_subs, pub_id, sub_id)
    app_name = f"sub-{client_id}"
    app_id = f"0x{int(client_id):04x}"
    if not Path(host_config).is_file():
        host.cmd(f'cp {subscriber_config_template} {host_config}')
        create_host_config(host, host_config, app_id, app_name)
    else:
        # add another app id to the existing config
        with open(host_config, 'r') as file:
            config = json.load(file)
        app_exists = False
        new_app_data = {"name": app_name, "id": app_id}
        for app in config['applications']:
            if app['name'] == app_name:
                app_exists = True
                app = new_app_data
                break
        if not app_exists:
            config['applications'].append(new_app_data)
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    client_exists = False
    new_client_config = {
            'service': "0x{:04x}".format(pub_id),
            'instance': INSTANCE_ID_HEX_STR,
            'unreliable': [str(SUBSCRIBER_PORT + client_id)],
            'client-id': f"0x{int(client_id):04x}"
        }
    if not config['clients']:
        config['clients'] = []
    else:
        for client in config['clients']:
            if client['service'] == f"0x{pub_id:04x}" and client['client-id'] == f"0x{int(client_id):04x}":
                client_exists = True
                client = new_client_config
                break
    if not client_exists:
        config['clients'].append(new_client_config)
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_publisher_config(host, pub_id: int):
    host_name = host.__str__()
    service_id = pub_id
    service_id_hex = "0x{:04x}".format(service_id)
    app_name = "pub-" + str(service_id)
    app_id = service_id_hex
    publisher_config_template = f"{PROJECT_PATH}/vsomeip-configs/vsomeip-udp-mininet-publisher.json"
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    if not Path(host_config).is_file():
        host.cmd(f'cp {publisher_config_template} {host_config}')
        create_host_config(host, host_config, app_id, app_name)
    else:
        # add another app id to the existing config
        with open(host_config, 'r') as file:
            config = json.load(file)
        app_exists = False
        new_app_data = {"name": app_name, "id": app_id}
        for app in config['applications']:
            if app['name'] == app_name:
                app_exists = True
                app = new_app_data
                break
        if not app_exists:
            config['applications'].append(new_app_data)
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    service_exists = False
    new_service_config = {
        'service': service_id_hex,
        'instance': INSTANCE_ID_HEX_STR,
        'unreliable': str(PUBLISHER_PORT+service_id),
        'events': [{"events": f"0x{int(10000+service_id):04x}", "is_field" : "true", "update-cycle" : 0},
        {"events": f"0x{int(20000+service_id):04x}", "is_field" : "true"}]
    }
    lowerTwoDigetsServiceId = service_id % 256
    upperTwoDigetsServiceId = service_id // 256
    mcast_ip = "224.225." + str(upperTwoDigetsServiceId) + "." + str(lowerTwoDigetsServiceId)
    new_service_config['eventgroups'] = [
        {"eventgroup" : f"0x{int(30000+service_id):04x}", "events" : [ f"0x{int(10000+service_id):04x}", f"0x{int(20000+service_id):04x}" ], "multicast" : { "address" : mcast_ip, "port" :  str(PUBLISHER_MCAST_PORT+service_id) } }
    ]
    if not config['services']:
        config['services'] = []
    else:
        for service in config['services']:
            if service['service'] == service_id_hex:
                service_exists = True
                service = new_service_config
                break
    if not service_exists:
        config['services'].append(new_service_config)
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_host_config(host, host_config: str, app_id, app_name: str):
    host_name = host.__str__()
    unicast_ip = host.IP(intf=host.defaultIntf())
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['network'] = f'-{host_name}'
    config['unicast'] = unicast_ip
    config['logging']['level'] = 'trace'
    config['logging']['console'] = 'false'
    config['logging']['file']['enable'] = 'true'
    config['logging']['file']['path'] = f'/var/log/multihost/{host_name}.log'
    config['applications'][0]['name'] = app_name
    config['applications'][0]['id'] = app_id
    config['clients'] = []
    config['services'] = []
    config['routing'] = f'{app_name}'

    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_client_certificate(host, total_pubs, total_subs, pub_id, sub_id):
    host_name = host.__str__()
    client_id = get_subscriber_id(total_pubs, total_subs, pub_id, sub_id)
    certificate = f'{PROJECT_PATH}/certificates/{client_id}.client.cert.pem'
    private_key = f'{PROJECT_PATH}/certificates/{client_id}.client.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{PROJECT_PATH}/client-svcb-and-tlsa-generator.bash {client_id} {pub_id} {INSTANCE_ID} {MAJOR_VERSION} {host_ip} {SUBSCRIBER_PORT + client_id} {PROTOCOL} {client_id}')
        host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        # find the correct client id
        for client in config['clients']:
            if client['client-id'] == f"0x{client_id:04x}" and client['service'] == f"0x{pub_id:04x}":
                client['private-key-path'] = private_key
                break
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def create_service_certificate(host, pub_id: int):
    host_name = host.__str__()
    certificate = f'{PROJECT_PATH}/certificates/{pub_id}.service.cert.pem'
    private_key = f'{PROJECT_PATH}/certificates/{pub_id}.service.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{PROJECT_PATH}/service-svcb-and-tlsa-generator.bash {pub_id} {INSTANCE_ID} {MAJOR_VERSION} {MINOR_VERSION} {host_ip} {PUBLISHER_PORT+pub_id} {PROTOCOL} {pub_id}')
        host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        # find the correct service id
        for service in config['services']:
            if service['service'] == f"0x{pub_id:04x}":
                service['private-key-path'] = private_key
                break
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def get_subscriber_id(total_pubs, total_subs, pub_id, sub_id):
    return total_pubs + (pub_id-1)*total_subs + sub_id

def get_publisher_host_id(pub_id, pubs_per_host):
    return ((pub_id-1) // pubs_per_host) + 1

def create_publishers(net: Mininet, pub_count: int, dns_host_name: str, pubs_per_host: int):
    # publishers are the first nodes from h1 to hpub_count
    for i in range(1, pub_count+1):
        host_id = get_publisher_host_id(i, pubs_per_host)
        print(f"Creating publisher {i}/{pub_count} on host {net['h'+str(host_id)]}")
        create_publisher_config(net['h'+str(host_id)], i)
        create_service_certificate(net['h'+str(host_id)], i)
        if (dns_host_name != ""):
            set_dns_server_ip(net['h'+str(host_id)], net[dns_host_name])

def get_subscriber_host_id(pub_count, sub_count, pub_id, sub_id, pubs_per_host, one_sub_host):
    max_pub_host_id = get_publisher_host_id(pub_count, pubs_per_host)
    if one_sub_host:
        return max_pub_host_id + sub_id
    return max_pub_host_id + (pub_id-1)*sub_count + sub_id


def create_subscribers(net: Mininet, sub_count: int, pub_count: int, dns_host_name: str, one_sub_host: bool = False, pubs_per_host: int = 1):
    # subscribers are the have the offset of pub_count from hpub_count+1 to hpub_count+sub_count*pub_count
    for i in range(1, pub_count+1):
        for j in range(1, sub_count+1):
            # find the unique subscriber id (publishers take the ids from 1 to pub_count)
            sub_host = net['h' + str(get_subscriber_host_id(pub_count, sub_count, i, j, pubs_per_host, one_sub_host))]
            print(f"Creating subscriber {i}/{pub_count} - {j}/{sub_count} on host {sub_host}")
            create_subscriber_config(sub_host, pub_count, sub_count, i, j)
            create_client_certificate(sub_host, pub_count, sub_count, i, j)
            if (dns_host_name != ""):
                set_dns_server_ip(sub_host, net[dns_host_name])

def reference_certificates(net: Mininet, pub_count: int, sub_count: int, one_sub_host: bool, pubs_per_host: int):
    for i in range(1, pub_count+1):
        host_id = get_publisher_host_id(i, pubs_per_host)
        publisher_id = i
        # set all subscriber certs for this publisher
        pub_host_name = 'h'+str(host_id)
        pub_config = f"{PROJECT_PATH}/vsomeip-configs/{pub_host_name}.json"
        client_certificate_paths = []
        for j in range(1, sub_count+1):
            subscriber_id = get_subscriber_id(pub_count, sub_count, i, j)
            client_certificate_paths.append({"id": f"0x{subscriber_id:04x}", "certificate-path": f'{PROJECT_PATH}/certificates/{subscriber_id}.client.cert.pem'})
            # set the publisher cert at the subscriber
            sub_host_name = 'h' + str(get_subscriber_host_id(pub_count, sub_count, i, j, pubs_per_host, one_sub_host))
            sub_config = f"{PROJECT_PATH}/vsomeip-configs/{sub_host_name}.json"
            with open(sub_config, 'r') as file:
                config = json.load(file)
            # find the correct client id
            for client in config['clients']:
                if client['service'] == f"0x{publisher_id:04x}":
                    client['service-certificate-path'] = f'{PROJECT_PATH}/certificates/{publisher_id}.service.cert.pem'
                    break
            with open(sub_config, 'w') as file:
                json.dump(config, file, indent=4)
        with open(pub_config, 'r') as file:
            config = json.load(file)    
        # find the correct service 
        for service in config['services']:
            if service['service'] == f"0x{publisher_id:04x}":
                service['client-certificates'] = client_certificate_paths
                break
        with open(pub_config, 'w') as file:
            json.dump(config, file, indent=4)        

def reset_zone_files():
    subprocess.run(["su", "-", "vm-user", "-c", f"{PROJECT_PATH}/reset-zone-file.bash"])

def start_someip_subscriber_app(host, pub_id: int, app_name: str):
    host_name = host.__str__()
    launch_cmd = f"env VSOMEIP_CONFIGURATION={PROJECT_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-subscriber --serviceid {pub_id} --instanceid {INSTANCE_ID} --eventgroupid {30000+pub_id} --eventid {10000+pub_id}"
    if STD_CONDITION:
        host.cmd(f"{launch_cmd}> /var/log/{host_name}.std &")
    else:
        host.cmd(f"{launch_cmd} &")

def start_subscribers(net: Mininet, pub_count: int, sub_count: int, one_sub_host: bool, pubs_per_host: int):
    initial_host_started = False
    for i in range(1, pub_count+1):
        for j in range(1, sub_count+1):
            client_id = get_subscriber_id(pub_count, sub_count, i, j)
            sub_host = net['h'+str(get_subscriber_host_id(pub_count, sub_count, i, j, pubs_per_host, one_sub_host))]
            app_name = f"sub-{client_id}"
            start_someip_subscriber_app(sub_host, i, app_name)
        if one_sub_host and not initial_host_started:
            print("First subscribers started on hosts, waiting")
            time.sleep(0.001)
            initial_host_started = True

def start_someip_publisher_app(host, pub_id: int):
    host_name = host.__str__()
    app_name = f"pub-{pub_id}"
    launch_cmd = f"env VSOMEIP_CONFIGURATION={PROJECT_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={app_name} {PROJECT_PATH}/vsomeip/build/examples/my-publisher --serviceid {pub_id} --instanceid {INSTANCE_ID} --eventgroupid {30000+pub_id} --eventid {10000+pub_id}"
    if STD_CONDITION:
        host.cmd(f"{launch_cmd}> /var/log/{host_name}.std &")
    else:
        host.cmd(f"{launch_cmd} &")

def start_publishers(net: Mininet, pub_count: int, pubs_per_host: int):
    for i in range(1, pub_count+1):
        host_id = get_publisher_host_id(i, pubs_per_host)
        start_someip_publisher_app(net['h'+str(host_id)], i)
        # wait if this is the first publisher on a new host
        if i % pubs_per_host == 1:
            print("First publisher " + str(i) + " on host " + str(host_id))
            time.sleep(0.001)

def stop_subscriber_app(host):
    host.cmd("pkill my-subscriber")

def stop_publisher_app(host):
    host.cmd("pkill my-publisher")

def stop_subscribers(net: Mininet, pub_count: int, sub_count: int, one_sub_host: bool, pubs_per_host: int):
    for i in range(1, pub_count+1):
        for j in range(1, sub_count+1):
            sub_host = net['h'+str(get_subscriber_host_id(pub_count, sub_count, i, j, pubs_per_host, one_sub_host))]
            stop_subscriber_app(sub_host)
        if one_sub_host:
            break

def stop_publishers(net: Mininet, pub_count: int, pubs_per_host: int):
    for i in range(1, pub_count+1):
        host_id = get_publisher_host_id(i, pubs_per_host)
        stop_publisher_app(net['h'+str(host_id)])

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
    subprocess.run("rm -f /var/log/multihost/h*.log", shell=True)
    subprocess.run(f"rm -f {PROJECT_PATH}/publisher-initialized*", shell=True)
    subprocess.run(f"rm -f /var/log/h*.std", shell=True)

def start_evaluation(total_evaluation_runs: int, evaluation_option: str, add_compile_definitions: str, net: Mininet, dns_host_name: str, pub_count: int, sub_count: int, one_sub_host: bool = False, pubs_per_host: int = 1):
    entire_evaluation_start = time.time()
    current_run = 1
    while current_run <= total_evaluation_runs:
        print(f"Starting {current_run}/{total_evaluation_runs} evaluation run {evaluation_option} ... ")
        # start statistics writer
        print("Starting statistics-writer ...")
        # check if result dir exists and create it if not
        services = "[" + ",".join(str(i) for i in range(1, pub_count+1)) + "]"
        member_counts = "[" + ",".join(str(sub_count) for i in range(1, pub_count+1)) + "]"
        print(f"services: {services}")
        print(f"member_counts: {member_counts}")
        if not Path(f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series").is_dir():
            subprocess.run(f"mkdir -p {PROJECT_PATH}/statistic-results/{evaluation_option}-series", shell = True) 
        statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", services, member_counts, f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series", evaluation_option+"-"+str(pub_count)+"-"+str(sub_count)])
        # statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results", evaluation_option])
        print("Done.")
        # start dns server
        if WITH_DNSSEC in add_compile_definitions:
            print("Starting DNS server ... ")
            start_dns_server(net[dns_host_name])
            print("Done.")
        time.sleep(0.1)
        start_apps_begin = time.time()
        # start someip publisher and subscribers
        print("Starting SOME/IP subscribers ... ")
        start_subscribers(net, pub_count, sub_count, one_sub_host, pubs_per_host)
        start_subs_end = time.time()
        print("Done. Took {}s".format(start_subs_end-start_apps_begin))
        # time.sleep(0.001)
        print("Starting SOME/IP publishers ... ")
        start_publishers(net, pub_count, pubs_per_host)
        start_pubs_end = time.time()
        print("Done. Took {}s, totel app start time: {}s".format(start_pubs_end-start_subs_end, start_pubs_end-start_apps_begin))
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
            print(f"RUN ({evaluation_option}-{pub_count}-{sub_count}): {current_run}/{total_evaluation_runs} ({evaluation_run_end-evaluation_run_start}s)")
            current_run += 1
        else:
            print(f"statistics writer failed with return code {return_code}")
            print(f"{current_run}/{total_evaluation_runs} evaluation run {evaluation_option} failed and will be repeated")
            current_run += 1
        # stop someip publisher, subscribers and dns server
        print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
        stop_subscribers(net, pub_count, sub_count, one_sub_host, pubs_per_host)
        stop_publishers(net, pub_count, pubs_per_host)
        if WITH_DNSSEC in add_compile_definitions:
            stop_dns_server(net[dns_host_name])
        # cleanup()
        print("Done.")
        # Give an extra second for remaining transmissions
        time.sleep(1)
    entire_evaluation_end = time.time()
    print(f"TOTAL TIME FOR OPTION {evaluation_option} in {total_evaluation_runs} RUN/S: {entire_evaluation_end - entire_evaluation_start}s")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Starts vsomeip w/ or w/o security mechanisms and collects timestamps of handshake events')
    parser.add_argument('--pubs', type=int, metavar='N', required=True, choices=range(1,0xffff+1), help='Specify the number of publishers. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--onesubhost', dest='onesubhost', action='store_true', help='Use only one subscriber host for all subscribers')
    parser.add_argument('--subsperpub', type=int, metavar='N', required=False, default=1, choices=range(1,0xffff+1), help='Specify the number of subscribers per publisher. (between 1 (inclusive) and 65536 (exclusive))')
    parser.add_argument('--pubsperhost', type=int, metavar='N', required=False, default=1, choices=range(1,0xffff+1), help='Specify the number of publishers to be placed on one host. (between 1 (inclusive) and 65536 (exclusive))')
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
    pub_count = args.pubs
    sub_count = args.subsperpub
    host_count: int = get_publisher_host_id(pub_count, args.pubsperhost)
    if args.onesubhost:
        host_count += sub_count
    else:
        host_count += pub_count * sub_count
    print("Host count: ", host_count)
    subscriber_count: int = sub_count * pub_count
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
    print("Done")

    # remove configs and certificates for clean start
    if args.clean_start:
        print("Removing configs and certificates ... ")
        subprocess.run(f"rm -f {PROJECT_PATH}/vsomeip-configs/h*.json", shell=True)
        subprocess.run(f"rm -f {PROJECT_PATH}/certificates/*", shell=True)
        reset_zone_files()
        print("Done.")

    # build mininet network
    print("Building mininet network ... ")
    setLogLevel('critical')
    if WITH_DNSSEC in add_compile_definitions:
        topo: simple_topo = simple_topo(n = host_count+1)
        dns_host_name = "h"+str(host_count+1)
    else:
        topo: simple_topo = simple_topo(n = host_count)
        dns_host_name: str = ""
    net: Mininet = Mininet(topo=topo, controller=None, switch=OVSBridge, link=TCLink)
    net.start()
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
    print("Creating host configs and certificates ... ")
    create_publishers(net, pub_count, dns_host_name, args.pubsperhost)
    create_subscribers(net, sub_count, pub_count, dns_host_name, args.onesubhost, args.pubsperhost)
    reference_certificates(net, pub_count, sub_count, args.onesubhost, args.pubsperhost)
    print("Done.")
    # Evaluate
    if args.evaluate and args.runs:
        start_evaluation(total_evaluation_runs, evaluation_option, add_compile_definitions, net, dns_host_name, pub_count, sub_count, args.onesubhost, args.pubsperhost)
    print("Stopping mininet network")
    net.stop()
    print("Done.")
else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-1sw-Nhosts.py --topo simple_topo
    topos = {'simple_topo': (lambda: simple_topo())}
