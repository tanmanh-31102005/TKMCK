#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: topo_branch2_3tier.py
MÔ TẢ: Topology LAN nội bộ Chi nhánh 2 – Mạng 3 lớp (Core-Distribution-Access)

Kiến trúc (theo LOGIC.jpg):
  ┌───────────────────────────────────────────────────────────────┐
  │              CHI NHÁNH 2 – 3-TIER HIERARCHICAL                │
  │                                                               │
  │                       [ce2_lan]  ◄── uplink lên CE2           │
  │                       /       \                               │
  │             [core1]           [core2]    ← LỚP CORE           │
  │            /   \               /   \                          │
  │       [dist1] [dist2]    [dist2] [dist1] ← LỚP DISTRIBUTION   │
  │        (cross-connected, mỗi dist nối cả 2 core)              │
  │             |      |      |      |                            │
  │          [acc1]  [acc2]  [acc3]          ← LỚP ACCESS         │
  │          /   \   /   \   /   \                               │
  │       adm1 adm2 lab1 lab2 gest1 gest2                        │
  └───────────────────────────────────────────────────────────────┘

Sơ đồ kết nối chi tiết (theo LOGIC.jpg):
  ce2_lan → core1, core2
  core1   → dist1, dist2
  core2   → dist1, dist2   (mỗi dist nối CẢ 2 core → redundancy)
  dist1   → acc1, acc2
  dist2   → acc2, acc3
  acc1    → admin1, admin2
  acc2    → lab1, lab2
  acc3    → guest1, guest2

Subnet và VLAN (mô phỏng bằng subnet khác nhau):
  VLAN 10 - Admin : 10.2.10.0/24  (admin1=.11, admin2=.12)
  VLAN 20 - Lab   : 10.2.20.0/24  (lab1=.21, lab2=.22)
  VLAN 30 - Guest : 10.2.30.0/24  (guest1=.31, guest2=.32)
  Mgmt/Core link  : 10.2.0.x/30 (point-to-point giữa router và switches)
  Uplink backbone : 10.0.2.1/30 (ce2_lan về CE2 backbone)

  Inter-VLAN routing thực hiện tại ce2_lan (router-on-a-stick concept).

CÁCH CHẠY ĐỘC LẬP:
  sudo mn --custom topo_branch2_3tier.py --topo branch2_3tier --test ping
  hoặc:
  sudo python3 topo_branch2_3tier.py
