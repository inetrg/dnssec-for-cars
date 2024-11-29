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

def add_default_route(host):
    host_name = host.__str__()
    host.cmd(f'route add default gw 10.0.0.0 {host_name}-eth0')
    


if __name__ == '__main__':
    print("Building mininet network ... ")
    setLogLevel('info')
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

    print("Dumping network information ... ")
    dump_infos(net)
    print("Done")

    print("Testing network ... ")
    simple_tests(net)
    print("Done")

    print("Stopping mininet network")
    net.stop()
    print("Done.")
    
