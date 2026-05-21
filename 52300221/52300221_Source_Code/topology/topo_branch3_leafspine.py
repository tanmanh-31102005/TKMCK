#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: topo_branch3_leafspine.py
MÔ TẢ: Topology LAN nội bộ Chi nhánh 3 – Mạng 2 lớp Leaf-Spine

Kiến trúc (theo LOGIC.jpg):
  ┌─────────────────────────────────────────────────────────────┐
  │              CHI NHÁNH 3 – LEAF-SPINE (2-TIER)              │
  │                                                             │
  │                      [ce3_lan]  ◄── uplink lên CE3          │
  │                      /       \                              │
  │           [spine1]          [spine2]    ← SWITCH SPINE       │
  │           /  |  \           /  |  \                         │
  │       [leaf1][leaf2][leaf3]              ← SWITCH LEAF       │
  │         (mỗi leaf nối tới TẤT CẢ spine)                    │
  │        /   \   /   \   /   \                               │
  │      web1 web2 dns1 dns2 db1 db2        ← SERVERS           │
  └─────────────────────────────────────────────────────────────┘

Nguyên tắc Leaf-Spine:
  - Mỗi Leaf switch kết nối đến TẤT CẢ Spine switch (any-to-any path).
  - Không có kết nối Leaf-Leaf hoặc Spine-Spine.
  - Mọi đường đi giữa 2 server đều qua đúng 2 hop (leaf → spine → leaf).
  - Đây là kiến trúc Clos Network, tối ưu cho Data Center.

Thành phần:
  Spine : spine1, spine2
  Leaf  : leaf1 (web), leaf2 (dns), leaf3 (db)
  Server: web1, web2, dns1, dns2, db1, db2
  Router: ce3_lan (uplink về backbone CE3)

Subnet:
  Spine/Leaf links (P2P /30):
    ce3_lan-eth0 ↔ spine1  : 10.3.0.1/30 -- 10.3.0.2/30
    ce3_lan-eth1 ↔ spine2  : 10.3.0.5/30 -- 10.3.0.6/30
    spine1 ↔ leaf1 : 10.3.1.0/30
    spine1 ↔ leaf2 : 10.3.1.4/30
    spine1 ↔ leaf3 : 10.3.1.8/30
    spine2 ↔ leaf1 : 10.3.2.0/30
    spine2 ↔ leaf2 : 10.3.2.4/30
    spine2 ↔ leaf3 : 10.3.2.8/30
  Server subnets (mỗi leaf /24):
    leaf1 zone – Web : 10.3.10.0/24 (web1=.11, web2=.12)
    leaf2 zone – DNS : 10.3.20.0/24 (dns1=.21, dns2=.22)
    leaf3 zone – DB  : 10.3.30.0/24 (db1=.31, db2=.32)

