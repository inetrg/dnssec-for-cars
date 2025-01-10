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

PUBLISHER_HOST_NAME = 'h1' # publisher host must be calles h1 for some reason... 
SUBSCRIBER_HOST_NAME = 'h2' # subscriber host must be calles h + number for some reason...
DNS_HOST_NAME = 'h3' # dns host must be calles h + something for some reason...
PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"

SERVICE_ID_INT = 2114
SERVICE_ID_HEX_STR = "0x{:04x}".format(SERVICE_ID_INT)
SERVICE_ID = str(int(SERVICE_ID_INT))
INSTANCE_ID_INT = 1
INSTANCE_ID_HEX_STR = "0x{:04x}".format(INSTANCE_ID_INT)
INSTANCE_ID = str(int(INSTANCE_ID_INT))
CLIENT_ID_INT = 301
CLIENT_ID_HEX_STR = "0x{:04x}".format(CLIENT_ID_INT)
CLIENT_ID = str(CLIENT_ID_INT)
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PUBLISHER_PORT = "30509"
SUBSCRIBER_PORTS = "40000,40002"
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
        # for i in range(n):
        #     host = self.addHost( 'h{}'.format(i + 1) )
        #     self.addLink( host, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999 )
        host1 = self.addHost( PUBLISHER_HOST_NAME )
        host2 = self.addHost( SUBSCRIBER_HOST_NAME )
        dns = self.addHost( DNS_HOST_NAME )
        self.addLink( host1, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999 )
        self.addLink( host2, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999 )
        self.addLink( dns, switch, bw=1000, delay='0ms', loss=0, max_queue_size=99999 )

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

def set_subscriber_count_to_record(host, subscriber_count_to_record: int):
    host_name = host.__str__()
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['subscriber-count-to-record'] = f'{subscriber_count_to_record}'
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

def create_subscriber_config(host):
    host_name = host.__str__()
    subscriber_config_template = f"{PROJECT_PATH}/vsomeip-configs/vsomeip-udp-mininet-subscriber.json"
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    if not Path(host_config).is_file():
        host.cmd(f'cp {subscriber_config_template} {host_config}')
        create_host_config(host, host_config, CLIENT_ID_HEX_STR)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['clients'][0]['service'] = SERVICE_ID_HEX_STR
    config['clients'][0]['instance'] = INSTANCE_ID_HEX_STR
    # config["applications"] = []
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_publisher_config(host):
    host_name = host.__str__()
    publisher_config_template = f"{PROJECT_PATH}/vsomeip-configs/vsomeip-udp-mininet-publisher.json"
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    if not Path(host_config).is_file():
        host.cmd(f'cp {publisher_config_template} {host_config}')
        create_host_config(host, host_config, SERVICE_ID_HEX_STR)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['services'][0]['service'] = SERVICE_ID_HEX_STR
    config['services'][0]['instance'] = INSTANCE_ID_HEX_STR
    # config["applications"] = []
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_host_config(host, host_config: str, app_id):
    host_name = host.__str__()
    unicast_ip = host.IP(intf=host.defaultIntf())
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['network'] = f'-{host_name}'
    config['unicast'] = unicast_ip
    config['logging']['level'] = 'fatal'
    config['logging']['console'] = 'false'
    config['logging']['file']['enable'] = 'false'
    config['logging']['file']['path'] = f'/var/log/{host_name}.log'
    config['applications'][0]['name'] = host_name
    config['applications'][0]['id'] = app_id
    config['routing'] = f'{host_name}'

    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_client_certificate(host):
    host_name = host.__str__()
    certificate = f'{PROJECT_PATH}/certificates/{host_name}.client.cert.pem'
    private_key = f'{PROJECT_PATH}/certificates/{host_name}.client.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{PROJECT_PATH}/client-svcb-and-tlsa-generator.bash {CLIENT_ID} {SERVICE_ID} {INSTANCE_ID} {MAJOR_VERSION} {host_ip} {SUBSCRIBER_PORTS} {PROTOCOL} {host_name}')
        host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def set_service_certificate_path(host):
    host_name = host.__str__()
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['service-certificate-path'] = f'{PROJECT_PATH}/certificates/{PUBLISHER_HOST_NAME}.service.cert.pem'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_service_certificate(host):
    host_name = host.__str__()
    certificate = f'{PROJECT_PATH}/certificates/{host_name}.service.cert.pem'
    private_key = f'{PROJECT_PATH}/certificates/{host_name}.service.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{PROJECT_PATH}/service-svcb-and-tlsa-generator.bash {SERVICE_ID} {INSTANCE_ID} {MAJOR_VERSION} {MINOR_VERSION} {host_ip} {PUBLISHER_PORT} {PROTOCOL} {host_name}')
        host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)


