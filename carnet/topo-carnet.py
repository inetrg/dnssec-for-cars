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
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.util import dumpNodeConnections
from mininet.util import dumpNetConnections
from pathlib import Path

PROJECT_PATH = "/home/vm-user/workspace/mininet-vsomeip-evaluation"
SCENARIO_PATH = f"{PROJECT_PATH}/carnet"

DNSNODENAME = 'dns'

# dummy to be replaced by car configuration file
SERVICE_ID = "4660"
INSTANCE_ID = "22136"
MAJOR_VERSION = "0"
MINOR_VERSION = "0"
PUBLISHER_PORT = "30509"
SUBSCRIBER_PORTS = "40000,40002"
PROTOCOL = "UDP"
PUBLISHER_HOST_NAME = 'zcRL'
SUBSCRIBER_HOST_NAMES = ['zcFR']

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
        sRL = self.addSwitch('sRL', dpid='0000000000000001')
        sFL = self.addSwitch('sFL', dpid='0000000000000002')
        sRR = self.addSwitch('sRR', dpid='0000000000000003')
        sFR = self.addSwitch('sFR', dpid='0000000000000004')
        sC = self.addSwitch('sC', dpid='0000000000000005')

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
        self.addLink(zcRl, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='zcRl-eth0', intfName2='sRL-eth1')
        self.addLink(zcFl, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='zcFl-eth0', intfName2='sFL-eth1')
        self.addLink(zcRr, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='zcRr-eth0', intfName2='sRR-eth1')
        self.addLink(zcFr, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='zcFr-eth0', intfName2='sFR-eth1')
        self.addLink(lRL, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='lRL-eth0', intfName2='sRL-eth2')
        self.addLink(lFL, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='lFL-eth0', intfName2='sFL-eth2')
        self.addLink(lRR, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='lRR-eth0', intfName2='sRR-eth2')
        self.addLink(lFR, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='lFR-eth0', intfName2='sFR-eth2')
        self.addLink(cR, sRL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='cR-eth0', intfName2='sRL-eth3')
        self.addLink(cF, sFR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='cF-eth0', intfName2='sFR-eth3')
        self.addLink(adas, sRR, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='adas-eth0', intfName2='sRR-eth3')
        self.addLink(inf, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='inf-eth0', intfName2='sFL-eth3')
        self.addLink(con, sFL, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='con-eth0', intfName2='sFL-eth4')
        self.addLink(sRL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='sRL-eth4', intfName2='sC-eth1')
        self.addLink(sFL, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='sFL-eth5', intfName2='sC-eth2')
        self.addLink(sRR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='sRR-eth4', intfName2='sC-eth3')
        self.addLink(sFR, sC, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='sFR-eth4', intfName2='sC-eth4')
        self.addLink(sC, dns, bw=1000, delay='0ms', loss=0, max_queue_size=99999, intfName1='sC-eth5', intfName2=DNSNODENAME+'-eth0')

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
    dns_host.cmd(f"sed -i -E 's/.* # mininet-host-ip/    ip-address: {dns_host_ip} # mininet-host-ip/' {PROJECT_PATH}/nsd/nsd.conf")
    dns_host.cmd(f"sed -i -E 's/ns\.service\.         IN    A    .*/ns.service.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/service.zone")
    dns_host.cmd(f"sed -i -E 's/ns\.client\.         IN    A    .*/ns.client.         IN    A    {dns_host_ip}/' {SCENARIO_PATH}/zones/client.zone")
    dns_host.cmd('nsd-control-setup')
    dns_host.cmd(f'nsd -c {PROJECT_PATH}/nsd/nsd.conf')

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

def create_host_config(host, host_config: str):
    host_name = host.__str__()
    host_id = "0x0001"
    unicast_ip = host.IP(intf=host.defaultIntf())
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['network'] = f'-{host_name}'
    config['unicast'] = unicast_ip
    config['logging']['level'] = 'fatal'
    config['logging']['console'] = 'true'
    config['logging']['file']['enable'] = 'true'
    config['logging']['file']['path'] = f'/var/log/{host_name}.log'
    config['applications'][0]['name'] = host_name
    config['applications'][0]['id'] = host_id
    config['routing'] = f'{host_name}'

    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def create_publisher_config(host):
    host_name = host.__str__()
    publisher_config_template = f"{SCENARIO_PATH}/vsomeip-configs/vsomeip-udp-mininet-publisher.json"
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"
    if not Path(host_config).is_file():
        host.cmd(f'cp {publisher_config_template} {host_config}')
        create_host_config(host, host_config)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_subscriber_config(host):
    host_name = host.__str__()
    subscriber_config_template = f"{SCENARIO_PATH}/vsomeip-configs/vsomeip-udp-mininet-subscriber.json"
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"
    if not Path(host_config).is_file():
        host.cmd(f'cp {subscriber_config_template} {host_config}')
        create_host_config(host, host_config)
    
    with open(host_config, 'r') as file:
        config = json.load(file)
    global STD_CONDITION
    if not STD_CONDITION:
        STD_CONDITION = ((config['logging']['console'] == 'true') or (config['logging']['file']['enable'] == 'true'))