=============================================================================
"""

from mininet.net import Mininet
from mininet.node import Node, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo


# ===========================================================================
# LinuxRouter: Node hoạt động như router Linux
# ===========================================================================
class LinuxRouter(Node):
    """Node Mininet hoạt động như router Linux (bật ip_forward)."""

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


# ===========================================================================
# Branch2ThreeTierTopo: Mạng 3 lớp chi nhánh 2
# ===========================================================================
class Branch2ThreeTierTopo(Topo):
    """
    Topology mạng 3 lớp (Core - Distribution - Access) – Chi nhánh 2.
    
    Lớp Core     : core1, core2
    Lớp Dist     : dist1, dist2
    Lớp Access   : acc1 (admin), acc2 (lab), acc3 (guest)
    Hosts        : admin1, admin2, lab1, lab2, guest1, guest2
    Router uplink: ce2_lan (Inter-VLAN + gateway về backbone)
    """

    def build(self, **opts):
        # -------------------------------------------------------------------
        # Router ce2_lan: Inter-VLAN routing + uplink về backbone CE2
        # eth0: kết nối core1  (10.2.0.1/30)
        # eth1: kết nối core2  (10.2.0.5/30)
        # eth2: uplink backbone (10.0.2.1/30) – dùng khi tích hợp
        # eth3: VLAN 10 gateway (10.2.10.1/24) – sub-interface logic
        # eth4: VLAN 20 gateway (10.2.20.1/24)
        # eth5: VLAN 30 gateway (10.2.30.1/24)
        # -------------------------------------------------------------------
        ce2_lan = self.addNode('ce2_lan', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # LỚP CORE (2 switch core kết nối redundant)
        # -------------------------------------------------------------------
        core1 = self.addSwitch('core1', cls=OVSSwitch, failMode='standalone')
        core2 = self.addSwitch('core2', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # LỚP DISTRIBUTION (2 switch, mỗi cái nối cả 2 core – cross-link)
        # -------------------------------------------------------------------
        dist1 = self.addSwitch('dist1', cls=OVSSwitch, failMode='standalone')
        dist2 = self.addSwitch('dist2', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # LỚP ACCESS (3 switch, phân theo nhóm user)
        # acc1: kết nối admin1, admin2
        # acc2: kết nối lab1, lab2
        # acc3: kết nối guest1, guest2
        # -------------------------------------------------------------------
        acc1 = self.addSwitch('acc1', cls=OVSSwitch, failMode='standalone')
        acc2 = self.addSwitch('acc2', cls=OVSSwitch, failMode='standalone')
        acc3 = self.addSwitch('acc3', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # Hosts: nhóm Admin (VLAN 10 – subnet 10.2.10.0/24)
        # -------------------------------------------------------------------
        admin1 = self.addHost('admin1',
                              ip='10.2.10.11/24',
                              defaultRoute='via 10.2.10.1')
        admin2 = self.addHost('admin2',
                              ip='10.2.10.12/24',
                              defaultRoute='via 10.2.10.1')

        # -------------------------------------------------------------------
        # Hosts: nhóm Lab (VLAN 20 – subnet 10.2.20.0/24)
        # -------------------------------------------------------------------
        lab1 = self.addHost('lab1',
                            ip='10.2.20.21/24',
                            defaultRoute='via 10.2.20.1')
        lab2 = self.addHost('lab2',
                            ip='10.2.20.22/24',
                            defaultRoute='via 10.2.20.1')

        # -------------------------------------------------------------------
        # Hosts: nhóm Guest (VLAN 30 – subnet 10.2.30.0/24)
        # -------------------------------------------------------------------
        guest1 = self.addHost('guest1',
                              ip='10.2.30.31/24',
                              defaultRoute='via 10.2.30.1')
        guest2 = self.addHost('guest2',
                              ip='10.2.30.32/24',
                              defaultRoute='via 10.2.30.1')

        # -------------------------------------------------------------------
        # LIÊN KẾT: ce2_lan ↔ LỚP CORE
        # ce2_lan-eth0 ↔ core1  (10.2.0.1/30 -- 10.2.0.2/30)
        # ce2_lan-eth1 ↔ core2  (10.2.0.5/30 -- 10.2.0.6/30)
        # -------------------------------------------------------------------
        self.addLink(ce2_lan, core1,
                     intfName1='ce2_lan-eth0',
                     params1={'ip': '10.2.0.1/30'},
                     intfName2='core1-eth0')

        self.addLink(ce2_lan, core2,
                     intfName1='ce2_lan-eth1',
                     params1={'ip': '10.2.0.5/30'},
                     intfName2='core2-eth0')

        # -------------------------------------------------------------------
        # LIÊN KẾT: LỚP CORE ↔ LỚP DISTRIBUTION (cross-connected)
        # core1 → dist1, core1 → dist2
        # core2 → dist1, core2 → dist2
        # -------------------------------------------------------------------
        self.addLink(core1, dist1,
                     intfName1='core1-eth1', intfName2='dist1-eth0')
        self.addLink(core1, dist2,
                     intfName1='core1-eth2', intfName2='dist2-eth0')
        self.addLink(core2, dist1,
                     intfName1='core2-eth1', intfName2='dist1-eth1')
        self.addLink(core2, dist2,
                     intfName1='core2-eth2', intfName2='dist2-eth1')

        # -------------------------------------------------------------------
        # LIÊN KẾT: LỚP DISTRIBUTION ↔ LỚP ACCESS
        # dist1 → acc1 (admin), dist1 → acc2 (lab)
        # dist2 → acc2 (lab),   dist2 → acc3 (guest)
        # -------------------------------------------------------------------
        self.addLink(dist1, acc1,
                     intfName1='dist1-eth2', intfName2='acc1-eth0')
        self.addLink(dist1, acc2,
                     intfName1='dist1-eth3', intfName2='acc2-eth0')
        self.addLink(dist2, acc2,
                     intfName1='dist2-eth2', intfName2='acc2-eth1')
        self.addLink(dist2, acc3,
                     intfName1='dist2-eth3', intfName2='acc3-eth0')

        # -------------------------------------------------------------------
        # LIÊN KẾT: LỚP ACCESS ↔ HOSTS
        # acc1 → admin1, admin2
        # acc2 → lab1, lab2
        # acc3 → guest1, guest2
        # -------------------------------------------------------------------
        self.addLink(acc1, admin1,
                     intfName1='acc1-eth1', intfName2='admin1-eth0')
        self.addLink(acc1, admin2,
                     intfName1='acc1-eth2', intfName2='admin2-eth0')

        self.addLink(acc2, lab1,
                     intfName1='acc2-eth2', intfName2='lab1-eth0')
        self.addLink(acc2, lab2,
                     intfName1='acc2-eth3', intfName2='lab2-eth0')

        self.addLink(acc3, guest1,
                     intfName1='acc3-eth1', intfName2='guest1-eth0')
        self.addLink(acc3, guest2,
                     intfName1='acc3-eth2', intfName2='guest2-eth0')


# ===========================================================================
# Hàm cấu hình Inter-VLAN routing tại ce2_lan
# ===========================================================================
def configure_branch2(net):
    """
    Cấu hình Inter-VLAN routing và IP gateway cho chi nhánh 2.

    Hai vấn đề đã được sửa so với phiên bản cũ (dummy interface):

    1. L2 LOOP: core1→dist1→core2→dist2→core1 (cross-link) tạo loop đ tích.
       Sửa: bật RSTP trên tất cả OVS switch, chờ hội tụ mới configure.

    2. ARP BROKEN: dummy interface (vlan10, vlan20, vlan30) không
       gửi ARP response trên switch fabric → host không tìm được gateway.
       Sửa: add IP alias trực tiếp lên ce2_lan-eth0 (cùng L2 domain với tất
       cả host). OVS standalone flood ARP → ce2_lan-eth0 hời ARP đúng.
    """
    import time
    info('\n*** Cấu hình Chi nhánh 2 – Mạng 3 lớp\n')

    ce2_lan = net['ce2_lan']

    # Bật IP forwarding
    ce2_lan.cmd('sysctl -w net.ipv4.ip_forward=1')

    # ------------------------------------------------------------------
    # Bước 1: Bật RSTP trên tất cả OVS switch – PHẢI LÀM TRƯỚC
    # Cross-link core⇔dist tạo loop L2 → broadcast storm nếu không có STP
    # ------------------------------------------------------------------
    info('*** [1/3] Bật RSTP trên OVS switches (chống loop L2)\n')
    for sw in ['core1', 'core2', 'dist1', 'dist2', 'acc1', 'acc2', 'acc3']:
        ret = net[sw].cmd(f'ovs-vsctl set Bridge {sw} rstp_enable=true 2>/dev/null')
        if 'error' in ret.lower() or 'unknown' in ret.lower():
            net[sw].cmd(f'ovs-vsctl set Bridge {sw} stp_enable=true 2>/dev/null')
    info('    Chờ 4 giây cho RSTP hội tụ...\n')
    time.sleep(4)

    # ------------------------------------------------------------------
    # Bước 2: Thêm IP alias cho các VLAN gateway trên ce2_lan-eth0
    # 
    # Tại sao IP alias chứ không phải dummy interface?
    # - Tất cả switch (core1/2, dist1/2, acc1/2/3) là OVS standalone →
    #   chúng tạo 1 broadcast domain duy nhất.
    # - ce2_lan-eth0 thuộc broadcast domain này (nối core1).
    # - Khi host ARP cho 10.2.10.1, ARP flood khắp switch, đến ce2_lan-eth0.
    # - ce2_lan-eth0 có IP 10.2.10.1/24 (alias) → trả lời ARP → routing OK.
    # ------------------------------------------------------------------
    info('*** [2/3] Thêm gateway IP aliases trên ce2_lan-eth0\n')
    ce2_lan.cmd('ip addr add 10.2.10.1/24 dev ce2_lan-eth0 2>/dev/null')
    ce2_lan.cmd('ip addr add 10.2.20.1/24 dev ce2_lan-eth0 2>/dev/null')
    ce2_lan.cmd('ip addr add 10.2.30.1/24 dev ce2_lan-eth0 2>/dev/null')

    # ------------------------------------------------------------------
    # Bước 3: Route Inter-VLAN (tự động có khi add alias, nhưng thêm rõ ràng)
    # ------------------------------------------------------------------
    info('*** [3/3] Cấu hình route Inter-VLAN trên ce2_lan\n')
    ce2_lan.cmd('ip route add 10.2.10.0/24 dev ce2_lan-eth0 2>/dev/null')
    ce2_lan.cmd('ip route add 10.2.20.0/24 dev ce2_lan-eth0 2>/dev/null')
    ce2_lan.cmd('ip route add 10.2.30.0/24 dev ce2_lan-eth0 2>/dev/null')

    info('\n*** Chi nhánh 2 sẵn sàng!\n')
    info('    VLAN 10 Admin : 10.2.10.0/24  gateway=10.2.10.1 (alias ce2_lan-eth0)\n')
    info('    VLAN 20 Lab   : 10.2.20.0/24  gateway=10.2.20.1 (alias ce2_lan-eth0)\n')
    info('    VLAN 30 Guest : 10.2.30.0/24  gateway=10.2.30.1 (alias ce2_lan-eth0)\n')
    info('    L2 Loop       : đã xử lý bằng RSTP (một số port sẽ bị block)\n')
    info('    Inter-VLAN    : host → ce2_lan-eth0 → route → host đích\n')


# ===========================================================================
# Hàm kiểm tra kết nối (ping test nội bộ)
# ===========================================================================
def test_connectivity(net):
    """Kiểm tra ping giữa các host cùng VLAN và khác VLAN."""
    info('\n*** Ping nội bộ (cùng VLAN)\n')
    admin1 = net['admin1']
    admin2 = net['admin2']
    lab1   = net['lab1']
    guest1 = net['guest1']

    info('  admin1 → admin2 (cùng VLAN 10): ')
    result = admin1.cmd('ping -c 2 -W 1 10.2.10.12')
    loss = '0%' if '0% packet loss' in result else 'FAIL'
    info(f'{loss}\n')

    info('  lab1 → lab2 (cùng VLAN 20): ')
    result = lab1.cmd('ping -c 2 -W 1 10.2.20.22')
    loss = '0%' if '0% packet loss' in result else 'FAIL'
    info(f'{loss}\n')

    info('\n*** Ping Inter-VLAN (qua ce2_lan router)\n')
    info('  admin1 → lab1 (VLAN 10 → 20): ')
    result = admin1.cmd('ping -c 2 -W 2 10.2.20.21')
    loss = '0%' if '0% packet loss' in result else 'FAIL/PARTIAL'
    info(f'{loss}\n')

    info('  admin1 → guest1 (VLAN 10 → 30): ')
    result = admin1.cmd('ping -c 2 -W 2 10.2.30.31')
    loss = '0%' if '0% packet loss' in result else 'FAIL/PARTIAL'
    info(f'{loss}\n')


# ===========================================================================
# Hàm main: chạy topology chi nhánh 2 độc lập
# ===========================================================================
def run_branch2():
    """Khởi chạy topology Branch 2 Three-Tier và mở CLI."""
    setLogLevel('info')

    info('*** Khởi tạo topology Chi nhánh 2 – Mạng 3 lớp (Core-Distribution-Access)\n')
    topo = Branch2ThreeTierTopo()

    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()

    configure_branch2(net)
    test_connectivity(net)

    info('\n*** Mở Mininet CLI (gõ "exit" để thoát)\n')
    CLI(net)

    net.stop()


# ===========================================================================
# Khai báo topos (dùng với --custom flag của Mininet)
# ===========================================================================
topos = {'branch2_3tier': Branch2ThreeTierTopo}

if __name__ == '__main__':
    run_branch2()