def set_client_certificate_paths(host, subscriber_count: int):
    host_name = host.__str__()
    host_config = f"{PROJECT_PATH}/vsomeip-configs/{host_name}.json"

    with open(host_config, 'r') as file:
        config = json.load(file)    
    client_certificate_paths = [ f'{PROJECT_PATH}/certificates/{SUBSCRIBER_HOST_NAME}.client.cert.pem' ]
    config['host-certificates'] = client_certificate_paths
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def reset_zone_files():
    subprocess.run(["su", "-", "vm-user", "-c", f"{PROJECT_PATH}/reset-zone-file.bash"])

def start_someip_subscriber_app(host):
    host_name = host.__str__()
    launch_cmd = f"env VSOMEIP_CONFIGURATION={PROJECT_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={host_name} {PROJECT_PATH}/vsomeip/build/examples/my-subscriber --serviceid {SERVICE_ID} --instanceid {INSTANCE_ID} &"
    if STD_CONDITION:
        host.cmd(f"{launch_cmd}> /var/log/{host_name}.std &")
    else:
        host.cmd(f"{launch_cmd}")

def start_someip_publisher_app(host):
    host_name = host.__str__()
    launch_cmd = f"env VSOMEIP_CONFIGURATION={PROJECT_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={host_name} {PROJECT_PATH}/vsomeip/build/examples/my-publisher --serviceid {SERVICE_ID} --instanceid {INSTANCE_ID} &"
    if STD_CONDITION:
        host.cmd(f"{launch_cmd}> /var/log/{host_name}.std &")
    else:
        host.cmd(f"{launch_cmd}")

def stop_subscriber_app(host):
    host.cmd("pkill my-subscriber")

def stop_publisher_app(host):
    host.cmd("pkill my-publisher")

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
    subprocess.run(f"rm -f {PROJECT_PATH}/vsomeip-h*", shell=True)
    subprocess.run("rm -f /var/log/h*.log", shell=True)
    subprocess.run(f"rm -f {PROJECT_PATH}/publisher-initialized", shell=True)
    subprocess.run(f"rm -f /var/log/h*.std", shell=True)