def create_publisher_certificate(host):
    host_name = host.__str__()
    certificate = f'{SCENARIO_PATH}/certificates/{host_name}.service.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{host_name}.service.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host.cmd(f'{SCENARIO_PATH}/pub-svcb-and-tlsa-generator.bash {SERVICE_ID} {INSTANCE_ID} {MAJOR_VERSION} {MINOR_VERSION} {host_ip} {PUBLISHER_PORT} {PROTOCOL} {host_name}')
        host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def create_subscriber_certificate(host):
    host_name = host.__str__()
    certificate = f'{SCENARIO_PATH}/certificates/{host_name}.client.cert.pem'
    private_key = f'{SCENARIO_PATH}/certificates/{host_name}.client.key.pem'
    if not (Path(certificate).is_file() and Path(private_key).is_file()):
        host_ip = host.IP(intf=host.defaultIntf())
        host_id = str(2)
        host.cmd(f'{SCENARIO_PATH}/sub-svcb-and-tlsa-generator.bash {host_id} {SERVICE_ID} {INSTANCE_ID} {MAJOR_VERSION} {host_ip} {SUBSCRIBER_PORTS} {PROTOCOL} {host_name}')
        host_config = f"{SCENARIO_PATH}/vsomeip-configs/{host_name}.json"
        with open(host_config, 'r') as file:
            config = json.load(file)
        config['certificate-path'] = certificate
        config['private-key-path'] = private_key
        with open(host_config, 'w') as file:
            json.dump(config, file, indent=4)

def set_pub_certificate_path_at_sub(pub, sub):
    pub_name = pub.__str__()
    sub_name = sub.__str__()
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{sub_name}.json"
    with open(host_config, 'r') as file:
        config = json.load(file)
    config['service-certificate-path'] = f'{SCENARIO_PATH}/certificates/{pub_name}.service.cert.pem'
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def set_sub_certificate_path_at_pub(pub, sub):
    # todo make subs a list an accept multiple subscribers
    pub_name = pub.__str__()
    sub_name = sub.__str__()
    host_config = f"{SCENARIO_PATH}/vsomeip-configs/{pub_name}.json"
    with open(host_config, 'r') as file:
        config = json.load(file)
    client_certificate_paths = [f'{SCENARIO_PATH}/certificates/{sub_name}.client.cert.pem']
    config['host-certificates'] = client_certificate_paths
    with open(host_config, 'w') as file:
        json.dump(config, file, indent=4)

def start_someip_app(host, app_name):
    host_name = host.__str__()
    if STD_CONDITION:
        host.cmd(f"env VSOMEIP_CONFIGURATION={SCENARIO_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={host_name} {PROJECT_PATH}/vsomeip/build/examples/{app_name} &> /var/log/{host_name}.std &")
    else:
        host.cmd(f"env VSOMEIP_CONFIGURATION={SCENARIO_PATH}/vsomeip-configs/{host_name}.json  VSOMEIP_APPLICATION_NAME={host_name} {PROJECT_PATH}/vsomeip/build/examples/{app_name} &")

def start_someip_subscriber_app(host):
    start_someip_app(host, "my-subscriber")

def start_someip_publisher_app(host):
    start_someip_app(host, "my-publisher")

def stop_subscriber_app(host):
    host.cmd("pkill my-subscriber")

def stop_publisher_app(host):
    host.cmd("pkill my-publisher")

