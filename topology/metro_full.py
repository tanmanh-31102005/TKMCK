#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: metro_full.py  —  Orchestrator tổng hợp toàn hệ thống (VIẾT LẠI)
=============================================================================
Lý do viết lại: phiên bản cũ dùng _ingest()/self.g không ổn định trên
tất cả phiên bản Mininet. Phiên bản này tự khai báo TẤT CẢ node/link
trong một class Topo duy nhất, không dùng graph internal API.

Kiến trúc kết nối:
  [host1-4]─s_acc1─ce1_lan──────────────ce1─pe1─P1─P2─pe3─ce3─ce3_lan───[spine/leaf]
                                   ↑glue link↑         └─P3─P4─pe2─ce2─ce2_lan───[3-tier]
                                 10.100.x.0/30

  "Glue links" CE ↔ ce_lan (subnet KHÁC với CE-PE):
    CE1 ↔ ce1_lan : 10.100.1.0/30  (CE1=.1, ce1_lan=.2)
    CE2 ↔ ce2_lan : 10.100.2.0/30  (CE2=.1, ce2_lan=.2)
    CE3 ↔ ce3_lan : 10.100.3.0/30  (CE3=.1, ce3_lan=.2)

CÁCH CHẠY:
  sudo python3 metro_full.py
  hoặc: sudo mn --custom metro_full.py --topo metro_full