def start_evaluation(total_evaluation_runs: int, evaluation_option: str, subscriber_count: int, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    entire_evaluation_start = time.time()
    current_run = 1
    while current_run <= total_evaluation_runs:
        print(f"Starting {current_run}/{total_evaluation_runs} evaluation run {evaluation_option} ... ")
        # start statistics writer
        print("Starting statistics-writer ...")
        # check if result dir exists and create it if not
        if not Path(f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series").is_dir():
            subprocess.run(f"mkdir -p {PROJECT_PATH}/statistic-results/{evaluation_option}-series", shell = True) 
        statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series", evaluation_option])
        # statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results", evaluation_option])
        print("Done.")
        # start dns server
        if WITH_DNSSEC in add_compile_definitions:
            print("Starting DNS server ... ")
            start_dns_server(net[dns_host_name])
            print("Done.")
        # start someip publisher and subscribers
        print("Starting SOME/IP publisher ... ")
        start_someip_publisher_app(net[PUBLISHER_HOST_NAME])
        publisher_initialized_file = Path(f"{PROJECT_PATH}/publisher-initialized")
        while not publisher_initialized_file.is_file():
            time.sleep(1)
        # Give an extra second for startup
        time.sleep(1) 
        print("Done.")
        print("Starting SOME/IP subscribers ... ")
        for host in net.hosts:
            host_name = host.__str__()
            if host_name != PUBLISHER_HOST_NAME and host_name != dns_host_name:
                start_someip_subscriber_app(host)
        print("Done.")
        evaluation_run_start = time.time()
        # Wait for statistics writer
        print("Waiting until all statistics are contributed ... ")
        return_code = statistics_writer_process.wait(timeout=10)
        if return_code == 0:
            print("Done.")
            evaluation_run_end = time.time()
            print(f"RUN ({evaluation_option}-{subscriber_count}): {current_run}/{total_evaluation_runs} ({evaluation_run_end-evaluation_run_start}s)")
            current_run += 1
        else:
            print(f"statistics writer failed with return code {return_code}")
            print(f"{current_run}/{total_evaluation_runs} evaluation run {evaluation_option} failed and will be repeated")
        # stop someip publisher, subscribers and dns server
        print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
        for host in net.hosts:
            host_name: str = host.__str__()
            if host_name != dns_host_name:
                if host_name != PUBLISHER_HOST_NAME:
                    stop_subscriber_app(host)
                else:
                    stop_publisher_app(host)
        if WITH_DNSSEC in add_compile_definitions:
            stop_dns_server(net[dns_host_name])
        cleanup()
        print("Done.")
        # Give an extra second for remaining transmissions
        time.sleep(1)
    entire_evaluation_end = time.time()
    print(f"TOTAL TIME FOR OPTION {evaluation_option} in {total_evaluation_runs} RUN/S: {entire_evaluation_end - entire_evaluation_start}s")

def start_debug(evaluation_option: str, subscriber_count: int, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    # start statistics writer
    print("Starting statistics-writer ...")
    subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results/debug", evaluation_option])
    print("Done.")
    # start dns server
    if WITH_DNSSEC in add_compile_definitions:
        print("Starting DNS server ... ")
        start_dns_server(net[dns_host_name])
        print("Done.")
    CLI(net)
    # stop someip publisher, subscribers and dns server
    print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
    for host in net.hosts:
        host_name: str = host.__str__()
        if host_name != dns_host_name:
            if host_name != PUBLISHER_HOST_NAME:
                stop_subscriber_app(host)
            else:
                stop_publisher_app(host)
    if WITH_DNSSEC in add_compile_definitions:
        stop_dns_server(net[dns_host_name])
    cleanup()
    print("Done.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Starts vsomeip w/ or w/o security mechanisms and collects timestamps of handshake events')
    parser.add_argument('--hosts', type=int, metavar='N', required=True, choices=range(2,0xffff+1), help='Specify the number of hosts. (between 2 (inclusive) and 65536 (exclusive))')
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
    host_count: int = args.hosts
    subscriber_count: int = host_count-1
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
        dns_host_name = DNS_HOST_NAME
    else:
        topo: simple_topo = simple_topo(n = host_count)
        dns_host_name: str = ""
    net: Mininet = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()
    for switch in net.switches:
        make_switch_traditional(net, switch.__str__())
    print("Done.")
    # build vsomeip
    print("Building vsomeip ... ")
    # set compile definitions
    subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
    build_vsomeip()
    print("Done.")
    # create host configs and certificates
    print("Creating host configs and certificates ... ")
    create_publisher_config(net[PUBLISHER_HOST_NAME])
    create_service_certificate(net[PUBLISHER_HOST_NAME])
    set_client_certificate_paths(net[PUBLISHER_HOST_NAME], subscriber_count)
    for host in net.hosts:
        add_default_route(host)
        host_name = host.__str__()
        if host_name != PUBLISHER_HOST_NAME and host_name != dns_host_name:
            create_subscriber_config(host)
            create_client_certificate(host)
            set_service_certificate_path(host)
        if len(dns_host_name) and host_name != dns_host_name:
            set_dns_server_ip(host, net[dns_host_name])
        if host_name != dns_host_name:
            set_subscriber_count_to_record(host, subscriber_count)
        if STD_CONDITION:
            subprocess.run(f'touch /var/log/{host_name}.std', shell=True)
    print("Done.")
    # Evaluate
    if args.evaluate and args.runs:
        start_evaluation(total_evaluation_runs, evaluation_option, subscriber_count, add_compile_definitions, net, dns_host_name)
    else:
        start_debug(evaluation_option, subscriber_count, add_compile_definitions, net, dns_host_name)
    print("Stopping mininet network")
    net.stop()
    print("Done.")
else:
    # Command to start CLI w/ topo only: sudo -E mn --mac --controller none --custom ~/vscode-workspaces/topo-1sw-Nhosts.py --topo simple_topo
    topos = {'simple_topo': (lambda: simple_topo())}