def start_evaluation(evaluation_option: str, add_compile_definitions: str, net: Mininet, dns_host_name: str):
    entire_evaluation_start = time.time()
    # start statistics writer
    print("Starting statistics-writer ...")
    # check if result dir exists and create it if not
    if not Path(f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series").is_dir():
        subprocess.run(f"mkdir -p {PROJECT_PATH}/statistic-results/{evaluation_option}-series", shell = True) 
    # statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(1), f"{PROJECT_PATH}/statistic-results/{evaluation_option}-series", evaluation_option])
    # statistics_writer_process = subprocess.Popen([f"{PROJECT_PATH}/vsomeip/build/implementation/statistics/statistics-writer-main", str(subscriber_count), f"{PROJECT_PATH}/statistic-results", evaluation_option])
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
    start_someip_subscriber_app(net[SUBSCRIBER_HOST_NAMES[0]])
    print("Done.")
    evaluation_run_start = time.time()
    # Wait for statistics writer
    # print("Waiting until all statistics are contributed ... ")
    # return_code = statistics_writer_process.wait(timeout=120)
    # wait 
    time.sleep(10)
    # if return_code == 0:
    #     print("Done.")
    evaluation_run_end = time.time()
    #     print(f"RUN ({evaluation_option}): ({evaluation_run_end-evaluation_run_start}s)")
    # else:
    #     print(f"statistics writer failed with return code {return_code}")
    #     print(f"evaluation run {evaluation_option} failed ")
    # stop someip publisher, subscribers and dns server
    print("Stopping SOME/IP apps and DNS server, and cleaning up ... ")
    for host in net.hosts:
        host_name: str = host.__str__()
        if host_name != dns_host_name:
            if host_name != PUBLISHER_HOST_NAME:
                stop_subscriber_app(host)
            else:
                stop_publisher_app(host)
    print("Done.")
    # Give an extra second for remaining transmissions
    time.sleep(1)
    entire_evaluation_end = time.time()
    print(f"TOTAL TIME FOR OPTION {evaluation_option}: {entire_evaluation_end - entire_evaluation_start}s")

def cleanup():
    subprocess.run(["pkill", "statistics-writ"])
    subprocess.run(f"rm -f {PROJECT_PATH}/vsomeip-zc*", shell=True)
    subprocess.run("rm -f /var/log/zc*.log", shell=True)
    subprocess.run(f"rm -f {PROJECT_PATH}/publisher-initialized", shell=True)
    subprocess.run(f"rm -f /var/log/zc*.std", shell=True)

if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description='Starts a car network topology in mininet and runs some connection tests')
        parser.add_argument('--iperf', type=bool, default=False, help='Run iperf tests')
        parser.add_argument('--debug', type=bool, default=False, help='Enable debug output, such as network dumps')
        parser.add_argument('--connectivity', type=bool, default=False, help='Test network connectivity')
        parser.add_argument('--clean', type=bool, default=False, help='Clean up all mininet interfaces from previous runs')
        parser.add_argument('--nobuild', type=bool, default=False, help='Do not rebuild vsomeip but use latest build')
        parser.add_argument('--noeval', type=bool, default=False, help='Do not run evaluation')
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

        if args.clean:
            print("Cleaning up mininet interfaces ... ")
            subprocess.run(['mn', '-c'])
            print("Done")
            print("Removing configs and certificates ... ")
            subprocess.run(f"rm -f {SCENARIO_PATH}/vsomeip-configs/h*.json", shell=True)
            subprocess.run(f"rm -f {SCENARIO_PATH}/certificates/*", shell=True)
            cleanup()
            reset_zone_files()
            print("Done.")

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
            print("Dumping switch information ... ")
            for switch in net.switches:
                dump_switch_information(net, switch.__str__())
            print("Done")

        if args.connectivity:
            print("Testing network connectivity ... ")
            test_connectivity(net)
            print("Done")

        if args.iperf:
            print( "Testing bandwidth between hosts ... " )
            test_bandwidth(net)
            print("Done")

        add_compile_definitions = compile_definitions[args.evaluate]
        if not args.nobuild:
            print("Building vsomeip ... ")
            subprocess.run(f"sed -i -E 's/add_compile_definitions.*/add_compile_definitions\({add_compile_definitions}\)/' {PROJECT_PATH}/vsomeip/CMakeLists.txt", shell=True)
            build_vsomeip()
            print("Done.")

        # create host configs and certificates
        print("Creating host configs and certificates ... ")
        create_publisher_config(net['zcRL'])
        create_publisher_certificate(net['zcRL'])
        create_subscriber_config(net['zcFR'])
        create_subscriber_certificate(net['zcFR'])
        set_pub_certificate_path_at_sub(pub=net['zcRL'], sub=net['zcFR']) # todo --> on per service basis instead of per host
        set_sub_certificate_path_at_pub(sub=net['zcFR'], pub=net['zcRL']) # todo --> on per service basis instead of per host
        if WITH_DNSSEC in add_compile_definitions:
            # for host in net.hosts:
                # set_dns_server_ip(host, net[DNSNODENAME])
            set_dns_server_ip(net[PUBLISHER_HOST_NAME], net[DNSNODENAME])
            set_dns_server_ip(net[SUBSCRIBER_HOST_NAMES[0]], net[DNSNODENAME])
        print("Done.")
        if WITH_DNSSEC in add_compile_definitions:
            print("Starting DNS server ... ")
            start_dns_server(net[DNSNODENAME])
            print("Done.")
            
        if not args.noeval:
            print("Starting vsomeip scenario ... ")
            # Evaluate
            start_evaluation(args.evaluate, add_compile_definitions, net, DNSNODENAME)
            print("Done.")
        
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

