#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: topo_branch1_flat.py
MÔ TẢ: Topology LAN nội bộ Chi nhánh 1 – Mạng phẳng (Flat Network)

Kiến trúc:
  ┌─────────────────────────────────────────┐
  │            CHI NHÁNH 1 – FLAT            │
  │                                          │
  │  [host1] [host2] [host3] [host4]         │
  │     |       |       |       |            │
  │     └───────┴──[s_acc1]────┘            │
  │                    |                     │
  │                 [ce1_lan]  ←── kết nối   │
  │                    |           lên CE1   │
  └─────────────────── | ───────────────────┘
                        ↓
                  (backbone CE1)

Subnet LAN chi nhánh 1: 10.1.0.0/24
  host1   : 10.1.0.101/24
  host2   : 10.1.0.102/24
  host3   : 10.1.0.103/24
  host4   : 10.1.0.104/24
  ce1_lan : 10.1.0.1/24  (gateway LAN)
  ce1_lan : 10.0.1.1/30  (uplink về CE1 backbone) [khi tích hợp]

CÁCH CHẠY ĐỘC LẬP:
  sudo mn --custom topo_branch1_flat.py --topo branch1_flat --test ping
  hoặc:
  sudo python3 topo_branch1_flat.py
=============================================================================
"""

from mininet.net import Mininet
from mininet.node import Node, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo


# ===========================================================================
# LinuxRouter: Node hoạt động như router (bật IP forwarding)
# ===========================================================================
class LinuxRouter(Node):
    """Node Mininet hoạt động như router Linux."""

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


# ===========================================================================
# Branch1FlatTopo: Mạng phẳng chi nhánh 1
# ===========================================================================
class Branch1FlatTopo(Topo):
    """
    Topology mạng phẳng (Flat Network) – Chi nhánh 1.
    
    Thành phần:
      - 1 switch Access: s_acc1
      - 4 host: host1, host2, host3, host4
      - 1 router: ce1_lan (gateway LAN và uplink về backbone CE1)
    
    Tất cả host nằm trong subnet 10.1.0.0/24 (Layer 2 phẳng).
    """

    def build(self, **opts):
        # -------------------------------------------------------------------
        # Router CE1 LAN: gateway nội bộ, đồng thời là uplink về backbone
        # Interface eth0: phía LAN (10.1.0.1/24)
        # Interface eth1: phía backbone CE1 (10.0.1.1/30) – dùng khi tích hợp
        # -------------------------------------------------------------------
        ce1_lan = self.addNode('ce1_lan', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # Switch Access (Layer 2) – kết nối tất cả host trong cùng broadcast domain
        # -------------------------------------------------------------------
        s_acc1 = self.addSwitch('s_acc1', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # 4 Host trong mạng phẳng, subnet 10.1.0.0/24
        # defaultRoute trỏ về ce1_lan (10.1.0.1) làm gateway
        # -------------------------------------------------------------------
        host1 = self.addHost('host1',
                             ip='10.1.0.101/24',
                             defaultRoute='via 10.1.0.1')
        host2 = self.addHost('host2',
                             ip='10.1.0.102/24',
                             defaultRoute='via 10.1.0.1')
        host3 = self.addHost('host3',
                             ip='10.1.0.103/24',
                             defaultRoute='via 10.1.0.1')
        host4 = self.addHost('host4',
                             ip='10.1.0.104/24',
                             defaultRoute='via 10.1.0.1')

        # -------------------------------------------------------------------
        # Kết nối: host ↔ switch Access
        # -------------------------------------------------------------------
        self.addLink(host1, s_acc1, intfName1='host1-eth0', intfName2='s_acc1-eth1')
        self.addLink(host2, s_acc1, intfName1='host2-eth0', intfName2='s_acc1-eth2')
        self.addLink(host3, s_acc1, intfName1='host3-eth0', intfName2='s_acc1-eth3')
        self.addLink(host4, s_acc1, intfName1='host4-eth0', intfName2='s_acc1-eth4')

        # -------------------------------------------------------------------
        # Kết nối: switch Access ↔ ce1_lan (uplink từ LAN lên router)
        # ce1_lan-eth0: IP LAN 10.1.0.1/24
        # -------------------------------------------------------------------
        self.addLink(s_acc1, ce1_lan,
                     intfName1='s_acc1-eth0',
                     intfName2='ce1_lan-eth0',
                     params2={'ip': '10.1.0.1/24'})


# ===========================================================================
# Hàm cấu hình sau khi Mininet khởi động
# ===========================================================================
def configure_branch1(net):
    """
    Cấu hình thêm cho chi nhánh 1:
    - Bật IP forwarding trên ce1_lan
    - Chuẩn bị interface eth1 (uplink backbone) - chưa gán IP khi chạy độc lập
    - Kiểm tra ping nội bộ
    """
    info('\n*** Cấu hình Chi nhánh 1 – Mạng phẳng\n')

    ce1_lan = net['ce1_lan']

    # Bật IP forwarding trên router
    ce1_lan.cmd('sysctl -w net.ipv4.ip_forward=1')

    # Chuẩn bị interface eth1 (uplink về backbone CE1)
    # Khi chạy độc lập: để trống
    # Khi tích hợp orchestrator: sẽ được gán 10.0.1.1/30
    info('*** [INFO] ce1_lan-eth1 là uplink về backbone CE1 (10.0.1.1/30)\n')
    info('          Khi chạy độc lập, interface này chưa kết nối.\n')

    info('*** Cấu hình Chi nhánh 1 hoàn tất!\n')
    info('    Subnet LAN: 10.1.0.0/24\n')
    info('    Gateway:    ce1_lan = 10.1.0.1\n')
    info('    Hosts:      host1=10.1.0.101, host2=.102, host3=.103, host4=.104\n')


# ===========================================================================
# Hàm main: chạy topology chi nhánh 1 độc lập
# ===========================================================================
def run_branch1():
    """Khởi chạy topology Branch 1 Flat và mở CLI."""
    setLogLevel('info')

    info('*** Khởi tạo topology Chi nhánh 1 – Mạng phẳng (Flat Network)\n')
    topo = Branch1FlatTopo()

    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()

    configure_branch1(net)

    info('\n*** Kiểm tra kết nối nội bộ (ping all)\n')
    net.pingAll()

    info('\n*** Mở Mininet CLI (gõ "exit" để thoát)\n')
    CLI(net)

    net.stop()


# ===========================================================================
# Khai báo topos (dùng với --custom flag của Mininet)
# ===========================================================================
topos = {'branch1_flat': Branch1FlatTopo}

if __name__ == '__main__':
    run_branch1()
