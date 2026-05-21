#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: topo_backbone_mpls.py
MÔ TẢ: Topology backbone Metro Ethernet MPLS
        Bao gồm: CE1/CE2/CE3 (Customer Edge)
                 PE1/PE2/PE3 (Provider Edge)
                 P1/P2/P3/P4 (Provider Core - MPLS region)
        KHÔNG chứa LAN nội bộ chi nhánh (xem các file topo_branch*.py)

SƠ ĐỒ (theo LOGIC.jpg):
         [CE1]          [CE2]          [CE3]
           |              |              |
          PE1            PE2            PE3
         / \            / \            / \
        P1  P3        P3  P4        P2  P4
         \  /  \    /  \ /  \    /  /\ 
          \/    P1-P2    \/    P2-P1  \/
          P1---P2  (full-mesh P1,P2,P3,P4)
          |\ / |
          P3--P4

Sơ đồ kết nối P (full-mesh):
  P1 -- P2, P1 -- P3, P1 -- P4
  P2 -- P3, P2 -- P4
  P3 -- P4

PE kết nối P:
  PE1 -- P1, PE1 -- P3
  PE2 -- P3, PE2 -- P4
  PE3 -- P2, PE3 -- P4

CE kết nối PE:
  CE1 -- PE1
  CE2 -- PE2
  CE3 -- PE3

CÁCH CHẠY:
  sudo python3 topo_backbone_mpls.py
  hoặc:
  sudo mn --custom topo_backbone_mpls.py --topo backbone_mpls --test pingall

ĐỊA CHỈ IP (Point-to-Point links, /30):
  CE1-PE1  : 10.0.1.0/30  (CE1=.1, PE1=.2)
  CE2-PE2  : 10.0.2.0/30  (CE2=.1, PE2=.2)
  CE3-PE3  : 10.0.3.0/30  (CE3=.1, PE3=.2)
  PE1-P1   : 10.10.11.0/30
  PE1-P3   : 10.10.13.0/30
  PE2-P3   : 10.10.23.0/30
  PE2-P4   : 10.10.24.0/30
  PE3-P2   : 10.10.32.0/30
  PE3-P4   : 10.10.34.0/30
  P1-P2    : 10.20.12.0/30
  P1-P3    : 10.20.13.0/30
  P1-P4    : 10.20.14.0/30
  P2-P3    : 10.20.23.0/30
  P2-P4    : 10.20.24.0/30
  P3-P4    : 10.20.34.0/30

Loopback (dùng cho OSPF Router-ID và LDP):
  CE1: 1.1.1.1/32  CE2: 1.1.1.2/32  CE3: 1.1.1.3/32
  PE1: 2.2.2.1/32  PE2: 2.2.2.2/32  PE3: 2.2.2.3/32
  P1:  3.3.3.1/32  P2:  3.3.3.2/32
  P3:  3.3.3.3/32  P4:  3.3.3.4/32