=============================================================================
"""

import re
from mininet.net import Mininet
from mininet.node import Node, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.topo import Topo


# ===========================================================================
# LinuxRouter – Node hoạt động như router Linux (bật ip_forward)
# ===========================================================================
class LinuxRouter(Node):
    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


# ===========================================================================
# MetroFullTopo – Topo tự khai báo tất cả node/link, không dùng _ingest
# ===========================================================================
class MetroFullTopo(Topo):
    """
    Topo tổng hợp: CE/PE/P backbone + 3 chi nhánh LAN.
    Tất cả node/link khai báo trực tiếp → stable với mọi Mininet version.
    """

    def build(self, **opts):
        self._build_backbone()
        self._build_branch1()
        self._build_branch2()
        self._build_branch3()
        self._build_glue_links()

    # -----------------------------------------------------------------------
    # BACKBONE: CE/PE/P
    # -----------------------------------------------------------------------
    def _build_backbone(self):
        """Khai báo toàn bộ router backbone và link P2P."""
        # CE routers (Customer Edge)
        self.addNode('ce1', cls=LinuxRouter, ip=None)
        self.addNode('ce2', cls=LinuxRouter, ip=None)
        self.addNode('ce3', cls=LinuxRouter, ip=None)

        # PE routers (Provider Edge)
        self.addNode('pe1', cls=LinuxRouter, ip=None)
        self.addNode('pe2', cls=LinuxRouter, ip=None)
        self.addNode('pe3', cls=LinuxRouter, ip=None)

        # P routers (Provider Core – MPLS region)
        self.addNode('p1', cls=LinuxRouter, ip=None)
        self.addNode('p2', cls=LinuxRouter, ip=None)
        self.addNode('p3', cls=LinuxRouter, ip=None)
        self.addNode('p4', cls=LinuxRouter, ip=None)

        # CE–PE links
        self.addLink('ce1', 'pe1',
                     intfName1='ce1-eth0', params1={'ip': '10.0.1.1/30'},
                     intfName2='pe1-eth0', params2={'ip': '10.0.1.2/30'})
        self.addLink('ce2', 'pe2',
                     intfName1='ce2-eth0', params1={'ip': '10.0.2.1/30'},
                     intfName2='pe2-eth0', params2={'ip': '10.0.2.2/30'})
        self.addLink('ce3', 'pe3',
                     intfName1='ce3-eth0', params1={'ip': '10.0.3.1/30'},
                     intfName2='pe3-eth0', params2={'ip': '10.0.3.2/30'})

        # PE–P links
        self.addLink('pe1', 'p1',
                     intfName1='pe1-eth1', params1={'ip': '10.10.11.1/30'},
                     intfName2='p1-eth0',  params2={'ip': '10.10.11.2/30'})
        self.addLink('pe1', 'p3',
                     intfName1='pe1-eth2', params1={'ip': '10.10.13.1/30'},
                     intfName2='p3-eth0',  params2={'ip': '10.10.13.2/30'})
        self.addLink('pe2', 'p3',
                     intfName1='pe2-eth1', params1={'ip': '10.10.23.1/30'},
                     intfName2='p3-eth1',  params2={'ip': '10.10.23.2/30'})
        self.addLink('pe2', 'p4',
                     intfName1='pe2-eth2', params1={'ip': '10.10.24.1/30'},
                     intfName2='p4-eth0',  params2={'ip': '10.10.24.2/30'})
        self.addLink('pe3', 'p2',
                     intfName1='pe3-eth1', params1={'ip': '10.10.32.1/30'},
                     intfName2='p2-eth0',  params2={'ip': '10.10.32.2/30'})
        self.addLink('pe3', 'p4',
                     intfName1='pe3-eth2', params1={'ip': '10.10.34.1/30'},
                     intfName2='p4-eth1',  params2={'ip': '10.10.34.2/30'})

        # P–P links (full-mesh P1/P2/P3/P4)
        self.addLink('p1', 'p2',
                     intfName1='p1-eth1', params1={'ip': '10.20.12.1/30'},
                     intfName2='p2-eth1', params2={'ip': '10.20.12.2/30'})
        self.addLink('p1', 'p3',
                     intfName1='p1-eth2', params1={'ip': '10.20.13.1/30'},
                     intfName2='p3-eth2', params2={'ip': '10.20.13.2/30'})
        self.addLink('p1', 'p4',
                     intfName1='p1-eth3', params1={'ip': '10.20.14.1/30'},
                     intfName2='p4-eth2', params2={'ip': '10.20.14.2/30'})
        self.addLink('p2', 'p3',
                     intfName1='p2-eth2', params1={'ip': '10.20.23.1/30'},
                     intfName2='p3-eth3', params2={'ip': '10.20.23.2/30'})
        self.addLink('p2', 'p4',
                     intfName1='p2-eth3', params1={'ip': '10.20.24.1/30'},
                     intfName2='p4-eth3', params2={'ip': '10.20.24.2/30'})
        self.addLink('p3', 'p4',
                     intfName1='p3-eth4', params1={'ip': '10.20.34.1/30'},
                     intfName2='p4-eth4', params2={'ip': '10.20.34.2/30'})

    # -----------------------------------------------------------------------
    # CHI NHÁNH 1 – Mạng phẳng (Flat)
    # -----------------------------------------------------------------------
    def _build_branch1(self):
        """Switch access + 4 host + ce1_lan router. Subnet: 10.1.0.0/24."""
        self.addNode('ce1_lan', cls=LinuxRouter, ip=None)

        s_acc1 = self.addSwitch('s_acc1', cls=OVSSwitch, failMode='standalone')

        self.addHost('host1', ip='10.1.0.101/24', defaultRoute='via 10.1.0.1')
        self.addHost('host2', ip='10.1.0.102/24', defaultRoute='via 10.1.0.1')
        self.addHost('host3', ip='10.1.0.103/24', defaultRoute='via 10.1.0.1')
        self.addHost('host4', ip='10.1.0.104/24', defaultRoute='via 10.1.0.1')

        # host ↔ switch access
        self.addLink('host1', s_acc1)
        self.addLink('host2', s_acc1)
        self.addLink('host3', s_acc1)
        self.addLink('host4', s_acc1)

        # switch access ↔ ce1_lan (gateway LAN)
        self.addLink(s_acc1, 'ce1_lan',
                     intfName2='ce1_lan-eth0',
                     params2={'ip': '10.1.0.1/24'})

    # -----------------------------------------------------------------------
    # CHI NHÁNH 2 – 3-tier Core–Distribution–Access
    # -----------------------------------------------------------------------
    def _build_branch2(self):
        """
        3 lớp: core1/core2 → dist1/dist2 → acc1/acc2/acc3 → hosts.
        ce2_lan: Inter-VLAN routing + uplink về CE2.
        VLAN10=admin(10.2.10.0/24), VLAN20=lab(10.2.20.0/24), VLAN30=guest(10.2.30.0/24).
        """
        self.addNode('ce2_lan', cls=LinuxRouter, ip=None)

        # Lớp Core
        core1 = self.addSwitch('core1', cls=OVSSwitch, failMode='standalone')
        core2 = self.addSwitch('core2', cls=OVSSwitch, failMode='standalone')

        # Lớp Distribution
        dist1 = self.addSwitch('dist1', cls=OVSSwitch, failMode='standalone')
        dist2 = self.addSwitch('dist2', cls=OVSSwitch, failMode='standalone')

        # Lớp Access
        acc1 = self.addSwitch('acc1', cls=OVSSwitch, failMode='standalone')
        acc2 = self.addSwitch('acc2', cls=OVSSwitch, failMode='standalone')
        acc3 = self.addSwitch('acc3', cls=OVSSwitch, failMode='standalone')

        # Hosts
        self.addHost('admin1', ip='10.2.10.11/24', defaultRoute='via 10.2.10.1')
        self.addHost('admin2', ip='10.2.10.12/24', defaultRoute='via 10.2.10.1')
        self.addHost('lab1',   ip='10.2.20.21/24', defaultRoute='via 10.2.20.1')
        self.addHost('lab2',   ip='10.2.20.22/24', defaultRoute='via 10.2.20.1')
        self.addHost('guest1', ip='10.2.30.31/24', defaultRoute='via 10.2.30.1')
        self.addHost('guest2', ip='10.2.30.32/24', defaultRoute='via 10.2.30.1')

        # ce2_lan ↔ Core (dual uplink)
        self.addLink('ce2_lan', core1,
                     intfName1='ce2_lan-eth0', params1={'ip': '10.2.0.1/30'})
        self.addLink('ce2_lan', core2,
                     intfName1='ce2_lan-eth1', params1={'ip': '10.2.0.5/30'})

        # Core ↔ Distribution (cross-connected – redundant path)
        self.addLink(core1, dist1)
        self.addLink(core1, dist2)
        self.addLink(core2, dist1)
        self.addLink(core2, dist2)

        # Distribution ↔ Access
        self.addLink(dist1, acc1)
        self.addLink(dist1, acc2)
        self.addLink(dist2, acc2)
        self.addLink(dist2, acc3)

        # Access ↔ Hosts
        self.addLink(acc1, 'admin1')
        self.addLink(acc1, 'admin2')
        self.addLink(acc2, 'lab1')
        self.addLink(acc2, 'lab2')
        self.addLink(acc3, 'guest1')
        self.addLink(acc3, 'guest2')

    # -----------------------------------------------------------------------
    # CHI NHÁNH 3 – Leaf–Spine (2-tier)
    # -----------------------------------------------------------------------
    def _build_branch3(self):
        """
        2 Spine + 3 Leaf (full-mesh) + 6 servers.
        ce3_lan: gateway + uplink về CE3.
        Web=10.3.10.0/24, DNS=10.3.20.0/24, DB=10.3.30.0/24.
        """
        self.addNode('ce3_lan', cls=LinuxRouter, ip=None)

        # Lớp Spine
        spine1 = self.addSwitch('spine1', cls=OVSSwitch, failMode='standalone')
        spine2 = self.addSwitch('spine2', cls=OVSSwitch, failMode='standalone')

        # Lớp Leaf
        leaf1 = self.addSwitch('leaf1', cls=OVSSwitch, failMode='standalone')
        leaf2 = self.addSwitch('leaf2', cls=OVSSwitch, failMode='standalone')
        leaf3 = self.addSwitch('leaf3', cls=OVSSwitch, failMode='standalone')

        # Servers
        self.addHost('web1', ip='10.3.10.11/24', defaultRoute='via 10.3.10.1')
        self.addHost('web2', ip='10.3.10.12/24', defaultRoute='via 10.3.10.1')
        self.addHost('dns1', ip='10.3.20.21/24', defaultRoute='via 10.3.20.1')
        self.addHost('dns2', ip='10.3.20.22/24', defaultRoute='via 10.3.20.1')
        self.addHost('db1',  ip='10.3.30.31/24', defaultRoute='via 10.3.30.1')
        self.addHost('db2',  ip='10.3.30.32/24', defaultRoute='via 10.3.30.1')

        # ce3_lan ↔ Spine
        self.addLink('ce3_lan', spine1,
                     intfName1='ce3_lan-eth0', params1={'ip': '10.3.0.1/30'})
        self.addLink('ce3_lan', spine2,
                     intfName1='ce3_lan-eth1', params1={'ip': '10.3.0.5/30'})

        # Spine ↔ Leaf (full-mesh: mỗi leaf nối TẤT CẢ spine)
        self.addLink(spine1, leaf1)
        self.addLink(spine1, leaf2)
        self.addLink(spine1, leaf3)
        self.addLink(spine2, leaf1)
        self.addLink(spine2, leaf2)
        self.addLink(spine2, leaf3)

        # Leaf ↔ Servers
        self.addLink(leaf1, 'web1')
        self.addLink(leaf1, 'web2')
        self.addLink(leaf2, 'dns1')
        self.addLink(leaf2, 'dns2')
        self.addLink(leaf3, 'db1')
        self.addLink(leaf3, 'db2')

    # -----------------------------------------------------------------------
    # GLUE LINKS: CE backbone ↔ ce_lan chi nhánh
    # -----------------------------------------------------------------------
    def _build_glue_links(self):
        """
        Nối CE backbone với router LAN từng chi nhánh.
        Dùng subnet 10.100.x.0/30 (KHÁC với CE-PE 10.0.x.0/30).
        """
        # CE1 (eth1) ↔ ce1_lan (eth1) : 10.100.1.0/30
        self.addLink('ce1', 'ce1_lan',
                     intfName1='ce1-eth1',     params1={'ip': '10.100.1.1/30'},
                     intfName2='ce1_lan-eth1', params2={'ip': '10.100.1.2/30'})

        # CE2 (eth1) ↔ ce2_lan (eth2) : 10.100.2.0/30
        self.addLink('ce2', 'ce2_lan',
                     intfName1='ce2-eth1',     params1={'ip': '10.100.2.1/30'},
                     intfName2='ce2_lan-eth2', params2={'ip': '10.100.2.2/30'})

        # CE3 (eth1) ↔ ce3_lan (eth2) : 10.100.3.0/30
        self.addLink('ce3', 'ce3_lan',
                     intfName1='ce3-eth1',     params1={'ip': '10.100.3.1/30'},
                     intfName2='ce3_lan-eth2', params2={'ip': '10.100.3.2/30'})


# ===========================================================================
# Cấu hình toàn hệ thống sau khi Mininet start()
# ===========================================================================
def configure_full_network(net):
    """
    Các bước cấu hình sau khi mạng đã khởi động:
    1. Bật IP forwarding
    2. Gán loopback (OSPF Router-ID)
    3. Gán gateway ảo cho LAN (dummy interface)
    4. Cấu hình route end-to-end
    """
    info('\n' + '='*68 + '\n')
    info('  KHỞI TẠO METRO ETHERNET MPLS – TOÀN HỆ THỐNG\n')
    info('='*68 + '\n')

    # ------------------------------------------------------------------
    # 1. Bật IP forwarding
    # ------------------------------------------------------------------
    info('*** [1/4] Bật IP forwarding trên tất cả router\n')
    routers = ['ce1','ce2','ce3','pe1','pe2','pe3',
               'p1','p2','p3','p4','ce1_lan','ce2_lan','ce3_lan']
    for r in routers:
        net[r].cmd('sysctl -w net.ipv4.ip_forward=1')

    # ------------------------------------------------------------------
    # 2. Loopback (dùng làm Router-ID cho OSPF/LDP)
    # ------------------------------------------------------------------
    info('*** [2/4] Gán loopback address\n')
    loopbacks = {
        'ce1': '1.1.1.1', 'ce2': '1.1.1.2', 'ce3': '1.1.1.3',
        'pe1': '2.2.2.1', 'pe2': '2.2.2.2', 'pe3': '2.2.2.3',
        'p1':  '3.3.3.1', 'p2':  '3.3.3.2',
        'p3':  '3.3.3.3', 'p4':  '3.3.3.4',
    }
    for node, lo_ip in loopbacks.items():
        net[node].cmd(f'ip addr add {lo_ip}/32 dev lo')

    # ------------------------------------------------------------------
    # 3. Bật RSTP/STP trên tất cả OVS switch – QUAN TRỌNG!
    #    Leaf-Spine và 3-tier có loop L2 → phải bật STP để tránh broadcast storm.
    # ------------------------------------------------------------------
    info('*** [3/4] Bật RSTP trên OVS switches\n')
    ovs_switches = [
        's_acc1',                          # Branch 1
        'core1', 'core2',                  # Branch 2 – Core layer
        'dist1', 'dist2',                  # Branch 2 – Distribution layer
        'acc1', 'acc2', 'acc3',            # Branch 2 – Access layer
        'spine1', 'spine2',                # Branch 3 – Spine layer
        'leaf1', 'leaf2', 'leaf3',         # Branch 3 – Leaf layer
    ]
    for sw in ovs_switches:
        if sw in net:
            # Thử RSTP trước (nhanh hơn), fallback về STP
            ret = net[sw].cmd(
                f'ovs-vsctl set Bridge {sw} rstp_enable=true 2>/dev/null')
            if 'error' in ret.lower() or 'unknown' in ret.lower():
                net[sw].cmd(f'ovs-vsctl set Bridge {sw} stp_enable=true 2>/dev/null')
    import time as _time
    info('    Chờ 4 giây cho STP hội tụ...\n')
    _time.sleep(4)

    # ------------------------------------------------------------------
    # Gateway IP cho Branch 2 và Branch 3:
    # KHÔNG dùng dummy interface (chúng không trả lời ARP từ host).
    # Thêm IP alias trực tiếp lên interface vật lý kết nối switch fabric
    # → ce2_lan-eth0 sẽ phản hồi ARP cho tất cả gateway 10.2.x.1
    # → ce3_lan-eth0 sẽ phản hồi ARP cho tất cả gateway 10.3.x.1
    # ------------------------------------------------------------------
    info('*** Thêm gateway IP aliases trên interface vật lý\n')

    # Branch 2: thêm gateway 3 VLAN lên ce2_lan-eth0 (đã nối switch fabric)
    net['ce2_lan'].cmd('ip addr add 10.2.10.1/24 dev ce2_lan-eth0 2>/dev/null')
    net['ce2_lan'].cmd('ip addr add 10.2.20.1/24 dev ce2_lan-eth0 2>/dev/null')
    net['ce2_lan'].cmd('ip addr add 10.2.30.1/24 dev ce2_lan-eth0 2>/dev/null')

    # Branch 3: thêm gateway 3 zone lên ce3_lan-eth0 (đã nối switch fabric)
    net['ce3_lan'].cmd('ip addr add 10.3.10.1/24 dev ce3_lan-eth0 2>/dev/null')
    net['ce3_lan'].cmd('ip addr add 10.3.20.1/24 dev ce3_lan-eth0 2>/dev/null')
    net['ce3_lan'].cmd('ip addr add 10.3.30.1/24 dev ce3_lan-eth0 2>/dev/null')

    # ------------------------------------------------------------------
    # 4. Route end-to-end
    # ------------------------------------------------------------------
    info('*** [4/4] Cấu hình static route end-to-end\n')

    # ---------- CE LAN routers ----------
    # ce1_lan: default route qua CE1
    net['ce1_lan'].cmd('ip route add default          via 10.100.1.1')
    net['ce1_lan'].cmd('ip route add 10.2.0.0/16      via 10.100.1.1')
    net['ce1_lan'].cmd('ip route add 10.3.0.0/16      via 10.100.1.1')

    # ce2_lan: default route qua CE2; route LAN local
    net['ce2_lan'].cmd('ip route add default          via 10.100.2.1 2>/dev/null')
    net['ce2_lan'].cmd('ip route add 10.1.0.0/24      via 10.100.2.1 2>/dev/null')
    net['ce2_lan'].cmd('ip route add 10.3.0.0/16      via 10.100.2.1 2>/dev/null')
    # Routes cho VLAN subnet đã tự động tạo khi add IP alias trên ce2_lan-eth0
    net['ce2_lan'].cmd('ip route add 10.2.10.0/24     dev ce2_lan-eth0 2>/dev/null')
    net['ce2_lan'].cmd('ip route add 10.2.20.0/24     dev ce2_lan-eth0 2>/dev/null')
    net['ce2_lan'].cmd('ip route add 10.2.30.0/24     dev ce2_lan-eth0 2>/dev/null')

    # ce3_lan: default route qua CE3; route LAN local
    net['ce3_lan'].cmd('ip route add default          via 10.100.3.1 2>/dev/null')
    net['ce3_lan'].cmd('ip route add 10.1.0.0/24      via 10.100.3.1 2>/dev/null')
    net['ce3_lan'].cmd('ip route add 10.2.0.0/16      via 10.100.3.1 2>/dev/null')
    # Routes cho server zones đã tự động tạo khi add IP alias trên ce3_lan-eth0  
    net['ce3_lan'].cmd('ip route add 10.3.10.0/24     dev ce3_lan-eth0 2>/dev/null')
    net['ce3_lan'].cmd('ip route add 10.3.20.0/24     dev ce3_lan-eth0 2>/dev/null')
    net['ce3_lan'].cmd('ip route add 10.3.30.0/24     dev ce3_lan-eth0 2>/dev/null')

    # ---------- CE backbone routers ----------
    # CE1: LAN1 via ce1_lan; các LAN khác via PE1
    net['ce1'].cmd('ip route add 10.1.0.0/24          via 10.100.1.2')
    net['ce1'].cmd('ip route add 10.2.0.0/16          via 10.0.1.2')
    net['ce1'].cmd('ip route add 10.3.0.0/16          via 10.0.1.2')
    net['ce1'].cmd('ip route add 10.100.1.0/30        dev ce1-eth1')

    # CE2: LAN2 via ce2_lan; các LAN khác via PE2
    net['ce2'].cmd('ip route add 10.2.0.0/16          via 10.100.2.2')
    net['ce2'].cmd('ip route add 10.1.0.0/24          via 10.0.2.2')
    net['ce2'].cmd('ip route add 10.3.0.0/16          via 10.0.2.2')

    # CE3: LAN3 via ce3_lan; các LAN khác via PE3
    net['ce3'].cmd('ip route add 10.3.0.0/16          via 10.100.3.2')
    net['ce3'].cmd('ip route add 10.1.0.0/24          via 10.0.3.2')
    net['ce3'].cmd('ip route add 10.2.0.0/16          via 10.0.3.2')

    # ---------- PE routers ----------
    # PE1: biết LAN1 qua CE1; các LAN khác qua P
    net['pe1'].cmd('ip route add 10.1.0.0/24          via 10.0.1.1')
    net['pe1'].cmd('ip route add 10.100.1.0/30        via 10.0.1.1')
    net['pe1'].cmd('ip route add 10.2.0.0/16          via 10.10.11.2')  # P1→P3→PE2
    net['pe1'].cmd('ip route add 10.3.0.0/16          via 10.10.11.2')  # P1→P2→PE3

    # PE2: biết LAN2+VLAN qua CE2; các LAN khác qua P
    net['pe2'].cmd('ip route add 10.2.0.0/16          via 10.0.2.1')
    net['pe2'].cmd('ip route add 10.100.2.0/30        via 10.0.2.1')
    net['pe2'].cmd('ip route add 10.1.0.0/24          via 10.10.23.2')  # P3→P1→PE1
    net['pe2'].cmd('ip route add 10.3.0.0/16          via 10.10.24.2')  # P4→PE3

    # PE3: biết LAN3 qua CE3; các LAN khác qua P
    net['pe3'].cmd('ip route add 10.3.0.0/16          via 10.0.3.1')
    net['pe3'].cmd('ip route add 10.100.3.0/30        via 10.0.3.1')
    net['pe3'].cmd('ip route add 10.1.0.0/24          via 10.10.32.2')  # P2→P1→PE1
    net['pe3'].cmd('ip route add 10.2.0.0/16          via 10.10.34.2')  # P4→PE2

    # ---------- P routers (lõi MPLS – forward L3 nếu chưa dùng MPLS) ----------
    net['p1'].cmd('ip route add 10.1.0.0/24           via 10.10.11.1')  # PE1→CE1
    net['p1'].cmd('ip route add 10.100.1.0/30         via 10.10.11.1')
    net['p1'].cmd('ip route add 10.2.0.0/16           via 10.20.13.2')  # P3→PE2
    net['p1'].cmd('ip route add 10.100.2.0/30         via 10.20.13.2')
    net['p1'].cmd('ip route add 10.3.0.0/16           via 10.20.12.2')  # P2→PE3
    net['p1'].cmd('ip route add 10.100.3.0/30         via 10.20.12.2')

    net['p2'].cmd('ip route add 10.3.0.0/16           via 10.10.32.1')  # PE3→CE3
    net['p2'].cmd('ip route add 10.100.3.0/30         via 10.10.32.1')
    net['p2'].cmd('ip route add 10.1.0.0/24           via 10.20.12.1')  # P1→PE1
    net['p2'].cmd('ip route add 10.100.1.0/30         via 10.20.12.1')
    net['p2'].cmd('ip route add 10.2.0.0/16           via 10.20.24.2')  # P4→PE2
    net['p2'].cmd('ip route add 10.100.2.0/30         via 10.20.24.2')

    net['p3'].cmd('ip route add 10.2.0.0/16           via 10.10.23.1')  # PE2→CE2
    net['p3'].cmd('ip route add 10.100.2.0/30         via 10.10.23.1')
    net['p3'].cmd('ip route add 10.1.0.0/24           via 10.10.13.1')  # PE1→CE1
    net['p3'].cmd('ip route add 10.100.1.0/30         via 10.10.13.1')
    net['p3'].cmd('ip route add 10.3.0.0/16           via 10.20.34.2')  # P4→PE3
    net['p3'].cmd('ip route add 10.100.3.0/30         via 10.20.34.2')

    net['p4'].cmd('ip route add 10.2.0.0/16           via 10.10.24.1')  # PE2→CE2
    net['p4'].cmd('ip route add 10.100.2.0/30         via 10.10.24.1')
    net['p4'].cmd('ip route add 10.3.0.0/16           via 10.10.34.1')  # PE3→CE3
    net['p4'].cmd('ip route add 10.100.3.0/30         via 10.10.34.1')
    net['p4'].cmd('ip route add 10.1.0.0/24           via 10.20.14.1')  # P1→PE1
    net['p4'].cmd('ip route add 10.100.1.0/30         via 10.20.14.1')

    info('\n*** Cấu hình hoàn tất!\n')
    _print_summary()


def _print_summary():
    lines = [
        ('Chi nhánh 1 – Flat',       'host1-4',  '10.1.0.0/24',   'ce1_lan–eth0→s_acc1'),
        ('Chi nhánh 2 – Admin',       'admin1-2', '10.2.10.0/24',  'vlan10@ce2_lan'),
        ('Chi nhánh 2 – Lab',         'lab1-2',   '10.2.20.0/24',  'vlan20@ce2_lan'),
        ('Chi nhánh 2 – Guest',       'guest1-2', '10.2.30.0/24',  'vlan30@ce2_lan'),
        ('Chi nhánh 3 – Web servers', 'web1-2',   '10.3.10.0/24',  'zone_web@ce3_lan'),
        ('Chi nhánh 3 – DNS servers', 'dns1-2',   '10.3.20.0/24',  'zone_dns@ce3_lan'),
        ('Chi nhánh 3 – DB  servers', 'db1-2',    '10.3.30.0/24',  'zone_db@ce3_lan'),
    ]
    info('\n' + '='*72 + '\n')
    info(f"  {'Chi nhánh':<30} {'Hosts':<12} {'Subnet':<16} {'Gateway'}\n")
    info('-'*72 + '\n')
    for chi, hosts, subnet, gw in lines:
        info(f"  {chi:<30} {hosts:<12} {subnet:<16} {gw}\n")
    info('='*72 + '\n')
    info('  Glue links: CE1↔ce1_lan=10.100.1.0/30 | CE2↔ce2_lan=10.100.2.0/30\n')
    info('              CE3↔ce3_lan=10.100.3.0/30\n')
    info('='*72 + '\n')


# ===========================================================================
# Kiểm tra kết nối end-to-end
# ===========================================================================
def test_end_to_end(net):
    """Ping test cross-branch qua backbone."""
    info('\n*** KIỂM TRA PING END-TO-END (cross-branch)\n')
    tests = [
        ('host1',  '10.1.0.102', 'host1→host2   [cùng branch1]'),
        ('host1',  '10.2.10.11', 'host1→admin1  [branch1→branch2]'),
        ('host1',  '10.3.10.11', 'host1→web1    [branch1→branch3]'),
        ('admin1', '10.3.20.21', 'admin1→dns1   [branch2→branch3]'),
        ('web1',   '10.2.30.31', 'web1→guest1   [branch3→branch2]'),
        ('db1',    '10.1.0.101', 'db1→host1     [branch3→branch1]'),
    ]
    for src, dst, desc in tests:
        out = net[src].cmd(f'ping -c 2 -W 2 {dst}')
        m = re.search(r'(\d+)% packet loss', out)
        loss = m.group(1) if m else '?'
        ok = '✓' if loss == '0' else '✗'
        info(f'  {ok} {desc:<40} loss={loss}%\n')


# ===========================================================================
# Entry point
# ===========================================================================
def run_full():
    setLogLevel('info')
    info('*** Khởi tạo Metro Full Topology\n')
    topo  = MetroFullTopo()
    net   = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()
    configure_full_network(net)
    test_end_to_end(net)
    info('\n*** CLI sẵn sàng. Gõ "exit" để thoát.\n')
    CLI(net)
    net.stop()


topos = {'metro_full': MetroFullTopo}

if __name__ == '__main__':
    run_full()