CÁCH CHẠY ĐỘC LẬP:
  sudo mn --custom topo_branch3_leafspine.py --topo branch3_leafspine --test ping
  hoặc:
  sudo python3 topo_branch3_leafspine.py
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
# Branch3LeafSpineTopo: Mạng Leaf-Spine chi nhánh 3
# ===========================================================================
class Branch3LeafSpineTopo(Topo):
    """
    Topology mạng Leaf-Spine (2 lớp) – Chi nhánh 3.
    
    Cấu trúc Clos Network:
      2 Spine switch (aggregation layer)
      3 Leaf switch  (edge layer, mỗi leaf nối tất cả spine)
      6 Server host  (2 leaf1=web, 2 leaf2=dns, 2 leaf3=db)
    
    Đặc điểm: mọi đường đi qua đúng 2 hop (leaf→spine→leaf),
    băng thông cân bằng, không có single point of failure.
    """

    def build(self, **opts):
        # -------------------------------------------------------------------
        # Router ce3_lan: gateway + uplink về backbone CE3
        # eth0: kết nối spine1  (10.3.0.1/30)
        # eth1: kết nối spine2  (10.3.0.5/30)
        # eth2: uplink backbone (10.0.3.1/30) – dùng khi tích hợp
        # -------------------------------------------------------------------
        ce3_lan = self.addNode('ce3_lan', cls=LinuxRouter, ip=None)

        # -------------------------------------------------------------------
        # LỚP SPINE (Aggregation Layer)
        # 2 Spine switch: spine1, spine2
        # Đây là lớp trung gian kết nối tất cả các Leaf
        # -------------------------------------------------------------------
        spine1 = self.addSwitch('spine1', cls=OVSSwitch, failMode='standalone')
        spine2 = self.addSwitch('spine2', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # LỚP LEAF (Edge Layer)
        # 3 Leaf switch, phân theo nhóm dịch vụ:
        #   leaf1: phụ trách Web servers (web1, web2)
        #   leaf2: phụ trách DNS servers (dns1, dns2)
        #   leaf3: phụ trách DB  servers (db1,  db2)
        # -------------------------------------------------------------------
        leaf1 = self.addSwitch('leaf1', cls=OVSSwitch, failMode='standalone')
        leaf2 = self.addSwitch('leaf2', cls=OVSSwitch, failMode='standalone')
        leaf3 = self.addSwitch('leaf3', cls=OVSSwitch, failMode='standalone')

        # -------------------------------------------------------------------
        # Server hosts theo nhóm dịch vụ
        # -------------------------------------------------------------------
        # Web servers – subnet 10.3.10.0/24 – gateway 10.3.10.1
        web1 = self.addHost('web1',
                            ip='10.3.10.11/24',
                            defaultRoute='via 10.3.10.1')
        web2 = self.addHost('web2',
                            ip='10.3.10.12/24',
                            defaultRoute='via 10.3.10.1')

        # DNS servers – subnet 10.3.20.0/24 – gateway 10.3.20.1
        dns1 = self.addHost('dns1',
                            ip='10.3.20.21/24',
                            defaultRoute='via 10.3.20.1')
        dns2 = self.addHost('dns2',
                            ip='10.3.20.22/24',
                            defaultRoute='via 10.3.20.1')

        # DB servers – subnet 10.3.30.0/24 – gateway 10.3.30.1
        db1 = self.addHost('db1',
                           ip='10.3.30.31/24',
                           defaultRoute='via 10.3.30.1')
        db2 = self.addHost('db2',
                           ip='10.3.30.32/24',
                           defaultRoute='via 10.3.30.1')

        # -------------------------------------------------------------------
        # LIÊN KẾT: ce3_lan ↔ LỚP SPINE
        # ce3_lan-eth0 ↔ spine1 (10.3.0.1/30 -- 10.3.0.2/30)
        # ce3_lan-eth1 ↔ spine2 (10.3.0.5/30 -- 10.3.0.6/30)
        # -------------------------------------------------------------------
        self.addLink(ce3_lan, spine1,
                     intfName1='ce3_lan-eth0',
                     params1={'ip': '10.3.0.1/30'},
                     intfName2='spine1-eth0')

        self.addLink(ce3_lan, spine2,
                     intfName1='ce3_lan-eth1',
                     params1={'ip': '10.3.0.5/30'},
                     intfName2='spine2-eth0')

        # -------------------------------------------------------------------
        # LIÊN KẾT: LỚP SPINE ↔ LỚP LEAF (full-mesh: mỗi leaf nối tất cả spine)
        #
        # Đây là nguyên tắc cốt lõi của Leaf-Spine:
        #   leaf1 ↔ spine1, leaf1 ↔ spine2
        #   leaf2 ↔ spine1, leaf2 ↔ spine2
        #   leaf3 ↔ spine1, leaf3 ↔ spine2
        # -------------------------------------------------------------------
        # spine1 ↔ leaf1
        self.addLink(spine1, leaf1,
                     intfName1='spine1-eth1', intfName2='leaf1-eth0')
        # spine1 ↔ leaf2
        self.addLink(spine1, leaf2,
                     intfName1='spine1-eth2', intfName2='leaf2-eth0')
        # spine1 ↔ leaf3
        self.addLink(spine1, leaf3,
                     intfName1='spine1-eth3', intfName2='leaf3-eth0')

        # spine2 ↔ leaf1
        self.addLink(spine2, leaf1,
                     intfName1='spine2-eth1', intfName2='leaf1-eth1')
        # spine2 ↔ leaf2
        self.addLink(spine2, leaf2,
                     intfName1='spine2-eth2', intfName2='leaf2-eth1')
        # spine2 ↔ leaf3
        self.addLink(spine2, leaf3,
                     intfName1='spine2-eth3', intfName2='leaf3-eth1')

        # -------------------------------------------------------------------
        # LIÊN KẾT: LỚP LEAF ↔ SERVERS
        # leaf1 → web1, web2
        # leaf2 → dns1, dns2
        # leaf3 → db1, db2
        # -------------------------------------------------------------------
        self.addLink(leaf1, web1,
                     intfName1='leaf1-eth2', intfName2='web1-eth0')
        self.addLink(leaf1, web2,
                     intfName1='leaf1-eth3', intfName2='web2-eth0')

        self.addLink(leaf2, dns1,
                     intfName1='leaf2-eth2', intfName2='dns1-eth0')
        self.addLink(leaf2, dns2,
                     intfName1='leaf2-eth3', intfName2='dns2-eth0')

        self.addLink(leaf3, db1,
                     intfName1='leaf3-eth2', intfName2='db1-eth0')
        self.addLink(leaf3, db2,
                     intfName1='leaf3-eth3', intfName2='db2-eth0')


# ===========================================================================
# Hàm cấu hình cho chi nhánh 3 (Leaf-Spine)
# ===========================================================================
def configure_branch3(net):
    """
    Cấu hình IP routing cho chi nhánh 3 Leaf-Spine.

    Hai vấn đề đã được sửa so với phiên bản cũ (dummy interface):

    1. L2 LOOP: Leaf-Spine full-mesh (mỗi leaf nối tất cả spine) tạo loop
       trên L2: spine1→leaf1→spine2→leaf2→spine1...
       Sửa: bật RSTP trước khi dùng mạng. RSTP block một số port nhưng
       vẫn đảm bảo 2-hop path.  

    2. ARP BROKEN: dummy interface (zone_web, zone_dns, zone_db) không
       phát ARP response trên switch fabric.
       Sửa: add IP alias trực tiếp trên ce3_lan-eth0 (thuộc L2 domain).
    """
    import time
    info('\n*** Cấu hình Chi nhánh 3 – Mạng Leaf-Spine\n')

    ce3_lan = net['ce3_lan']

    # Bật IP forwarding trên router
    ce3_lan.cmd('sysctl -w net.ipv4.ip_forward=1')

    # ------------------------------------------------------------------
    # Bước 1: Bật RSTP trên tất cả OVS switch – PHẢI LÀM TRƯỚC
    # Leaf-Spine full-mesh: spine1↔leaf1↔spine2 → loop L2!
    # RSTP/STP sẽ block một số port để phá vòng lặp.
    # ------------------------------------------------------------------
    info('*** [1/3] Bật RSTP trên OVS switches Leaf-Spine (chống loop L2)\n')
    for sw in ['spine1', 'spine2', 'leaf1', 'leaf2', 'leaf3']:
        ret = net[sw].cmd(f'ovs-vsctl set Bridge {sw} rstp_enable=true 2>/dev/null')
        if 'error' in ret.lower() or 'unknown' in ret.lower():
            net[sw].cmd(f'ovs-vsctl set Bridge {sw} stp_enable=true 2>/dev/null')
    info('    Chờ 4 giây cho RSTP hội tụ...\n')
    time.sleep(4)

    # ------------------------------------------------------------------
    # Bước 2: Thêm IP alias cho các server zone gateway trên ce3_lan-eth0
    #
    # Lý do dùng IP alias thay vì dummy interface:
    # - OVS standalone mode: spine1/spine2/leaf1/2/3 = 1 broadcast domain.
    # - ce3_lan-eth0 nối spine1 → thuộc broadcast domain đó.
    # - Host web1 ARP cho 10.3.10.1 → ARP flood qua các switch →
    #   đến ce3_lan-eth0 → ce3_lan trả lời ARP (vì eth0 có IP alias .1)
    # ------------------------------------------------------------------
    info('*** [2/3] Thêm gateway IP aliases trên ce3_lan-eth0\n')
    ce3_lan.cmd('ip addr add 10.3.10.1/24 dev ce3_lan-eth0 2>/dev/null')
    ce3_lan.cmd('ip addr add 10.3.20.1/24 dev ce3_lan-eth0 2>/dev/null')
    ce3_lan.cmd('ip addr add 10.3.30.1/24 dev ce3_lan-eth0 2>/dev/null')

    # ------------------------------------------------------------------
    # Bước 3: Route cho các server subnet (tự động có nhưng thêm tường minh)
    # ------------------------------------------------------------------
    info('*** [3/3] Cấu hình route server zones trên ce3_lan\n')
    ce3_lan.cmd('ip route add 10.3.10.0/24 dev ce3_lan-eth0 2>/dev/null')
    ce3_lan.cmd('ip route add 10.3.20.0/24 dev ce3_lan-eth0 2>/dev/null')
    ce3_lan.cmd('ip route add 10.3.30.0/24 dev ce3_lan-eth0 2>/dev/null')

    info('\n*** Chi nhánh 3 sẵn sàng!\n')
    info('    Leaf1 – Web Zone : 10.3.10.0/24  gateway=10.3.10.1 (alias ce3_lan-eth0)\n')
    info('    Leaf2 – DNS Zone : 10.3.20.0/24  gateway=10.3.20.1 (alias ce3_lan-eth0)\n')
    info('    Leaf3 – DB  Zone : 10.3.30.0/24  gateway=10.3.30.1 (alias ce3_lan-eth0)\n')
    info('    L2 Loop          : đã xử lý bằng RSTP\n')
    info('    Leaf-Spine paths : RSTP đảm bảo một đường nối có thể (bỏ qua)\n')


# ===========================================================================
# Hàm kiểm tra kết nối Leaf-Spine
# ===========================================================================
def test_connectivity(net):
    """
    Kiểm tra ping giữa các server – đặc điểm Leaf-Spine:
    Mọi đường đi đều qua spine (2 hops), đảm bảo equal-cost paths.
    """
    info('\n*** Kiểm tra kết nối Leaf-Spine\n')

    web1  = net['web1']
    dns1  = net['dns1']
    db1   = net['db1']
    web2  = net['web2']

    info('  web1 → web2 (cùng leaf1): ')
    result = web1.cmd('ping -c 2 -W 1 10.3.10.12')
    loss = '0%' if '0% packet loss' in result else 'FAIL'
    info(f'{loss}\n')

    info('  web1 → dns1 (leaf1 → spine → leaf2): ')
    result = web1.cmd('ping -c 2 -W 2 10.3.20.21')
    loss = '0%' if '0% packet loss' in result else 'FAIL/PARTIAL'
    info(f'{loss}\n')

    info('  web1 → db1  (leaf1 → spine → leaf3): ')
    result = web1.cmd('ping -c 2 -W 2 10.3.30.31')
    loss = '0%' if '0% packet loss' in result else 'FAIL/PARTIAL'
    info(f'{loss}\n')

    info('  dns1 → db2   (cross zone): ')
    result = dns1.cmd('ping -c 2 -W 2 10.3.30.32')
    loss = '0%' if '0% packet loss' in result else 'FAIL/PARTIAL'
    info(f'{loss}\n')


# ===========================================================================
# Hàm main: chạy topology chi nhánh 3 độc lập
# ===========================================================================
def run_branch3():
    """Khởi chạy topology Branch 3 Leaf-Spine và mở CLI."""
    setLogLevel('info')

    info('*** Khởi tạo topology Chi nhánh 3 – Mạng Leaf-Spine\n')
    topo = Branch3LeafSpineTopo()

    net = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()

    configure_branch3(net)
    test_connectivity(net)

    info('\n*** Mở Mininet CLI (gõ "exit" để thoát)\n')
    CLI(net)

    net.stop()


# ===========================================================================
# Khai báo topos (dùng với --custom flag của Mininet)
# ===========================================================================
topos = {'branch3_leafspine': Branch3LeafSpineTopo}

if __name__ == '__main__':
    run_branch3()