=============================================================================
"""

from mininet.net import Mininet
from mininet.node import Node
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo


# ===========================================================================
# LinuxRouter: Node hoạt động như router (bật IP forwarding)
# ===========================================================================
class LinuxRouter(Node):
    """Node Mininet hoạt động như router Linux (bật ip_forward)."""

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Bật IP forwarding
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


# ===========================================================================
# BackboneMplsTopo: Topo chỉ gồm CE/PE/P - KHÔNG có LAN chi nhánh
# ===========================================================================
class BackboneMplsTopo(Topo):
    """
    Topology backbone MPLS Metro Ethernet.
    Bao gồm CE1/CE2/CE3, PE1/PE2/PE3, P1-P4.
    Các router CE có 1 interface dự phòng (eth1) để sau này kết nối LAN.
    """

    def build(self, **opts):
        # -------------------------------------------------------------------
        # Tạo các router CE (Customer Edge) - đầu chi nhánh
        # -------------------------------------------------------------------
        ce1 = self.addNode('ce1', cls=LinuxRouter, ip=None)
        ce2 = self.addNode('ce2', cls=LinuxRouter, ip=None)
        ce3 = self.addNode('ce3', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # Tạo các router PE (Provider Edge) - biên ISP
        # -------------------------------------------------------------------
        pe1 = self.addNode('pe1', cls=LinuxRouter, ip=None)
        pe2 = self.addNode('pe2', cls=LinuxRouter, ip=None)
        pe3 = self.addNode('pe3', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # Tạo các router P (Provider Core) - lõi MPLS
        # -------------------------------------------------------------------
        p1 = self.addNode('p1', cls=LinuxRouter, ip=None)
        p2 = self.addNode('p2', cls=LinuxRouter, ip=None)
        p3 = self.addNode('p3', cls=LinuxRouter, ip=None)
        p4 = self.addNode('p4', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # Link CE -- PE (kết nối chi nhánh với ISP)
        # CE1-PE1: 10.0.1.0/30
        # CE2-PE2: 10.0.2.0/30
        # CE3-PE3: 10.0.3.0/30
        # -------------------------------------------------------------------
        self.addLink(ce1, pe1,
                     intfName1='ce1-eth0', params1={'ip': '10.0.1.1/30'},
                     intfName2='pe1-eth0', params2={'ip': '10.0.1.2/30'})

        self.addLink(ce2, pe2,
                     intfName1='ce2-eth0', params1={'ip': '10.0.2.1/30'},
                     intfName2='pe2-eth0', params2={'ip': '10.0.2.2/30'})

        self.addLink(ce3, pe3,
                     intfName1='ce3-eth0', params1={'ip': '10.0.3.1/30'},
                     intfName2='pe3-eth0', params2={'ip': '10.0.3.2/30'})

        # -------------------------------------------------------------------
        # Link PE -- P (kết nối PE với lõi MPLS theo LOGIC.jpg)
        # PE1 kết nối P1 và P3
        # PE2 kết nối P3 và P4
        # PE3 kết nối P2 và P4
        # -------------------------------------------------------------------
        # PE1 -- P1 : 10.10.11.0/30
        self.addLink(pe1, p1,
                     intfName1='pe1-eth1', params1={'ip': '10.10.11.1/30'},
                     intfName2='p1-eth0',  params2={'ip': '10.10.11.2/30'})

        # PE1 -- P3 : 10.10.13.0/30
        self.addLink(pe1, p3,
                     intfName1='pe1-eth2', params1={'ip': '10.10.13.1/30'},
                     intfName2='p3-eth0',  params2={'ip': '10.10.13.2/30'})

        # PE2 -- P3 : 10.10.23.0/30
        self.addLink(pe2, p3,
                     intfName1='pe2-eth1', params1={'ip': '10.10.23.1/30'},
                     intfName2='p3-eth1',  params2={'ip': '10.10.23.2/30'})

        # PE2 -- P4 : 10.10.24.0/30
        self.addLink(pe2, p4,
                     intfName1='pe2-eth2', params1={'ip': '10.10.24.1/30'},
                     intfName2='p4-eth0',  params2={'ip': '10.10.24.2/30'})

        # PE3 -- P2 : 10.10.32.0/30
        self.addLink(pe3, p2,
                     intfName1='pe3-eth1', params1={'ip': '10.10.32.1/30'},
                     intfName2='p2-eth0',  params2={'ip': '10.10.32.2/30'})

        # PE3 -- P4 : 10.10.34.0/30
        self.addLink(pe3, p4,
                     intfName1='pe3-eth2', params1={'ip': '10.10.34.1/30'},
                     intfName2='p4-eth1',  params2={'ip': '10.10.34.2/30'})

        # -------------------------------------------------------------------
        # Link P -- P (lõi MPLS, full-mesh giữa P1/P2/P3/P4 theo LOGIC.jpg)
        # -------------------------------------------------------------------
        # P1 -- P2 : 10.20.12.0/30
        self.addLink(p1, p2,
                     intfName1='p1-eth1', params1={'ip': '10.20.12.1/30'},
                     intfName2='p2-eth1', params2={'ip': '10.20.12.2/30'})

        # P1 -- P3 : 10.20.13.0/30
        self.addLink(p1, p3,
                     intfName1='p1-eth2', params1={'ip': '10.20.13.1/30'},
                     intfName2='p3-eth2', params2={'ip': '10.20.13.2/30'})

        # P1 -- P4 : 10.20.14.0/30
        self.addLink(p1, p4,
                     intfName1='p1-eth3', params1={'ip': '10.20.14.1/30'},
                     intfName2='p4-eth2', params2={'ip': '10.20.14.2/30'})

        # P2 -- P3 : 10.20.23.0/30
        self.addLink(p2, p3,
                     intfName1='p2-eth2', params1={'ip': '10.20.23.1/30'},
                     intfName2='p3-eth3', params2={'ip': '10.20.23.2/30'})

        # P2 -- P4 : 10.20.24.0/30
        self.addLink(p2, p4,
                     intfName1='p2-eth3', params1={'ip': '10.20.24.1/30'},
                     intfName2='p4-eth3', params2={'ip': '10.20.24.2/30'})

        # P3 -- P4 : 10.20.34.0/30
        self.addLink(p3, p4,
                     intfName1='p3-eth4', params1={'ip': '10.20.34.1/30'},
                     intfName2='p4-eth4', params2={'ip': '10.20.34.2/30'})


# ===========================================================================
# Hàm cấu hình IP và loopback cho tất cả router backbone
# ===========================================================================
def configure_backbone(net):
    """
    Cấu hình thêm sau khi Mininet đã khởi động:
    - Gán địa chỉ loopback (dùng cho OSPF Router-ID và LDP)
    - Bật ip_forward trên tất cả router
    - Cấu hình static route cơ bản (để test ping CE-CE qua backbone)
    """
    info('\n*** Cấu hình loopback cho các router backbone\n')

    # Loopback CE
    net['ce1'].cmd('ip addr add 1.1.1.1/32 dev lo')
    net['ce2'].cmd('ip addr add 1.1.1.2/32 dev lo')
    net['ce3'].cmd('ip addr add 1.1.1.3/32 dev lo')

    # Loopback PE
    net['pe1'].cmd('ip addr add 2.2.2.1/32 dev lo')
    net['pe2'].cmd('ip addr add 2.2.2.2/32 dev lo')
    net['pe3'].cmd('ip addr add 2.2.2.3/32 dev lo')

    # Loopback P
    net['p1'].cmd('ip addr add 3.3.3.1/32 dev lo')
    net['p2'].cmd('ip addr add 3.3.3.2/32 dev lo')
    net['p3'].cmd('ip addr add 3.3.3.3/32 dev lo')
    net['p4'].cmd('ip addr add 3.3.3.4/32 dev lo')

    info('*** Bật IP forwarding trên tất cả router\n')
    routers = ['ce1', 'ce2', 'ce3', 'pe1', 'pe2', 'pe3',
               'p1', 'p2', 'p3', 'p4']
    for r in routers:
        net[r].cmd('sysctl -w net.ipv4.ip_forward=1')

    info('*** Cấu hình static route cơ bản để test ping CE1-CE2-CE3\n')
    # CE1 -> CE2: CE1 -> PE1 -> P1/P3 -> PE2 -> CE2
    net['ce1'].cmd('ip route add 10.0.2.0/30 via 10.0.1.2')   # via PE1
    net['ce1'].cmd('ip route add 10.0.3.0/30 via 10.0.1.2')   # via PE1
    net['ce1'].cmd('ip route add 1.1.1.2/32  via 10.0.1.2')
    net['ce1'].cmd('ip route add 1.1.1.3/32  via 10.0.1.2')

    net['ce2'].cmd('ip route add 10.0.1.0/30 via 10.0.2.2')
    net['ce2'].cmd('ip route add 10.0.3.0/30 via 10.0.2.2')
    net['ce2'].cmd('ip route add 1.1.1.1/32  via 10.0.2.2')
    net['ce2'].cmd('ip route add 1.1.1.3/32  via 10.0.2.2')

    net['ce3'].cmd('ip route add 10.0.1.0/30 via 10.0.3.2')
    net['ce3'].cmd('ip route add 10.0.2.0/30 via 10.0.3.2')
    net['ce3'].cmd('ip route add 1.1.1.1/32  via 10.0.3.2')
    net['ce3'].cmd('ip route add 1.1.1.2/32  via 10.0.3.2')

    # PE1: biết đường đến CE2/CE3 và lõi P
    net['pe1'].cmd('ip route add 10.0.2.0/30 via 10.10.11.2')  # qua P1
    net['pe1'].cmd('ip route add 10.0.3.0/30 via 10.10.11.2')  # qua P1
    net['pe1'].cmd('ip route add 10.0.1.0/30 via 10.0.1.1')    # CE1 subnet
    net['pe1'].cmd('ip route add 2.2.2.2/32  via 10.10.11.2')
    net['pe1'].cmd('ip route add 2.2.2.3/32  via 10.10.11.2')

    # PE2: biết đường đến CE1/CE3 và lõi P
    net['pe2'].cmd('ip route add 10.0.1.0/30 via 10.10.23.2')  # qua P3
    net['pe2'].cmd('ip route add 10.0.3.0/30 via 10.10.24.2')  # qua P4
    net['pe2'].cmd('ip route add 10.0.2.0/30 via 10.0.2.1')
    net['pe2'].cmd('ip route add 2.2.2.1/32  via 10.10.23.2')
    net['pe2'].cmd('ip route add 2.2.2.3/32  via 10.10.24.2')

    # PE3: biết đường đến CE1/CE2 và lõi P
    net['pe3'].cmd('ip route add 10.0.1.0/30 via 10.10.32.2')  # qua P2
    net['pe3'].cmd('ip route add 10.0.2.0/30 via 10.10.34.2')  # qua P4
    net['pe3'].cmd('ip route add 10.0.3.0/30 via 10.0.3.1')
    net['pe3'].cmd('ip route add 2.2.2.1/32  via 10.10.32.2')
    net['pe3'].cmd('ip route add 2.2.2.2/32  via 10.10.34.2')

    # P1: route đến các subnet CE và PE khác
    net['p1'].cmd('ip route add 10.0.1.0/30 via 10.10.11.1')  # PE1
    net['p1'].cmd('ip route add 10.0.2.0/30 via 10.20.13.2')  # P3 -> PE2
    net['p1'].cmd('ip route add 10.0.3.0/30 via 10.20.12.2')  # P2 -> PE3

    # P2: route đến các subnet CE và PE khác
    net['p2'].cmd('ip route add 10.0.3.0/30 via 10.10.32.1')  # PE3
    net['p2'].cmd('ip route add 10.0.1.0/30 via 10.20.12.1')  # P1 -> PE1
    net['p2'].cmd('ip route add 10.0.2.0/30 via 10.20.24.2')  # P4 -> PE2

    # P3: route đến các subnet CE và PE khác
    net['p3'].cmd('ip route add 10.0.2.0/30 via 10.10.23.1')  # PE2
    net['p3'].cmd('ip route add 10.0.1.0/30 via 10.10.13.1')  # PE1
    net['p3'].cmd('ip route add 10.0.3.0/30 via 10.20.34.2')  # P4 -> PE3

    # P4: route đến các subnet CE và PE khác
    net['p4'].cmd('ip route add 10.0.2.0/30 via 10.10.24.1')  # PE2
    net['p4'].cmd('ip route add 10.0.3.0/30 via 10.10.34.1')  # PE3
    net['p4'].cmd('ip route add 10.0.1.0/30 via 10.20.14.1')  # P1 -> PE1

    info('*** Cấu hình backbone hoàn tất!\n')


# ===========================================================================
# Hàm in bảng tóm tắt địa chỉ IP
# ===========================================================================
def print_ip_table():
    """In bảng tóm tắt địa chỉ IP để dễ theo dõi."""
    info('\n' + '='*65 + '\n')
    info('  BẢNG TÓM TẮT ĐỊA CHỈ IP BACKBONE MPLS\n')
    info('='*65 + '\n')
    info('  Link             | Node 1 (IP)       | Node 2 (IP)\n')
    info('-'*65 + '\n')
    links = [
        ('CE1 -- PE1',  'CE1: 10.0.1.1/30',    'PE1: 10.0.1.2/30'),
        ('CE2 -- PE2',  'CE2: 10.0.2.1/30',    'PE2: 10.0.2.2/30'),
        ('CE3 -- PE3',  'CE3: 10.0.3.1/30',    'PE3: 10.0.3.2/30'),
        ('PE1 -- P1',   'PE1: 10.10.11.1/30',  'P1: 10.10.11.2/30'),
        ('PE1 -- P3',   'PE1: 10.10.13.1/30',  'P3: 10.10.13.2/30'),
        ('PE2 -- P3',   'PE2: 10.10.23.1/30',  'P3: 10.10.23.2/30'),
        ('PE2 -- P4',   'PE2: 10.10.24.1/30',  'P4: 10.10.24.2/30'),
        ('PE3 -- P2',   'PE3: 10.10.32.1/30',  'P2: 10.10.32.2/30'),
        ('PE3 -- P4',   'PE3: 10.10.34.1/30',  'P4: 10.10.34.2/30'),
        ('P1  -- P2',   'P1: 10.20.12.1/30',   'P2: 10.20.12.2/30'),
        ('P1  -- P3',   'P1: 10.20.13.1/30',   'P3: 10.20.13.2/30'),
        ('P1  -- P4',   'P1: 10.20.14.1/30',   'P4: 10.20.14.2/30'),
        ('P2  -- P3',   'P2: 10.20.23.1/30',   'P3: 10.20.23.2/30'),
        ('P2  -- P4',   'P2: 10.20.24.1/30',   'P4: 10.20.24.2/30'),
        ('P3  -- P4',   'P3: 10.20.34.1/30',   'P4: 10.20.34.2/30'),
    ]
    for link, n1, n2 in links:
        info(f'  {link:<16} | {n1:<17} | {n2}\n')
    info('='*65 + '\n')


# ===========================================================================
# Hàm main: khởi chạy topology backbone
# ===========================================================================
def run_backbone():
    """Khởi chạy topology backbone MPLS và mở CLI."""
    setLogLevel('info')

    info('*** Khởi tạo topology Backbone MPLS Metro Ethernet\n')
    topo = BackboneMplsTopo()

    # Tạo mạng Mininet với controller=None (không cần SDN controller)
    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()

    # Cấu hình thêm (loopback, static route cơ bản)
    configure_backbone(net)

    # In bảng IP
    print_ip_table()

    info('\n*** Kiểm tra ping nhanh CE1 -> CE2\n')
    ce1 = net['ce1']
    result = ce1.cmd('ping -c 3 10.0.2.1')  # CE2's interface
    info(result)

    info('\n*** Mở Mininet CLI (gõ "exit" để thoát)\n')
    CLI(net)

    net.stop()


# ===========================================================================
# Entry point
# ===========================================================================
# Khai báo topos để dùng với: sudo mn --custom topo_backbone_mpls.py
topos = {'backbone_mpls': BackboneMplsTopo}

if __name__ == '__main__':
    run_backbone()
