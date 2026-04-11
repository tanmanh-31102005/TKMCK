#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
ĐỀ TÀI: THIẾT KẾ VÀ TRIỂN KHAI MẠNG METRO ETHERNET SỬ DỤNG MPLS
        CHO KẾT NỐI ĐA CHI NHÁNH DOANH NGHIỆP
=============================================================================
Sinh viên: Huỳnh Văn Dũng - MSSV: 52300190
GVHD    : Lê Viết Thanh
Trường  : Đại học Tôn Đức Thắng – Khoa CNTT
=============================================================================

MÔ HÌNH TỔNG THỂ:
  ┌─────────────────────────────────────────────────────────────────┐
  │                    ISP MPLS BACKBONE                            │
  │                                                                 │
  │    PE1  ─── P1 ─── P2 ─── PE2                                  │
  │    │              │              │                              │
  │    │         P3 (Lõi)            │                              │
  │    │              │              │                              │
  │    PE3────────────┘              │                              │
  └─────────────────────────────────────────────────────────────────┘
       │                             │              │
      CE1                           CE2            CE3
       │                             │              │
  Chi nhánh 1               Chi nhánh 2      Chi nhánh 3
  (Flat Network)     (3-Tier: Core-Dist-Acc)  (Leaf-Spine)

MPLS Label Switching:
  - PE: Provider Edge – Push label vào gói IP khi vào backbone, Pop label khi ra
  - P : Provider (Core) – Swap label, chỉ nhìn nhãn, không xử lý IP header
  - CE: Customer Edge – Router phía khách hàng, giao tiếp bình thường bằng IP

Chạy:
  sudo python3 mpls_metro_topology.py
Hoặc:
  sudo mn --custom mpls_metro_topology.py --topo mpls_metro --controller=none
"""

import os
import sys
import time
import subprocess

from mininet.net import Mininet
from mininet.node import Host, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.topo import Topo


# ===========================================================================
# Lớp LinuxRouter: Host đóng vai Router Linux với IP Forwarding bật sẵn
# ===========================================================================
class LinuxRouter(Host):
    """
    Mô phỏng router bằng Linux host với IP forwarding.
    Đây là kỹ thuật phổ biến trong Mininet vì không có thiết bị router thật.
    """
    def config(self, **params):
        super().config(**params)
        # Bật IP forwarding – cho phép gói tin đi qua router
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        # Tắt RP filter để tránh drop gói tin hợp lệ
        self.cmd('for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


# ===========================================================================
#  Hàm dọn dẹp Mininet trước khi khởi động
# ===========================================================================
def cleanup_mininet():
    info('*** Dọn dẹp Mininet cũ (mn -c)...\n')
    subprocess.run(['sudo', 'mn', '-c'], capture_output=True, timeout=30)


# ===========================================================================
#  CHI NHÁNH 1: MẠNG PHẲNG (FLAT NETWORK)
#  ♦ Tất cả host chung 1 broadcast domain (Layer 2)
#  ♦ 1 Switch, N host, 1 CE router kết nối lên PE1
# ===========================================================================
def build_branch1_flat(net):
    """
    Xây dựng chi nhánh 1 – Mạng phẳng.
    Subnet: 10.1.0.0/24
    Host: h1a (10.1.0.1), h1b (10.1.0.2), h1c (10.1.0.3)
    CE1 : 10.1.0.254 (gateway cho branch 1)
         10.100.1.1  (kết nối lên PE1)
    """
    info('*** Tạo Chi nhánh 1: Mạng phẳng (Flat Network)\n')

    # --- Switch tầng truy cập duy nhất ---
    b1_sw = net.addSwitch('b1sw', cls=OVSSwitch, failMode='standalone', dpid='0000000000000001')

    # --- Các host tại chi nhánh 1 ---
    h1a = net.addHost('h1a', ip='10.1.0.1/24', defaultRoute='via 10.1.0.254')
    h1b = net.addHost('h1b', ip='10.1.0.2/24', defaultRoute='via 10.1.0.254')
    h1c = net.addHost('h1c', ip='10.1.0.3/24', defaultRoute='via 10.1.0.254')

    # --- CE1: Customer Edge Router của chi nhánh 1 ---
    ce1 = net.addHost('ce1', cls=LinuxRouter, ip='10.1.0.254/24')

    # --- Kết nối host vào switch ---
    net.addLink(h1a, b1_sw, bw=100)
    net.addLink(h1b, b1_sw, bw=100)
    net.addLink(h1c, b1_sw, bw=100)

    # --- Kết nối switch vào CE1 ---
    net.addLink(b1_sw, ce1, intfName2='ce1-lan', bw=1000)

    return {'ce': ce1, 'sw': b1_sw, 'hosts': [h1a, h1b, h1c]}


# ===========================================================================
#  CHI NHÁNH 2: MẠNG 3 LỚP (CORE – DISTRIBUTION – ACCESS)
#  ♦ Access: switch kết nối host
#  ♦ Distribution: switch gom access, thực hiện routing
#  ♦ Core: switch tốc độ cao kết nối ra CE
# ===========================================================================
def build_branch2_3tier(net):
    """
    Xây dựng chi nhánh 2 – Mạng 3 lớp truyền thống.
    Subnet: 10.2.0.0/24
    Host: h2a (10.2.0.1), h2b (10.2.0.2), h2c (10.2.0.3), h2d (10.2.0.4)
    CE2 : 10.2.0.254 (gateway), 10.100.2.1 (kết nối lên PE2)
    """
    info('*** Tạo Chi nhánh 2: Mạng 3 lớp (Core–Distribution–Access)\n')

    # === Tầng Access (Access Layer) – kết nối trực tiếp host ===
    acc1 = net.addSwitch('b2acc1', cls=OVSSwitch, failMode='standalone', dpid='0000000000000011')
    acc2 = net.addSwitch('b2acc2', cls=OVSSwitch, failMode='standalone', dpid='0000000000000012')

    # === Tầng Distribution – gom access switches ===
    dist1 = net.addSwitch('b2dist', cls=OVSSwitch, failMode='standalone', dpid='0000000000000021')

    # === Tầng Core – kết nối lên CE ===
    core1 = net.addSwitch('b2core', cls=OVSSwitch, failMode='standalone', dpid='0000000000000031')

    # --- Host (phân bổ 2 host mỗi access switch) ---
    h2a = net.addHost('h2a', ip='10.2.0.1/24', defaultRoute='via 10.2.0.254')
    h2b = net.addHost('h2b', ip='10.2.0.2/24', defaultRoute='via 10.2.0.254')
    h2c = net.addHost('h2c', ip='10.2.0.3/24', defaultRoute='via 10.2.0.254')
    h2d = net.addHost('h2d', ip='10.2.0.4/24', defaultRoute='via 10.2.0.254')

    # --- CE2 ---
    ce2 = net.addHost('ce2', cls=LinuxRouter, ip='10.2.0.254/24')

    # === Kết nối: Host → Access ===
    net.addLink(h2a, acc1, bw=100)
    net.addLink(h2b, acc1, bw=100)
    net.addLink(h2c, acc2, bw=100)
    net.addLink(h2d, acc2, bw=100)

    # === Kết nối: Access → Distribution ===
    net.addLink(acc1, dist1, bw=1000)
    net.addLink(acc2, dist1, bw=1000)

    # === Kết nối: Distribution → Core ===
    net.addLink(dist1, core1, bw=10000)

    # === Kết nối: Core → CE2 ===
    net.addLink(core1, ce2, intfName2='ce2-lan', bw=1000)

    return {'ce': ce2, 'hosts': [h2a, h2b, h2c, h2d], 'core': core1, 'dist': dist1}


# ===========================================================================
#  CHI NHÁNH 3: MẠNG 2 LỚP LEAF-SPINE
#  ♦ Spine: switch lõi (mọi Leaf đều kết nối lên mọi Spine – Full Mesh)
#  ♦ Leaf : switch truy cập, kết nối host
#  ♦ Không dùng STP – full ECMP, băng thông cực cao, latency thấp
# ===========================================================================
def build_branch3_leafspine(net):
    """
    Xây dựng chi nhánh 3 – Mạng Leaf-Spine.
    Subnet: 10.3.0.0/24
    Host: h3a (10.3.0.1), h3b (10.3.0.2), h3c (10.3.0.3), h3d (10.3.0.4)
    CE3 : 10.3.0.254 (gateway), 10.100.3.1 (kết nối lên PE3)

    Kiến trúc Leaf-Spine:
      Spine1 ─── Spine2
       │   ╲   ╱   │
      Leaf1   Leaf2
       │         │
     h3a,h3b  h3c,h3d
    """
    info('*** Tạo Chi nhánh 3: Mạng Leaf-Spine\n')

    # === Spine Switches – lõi băng thông cao ===
    spine1 = net.addSwitch('b3sp1', cls=OVSSwitch, failMode='standalone', dpid='0000000000000041')
    spine2 = net.addSwitch('b3sp2', cls=OVSSwitch, failMode='standalone', dpid='0000000000000042')

    # === Leaf Switches – truy cập ===
    leaf1 = net.addSwitch('b3lf1', cls=OVSSwitch, failMode='standalone', dpid='0000000000000051')
    leaf2 = net.addSwitch('b3lf2', cls=OVSSwitch, failMode='standalone', dpid='0000000000000052')

    # --- Host ---
    h3a = net.addHost('h3a', ip='10.3.0.1/24', defaultRoute='via 10.3.0.254')
    h3b = net.addHost('h3b', ip='10.3.0.2/24', defaultRoute='via 10.3.0.254')
    h3c = net.addHost('h3c', ip='10.3.0.3/24', defaultRoute='via 10.3.0.254')
    h3d = net.addHost('h3d', ip='10.3.0.4/24', defaultRoute='via 10.3.0.254')

    # --- CE3 ---
    ce3 = net.addHost('ce3', cls=LinuxRouter, ip='10.3.0.254/24')

    # === Full-Mesh Spine – Leaf (mỗi Leaf nối cả 2 Spine) ===
    net.addLink(leaf1, spine1, bw=10000)
    net.addLink(leaf1, spine2, bw=10000)
    net.addLink(leaf2, spine1, bw=10000)
    net.addLink(leaf2, spine2, bw=10000)

    # === Inter-Spine link (uplink) ===
    net.addLink(spine1, spine2, bw=40000)

    # === Host → Leaf ===
    net.addLink(h3a, leaf1, bw=1000)
    net.addLink(h3b, leaf1, bw=1000)
    net.addLink(h3c, leaf2, bw=1000)
    net.addLink(h3d, leaf2, bw=1000)

    # === Spine1 → CE3 (uplink ra ngoài) ===
    net.addLink(spine1, ce3, intfName2='ce3-lan', bw=10000)

    return {'ce': ce3, 'hosts': [h3a, h3b, h3c, h3d]}


# ===========================================================================
#  ISP MPLS BACKBONE
#  ♦ PE1, PE2, PE3: Provider Edge – kết nối CE, thực hiện Push/Pop label
#  ♦ P1, P2 (Core): Provider – chỉ Swap label, không xử lý IP
#  ♦ Giao thức: OSPF (underlay) + MPLS label switching (mô phỏng bằng ip route)
#
#  Topology backbone:
#    PE1 ── P1 ── P2 ── PE2
#             │
#            PE3
# ===========================================================================
def build_mpls_backbone(net):
    """
    Xây dựng MPLS backbone của ISP.

    Địa chỉ backbone (point-to-point /30):
      PE1–P1: 10.0.12.0/30  (PE1=.1, P1=.2)
      PE2–P2: 10.0.23.0/30  (PE2=.1, P2=.2)
      PE3–P1: 10.0.31.0/30  (PE3=.1, P1=.2)
      P1–P2 : 10.0.99.0/30  (P1=.1, P2=.2)

    Địa chỉ CE–PE (customer-facing):
      CE1–PE1: 10.100.1.0/30 (CE1=.1, PE1=.2)
      CE2–PE2: 10.100.2.0/30 (CE2=.1, PE2=.2)
      CE3–PE3: 10.100.3.0/30 (CE3=.1, PE3=.2)
    """
    info('*** Tạo MPLS Backbone (PE1, PE2, PE3, P1, P2)\n')

    # --- PE Routers (Provider Edge) ---
    pe1 = net.addHost('pe1', cls=LinuxRouter, ip='10.0.12.1/30')
    pe2 = net.addHost('pe2', cls=LinuxRouter, ip='10.0.23.1/30')
    pe3 = net.addHost('pe3', cls=LinuxRouter, ip='10.0.31.1/30')

    # --- P Routers (Provider/Core) ---
    p1 = net.addHost('p1', cls=LinuxRouter, ip='10.0.12.2/30')
    p2 = net.addHost('p2', cls=LinuxRouter, ip='10.0.23.2/30')

    # === Link backbone P1–P2 ===
    net.addLink(p1, p2,
                intfName1='p1-p2', intfName2='p2-p1',
                bw=10000, delay='1ms')

    # === Link PE–P ===
    net.addLink(pe1, p1,
                intfName1='pe1-p1', intfName2='p1-pe1',
                bw=1000, delay='2ms')
    net.addLink(pe2, p2,
                intfName1='pe2-p2', intfName2='p2-pe2',
                bw=1000, delay='2ms')
    net.addLink(pe3, p1,
                intfName1='pe3-p1', intfName2='p1-pe3',
                bw=1000, delay='2ms')

    return {
        'pe1': pe1, 'pe2': pe2, 'pe3': pe3,
        'p1': p1, 'p2': p2
    }


# ===========================================================================
#  KẾT NỐI CE–PE (Customer Edge – Provider Edge)
# ===========================================================================
def connect_ce_pe(net, branch_dict, backbone_dict):
    """
    Kết nối mỗi CE router của chi nhánh với PE router tương ứng.
    Link CE–PE mô phỏng đường Metro Ethernet (kiểu E-Line).
    """
    info('*** Kết nối CE–PE (Metro Ethernet access links)\n')

    ce1 = branch_dict['b1']['ce']
    ce2 = branch_dict['b2']['ce']
    ce3 = branch_dict['b3']['ce']
    pe1 = backbone_dict['pe1']
    pe2 = backbone_dict['pe2']
    pe3 = backbone_dict['pe3']

    # CE1 – PE1: 10.100.1.0/30
    net.addLink(ce1, pe1,
                intfName1='ce1-wan', intfName2='pe1-ce1',
                bw=100, delay='5ms')

    # CE2 – PE2: 10.100.2.0/30
    net.addLink(ce2, pe2,
                intfName1='ce2-wan', intfName2='pe2-ce2',
                bw=100, delay='5ms')

    # CE3 – PE3: 10.100.3.0/30
    net.addLink(ce3, pe3,
                intfName1='ce3-wan', intfName2='pe3-ce3',
                bw=100, delay='5ms')


# ===========================================================================
#  CẤU HÌNH ĐỊA CHỈ IP SAU KHI START
# ===========================================================================
def configure_ip_addresses(net):
    """
    Gán địa chỉ IP cho tất cả interface sau khi net.start().
    Cần làm thủ công vì Mininet không tự xử lý multi-interface router.
    """
    info('*** Cấu hình địa chỉ IP cho tất cả thiết bị...\n')

    # ─── CE1 ───────────────────────────────────────────────────────────────
    ce1 = net.get('ce1')
    ce1.cmd('ip addr flush dev ce1-lan 2>/dev/null')
    ce1.cmd('ip addr flush dev ce1-wan 2>/dev/null')
    ce1.cmd('ip addr add 10.1.0.254/24  dev ce1-lan')
    ce1.cmd('ip addr add 10.100.1.1/30  dev ce1-wan')
    ce1.cmd('ip link set ce1-lan up; ip link set ce1-wan up')

    # ─── CE2 ───────────────────────────────────────────────────────────────
    ce2 = net.get('ce2')
    ce2.cmd('ip addr flush dev ce2-lan 2>/dev/null')
    ce2.cmd('ip addr flush dev ce2-wan 2>/dev/null')
    ce2.cmd('ip addr add 10.2.0.254/24  dev ce2-lan')
    ce2.cmd('ip addr add 10.100.2.1/30  dev ce2-wan')
    ce2.cmd('ip link set ce2-lan up; ip link set ce2-wan up')

    # ─── CE3 ───────────────────────────────────────────────────────────────
    ce3 = net.get('ce3')
    ce3.cmd('ip addr flush dev ce3-lan 2>/dev/null')
    ce3.cmd('ip addr flush dev ce3-wan 2>/dev/null')
    ce3.cmd('ip addr add 10.3.0.254/24  dev ce3-lan')
    ce3.cmd('ip addr add 10.100.3.1/30  dev ce3-wan')
    ce3.cmd('ip link set ce3-lan up; ip link set ce3-wan up')

    # ─── PE1 ───────────────────────────────────────────────────────────────
    pe1 = net.get('pe1')
    pe1.cmd('ip addr flush dev pe1-ce1 2>/dev/null')
    pe1.cmd('ip addr flush dev pe1-p1  2>/dev/null')
    pe1.cmd('ip addr add 10.100.1.2/30  dev pe1-ce1')
    pe1.cmd('ip addr add 10.0.12.1/30   dev pe1-p1')
    pe1.cmd('ip link set pe1-ce1 up; ip link set pe1-p1 up')

    # ─── PE2 ───────────────────────────────────────────────────────────────
    pe2 = net.get('pe2')
    pe2.cmd('ip addr flush dev pe2-ce2 2>/dev/null')
    pe2.cmd('ip addr flush dev pe2-p2  2>/dev/null')
    pe2.cmd('ip addr add 10.100.2.2/30  dev pe2-ce2')
    pe2.cmd('ip addr add 10.0.23.1/30   dev pe2-p2')
    pe2.cmd('ip link set pe2-ce2 up; ip link set pe2-p2 up')

    # ─── PE3 ───────────────────────────────────────────────────────────────
    pe3 = net.get('pe3')
    pe3.cmd('ip addr flush dev pe3-ce3 2>/dev/null')
    pe3.cmd('ip addr flush dev pe3-p1  2>/dev/null')
    pe3.cmd('ip addr add 10.100.3.2/30  dev pe3-ce3')
    pe3.cmd('ip addr add 10.0.31.1/30   dev pe3-p1')
    pe3.cmd('ip link set pe3-ce3 up; ip link set pe3-p1 up')

    # ─── P1 (Provider Core) ─────────────────────────────────────────────────
    p1 = net.get('p1')
    p1.cmd('ip addr flush dev p1-pe1 2>/dev/null')
    p1.cmd('ip addr flush dev p1-pe3 2>/dev/null')
    p1.cmd('ip addr flush dev p1-p2  2>/dev/null')
    p1.cmd('ip addr add 10.0.12.2/30   dev p1-pe1')
    p1.cmd('ip addr add 10.0.31.2/30   dev p1-pe3')
    p1.cmd('ip addr add 10.0.99.1/30   dev p1-p2')
    p1.cmd('ip link set p1-pe1 up; ip link set p1-pe3 up; ip link set p1-p2 up')

    # ─── P2 (Provider Core) ─────────────────────────────────────────────────
    p2 = net.get('p2')
    p2.cmd('ip addr flush dev p2-pe2 2>/dev/null')
    p2.cmd('ip addr flush dev p2-p1  2>/dev/null')
    p2.cmd('ip addr add 10.0.23.2/30   dev p2-pe2')
    p2.cmd('ip addr add 10.0.99.2/30   dev p2-p1')
    p2.cmd('ip link set p2-pe2 up; ip link set p2-p1 up')

    info('*** Địa chỉ IP đã được cấu hình.\n')


# ===========================================================================
#  MÔ PHỎNG MPLS: LABEL SWITCHING (PUSH – SWAP – POP)
#  Vì Mininet/OVS không hỗ trợ nhãn MPLS thực, ta mô phỏng bằng:
#    1. Định tuyến tĩnh (ip route) theo kiểu Transit
#    2. Mô tả rõ vai trò Push/Swap/Pop tại từng router
#
#  MPLS Label Plan (ví dụ):
#    PE1 → PE2: Label 100 (push tại PE1, swap tại P1→P2, pop tại PE2)
#    PE1 → PE3: Label 200 (push tại PE1, swap/drop tại P1, pop tại PE3)
#    PE2 → PE1: Label 300 (push tại PE2, swap tại P2→P1, pop tại PE1)
#    PE2 → PE3: Label 400 (push tại PE2, swap tại P2→P1, pop tại PE3)
#    PE3 → PE1: Label 500 (push tại PE3, swap tại P1, pop tại PE1)
#    PE3 → PE2: Label 600 (push tại PE3, swap tại P1→P2, pop tại PE2)
# ===========================================================================
def configure_mpls_simulation(net):
    """
    Mô phỏng MPLS Label Switching bằng định tuyến tĩnh Linux.
    Trong thực tế sẽ dùng iproute2 MPLS hoặc FRRouting với LDP.
    Ở đây ta mô phỏng logic: gói tin đi đúng đường như MPLS label switching.

    Để dùng MPLS kernel thực sự cần:
      modprobe mpls_router
      modprobe mpls_iptunnel
      sysctl -w net.mpls.platform_labels=1000
    """
    info('\n=== CẤU HÌNH MPLS BACKBONE (Mô phỏng Label Switching) ===\n')

    # Thử bật MPLS kernel module (nếu có)
    os.system('modprobe mpls_router 2>/dev/null')
    os.system('modprobe mpls_iptunnel 2>/dev/null')

    ce1 = net.get('ce1')
    ce2 = net.get('ce2')
    ce3 = net.get('ce3')
    pe1 = net.get('pe1')
    pe2 = net.get('pe2')
    pe3 = net.get('pe3')
    p1  = net.get('p1')
    p2  = net.get('p2')

    # ─────────────────────────────────────────────────────────────────────
    # BƯỚC 1: Routing nội bộ backbone (OSPF-like với static routes)
    # P1 phải biết đường đến PE2 qua P2, và biết PE1, PE3 là direct
    # ─────────────────────────────────────────────────────────────────────

    # P1 routing table
    p1.cmd('ip route add 10.0.23.0/30 via 10.0.99.2 dev p1-p2')   # P1→P2→PE2
    p1.cmd('ip route add 10.100.1.0/30 dev p1-pe1')                 # P1→PE1 (direct)
    p1.cmd('ip route add 10.100.3.0/30 dev p1-pe3')                 # P1→PE3 (direct)
    p1.cmd('ip route add 10.100.2.0/30 via 10.0.99.2 dev p1-p2')   # P1→P2→PE2→CE2

    # P2 routing table
    p2.cmd('ip route add 10.0.12.0/30 via 10.0.99.1 dev p2-p1')   # P2→P1→PE1
    p2.cmd('ip route add 10.0.31.0/30 via 10.0.99.1 dev p2-p1')   # P2→P1→PE3
    p2.cmd('ip route add 10.100.1.0/30 via 10.0.99.1 dev p2-p1')  # P2→P1→PE1
    p2.cmd('ip route add 10.100.3.0/30 via 10.0.99.1 dev p2-p1')  # P2→P1→PE3
    p2.cmd('ip route add 10.100.2.0/30 dev p2-pe2')                 # P2→PE2 (direct)

    # ─────────────────────────────────────────────────────────────────────
    # BƯỚC 2: PE Routing (PUSH label simulation – quảng bá mạng khách hàng)
    # PE1 biết mạng chi nhánh 2, 3 qua backbone
    # ─────────────────────────────────────────────────────────────────────

    # --- PE1 routing ---
    # Biết chi nhánh 2 (10.2.0.0/24) qua backbone P1→P2→PE2
    pe1.cmd('ip route add 10.100.2.0/30 via 10.0.12.2 dev pe1-p1')  # next-hop P1
    pe1.cmd('ip route add 10.2.0.0/24   via 10.0.12.2 dev pe1-p1')  # route to branch2
    # Biết chi nhánh 3 (10.3.0.0/24) qua P1→PE3
    pe1.cmd('ip route add 10.100.3.0/30 via 10.0.12.2 dev pe1-p1')
    pe1.cmd('ip route add 10.3.0.0/24   via 10.0.12.2 dev pe1-p1')  # route to branch3
    # Route về backbone cho P routers
    pe1.cmd('ip route add 10.0.99.0/30  via 10.0.12.2 dev pe1-p1')
    pe1.cmd('ip route add 10.0.23.0/30  via 10.0.12.2 dev pe1-p1')
    pe1.cmd('ip route add 10.0.31.0/30  via 10.0.12.2 dev pe1-p1')

    # --- PE2 routing ---
    pe2.cmd('ip route add 10.100.1.0/30 via 10.0.23.2 dev pe2-p2')
    pe2.cmd('ip route add 10.1.0.0/24   via 10.0.23.2 dev pe2-p2')  # to branch1
    pe2.cmd('ip route add 10.100.3.0/30 via 10.0.23.2 dev pe2-p2')
    pe2.cmd('ip route add 10.3.0.0/24   via 10.0.23.2 dev pe2-p2')  # to branch3
    pe2.cmd('ip route add 10.0.99.0/30  via 10.0.23.2 dev pe2-p2')
    pe2.cmd('ip route add 10.0.12.0/30  via 10.0.23.2 dev pe2-p2')
    pe2.cmd('ip route add 10.0.31.0/30  via 10.0.23.2 dev pe2-p2')

    # --- PE3 routing ---
    pe3.cmd('ip route add 10.100.1.0/30 via 10.0.31.2 dev pe3-p1')
    pe3.cmd('ip route add 10.1.0.0/24   via 10.0.31.2 dev pe3-p1')  # to branch1
    pe3.cmd('ip route add 10.100.2.0/30 via 10.0.31.2 dev pe3-p1')
    pe3.cmd('ip route add 10.2.0.0/24   via 10.0.31.2 dev pe3-p1')  # to branch2
    pe3.cmd('ip route add 10.0.99.0/30  via 10.0.31.2 dev pe3-p1')
    pe3.cmd('ip route add 10.0.12.0/30  via 10.0.31.2 dev pe3-p1')
    pe3.cmd('ip route add 10.0.23.0/30  via 10.0.31.2 dev pe3-p1')

    # ─────────────────────────────────────────────────────────────────────
    # BƯỚC 3: CE Routing – default route hướng về PE
    # ─────────────────────────────────────────────────────────────────────
    ce1.cmd('ip route add 10.2.0.0/24  via 10.100.1.2 dev ce1-wan')
    ce1.cmd('ip route add 10.3.0.0/24  via 10.100.1.2 dev ce1-wan')
    ce1.cmd('ip route add 10.0.12.0/30 via 10.100.1.2 dev ce1-wan')

    ce2.cmd('ip route add 10.1.0.0/24  via 10.100.2.2 dev ce2-wan')
    ce2.cmd('ip route add 10.3.0.0/24  via 10.100.2.2 dev ce2-wan')
    ce2.cmd('ip route add 10.0.23.0/30 via 10.100.2.2 dev ce2-wan')

    ce3.cmd('ip route add 10.1.0.0/24  via 10.100.3.2 dev ce3-wan')
    ce3.cmd('ip route add 10.2.0.0/24  via 10.100.3.2 dev ce3-wan')
    ce3.cmd('ip route add 10.0.31.0/30 via 10.100.3.2 dev ce3-wan')

    info('*** MPLS backbone routing đã hoàn tất.\n')

    # ─────────────────────────────────────────────────────────────────────
    # BƯỚC 4: Mô phỏng MPLS Label với iproute2 MPLS (nếu kernel hỗ trợ)
    # ─────────────────────────────────────────────────────────────────────
    info('*** Kiểm tra và cấu hình MPLS kernel labels...\n')
    try:
        # Bật MPLS trên các interface của P routers
        for router_name, intfs in [
            ('p1', ['p1-pe1', 'p1-pe3', 'p1-p2']),
            ('p2', ['p2-pe2', 'p2-p1']),
            ('pe1', ['pe1-p1', 'pe1-ce1']),
            ('pe2', ['pe2-p2', 'pe2-ce2']),
            ('pe3', ['pe3-p1', 'pe3-ce3']),
        ]:
            r = net.get(router_name)
            r.cmd('sysctl -w net.mpls.platform_labels=1000 2>/dev/null')
            for intf in intfs:
                r.cmd(f'sysctl -w net.mpls.conf.{intf}.input=1 2>/dev/null')

        # === MPLS Label Routes (Push/Swap/Pop) ===
        # Đường PE1 → PE2 (qua P1 → P2): Label 100
        # Push: PE1 gắn label 100 cho traffic đến 10.2.0.0/24
        pe1.cmd('ip -f mpls route add 100 via inet 10.0.12.2 dev pe1-p1 2>/dev/null')
        # Swap: P1 nhận label 100, đổi thành label 200 chuyển sang P2
        p1.cmd('ip -f mpls route add 100 as 200 via inet 10.0.99.2 dev p1-p2 2>/dev/null')
        # Swap: P2 nhận label 200, đổi thành label 300 chuyển sang PE2
        p2.cmd('ip -f mpls route add 200 as 300 via inet 10.0.23.1 dev p2-pe2 2>/dev/null')
        # Pop (Penultimate Hop Popping): PE2 pop label, chuyển gói IP đến CE2
        pe2.cmd('ip -f mpls route add 300 via inet 10.100.2.1 dev pe2-ce2 2>/dev/null')

        info('*** MPLS labels đã cấu hình (PE1→PE2: label 100→200→300→pop)\n')
    except Exception as e:
        info(f'*** Lưu ý: MPLS kernel labels không khả dụng ({e}). Đang dùng routing tĩnh thay thế.\n')


# ===========================================================================
#  BUILD NETWORK TỔNG THỂ
# ===========================================================================
def build_net():
    """Hàm chính xây dựng toàn bộ topology."""
    cleanup_mininet()

    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)

    # Xây dựng 3 chi nhánh
    b1 = build_branch1_flat(net)
    b2 = build_branch2_3tier(net)
    b3 = build_branch3_leafspine(net)

    # Xây dựng MPLS backbone
    backbone = build_mpls_backbone(net)

    # Kết nối CE–PE
    connect_ce_pe(net,
                  branch_dict={'b1': b1, 'b2': b2, 'b3': b3},
                  backbone_dict=backbone)

    info('*** Khởi động mạng...\n')
    net.start()

    # Cấu hình IP sau khi start
    configure_ip_addresses(net)

    # Mô phỏng MPLS
    configure_mpls_simulation(net)

    # Chờ ổn định
    info('*** Đợi mạng ổn định (3s)...\n')
    time.sleep(3)

    return net


# ===========================================================================
#  HIỂN THỊ SƠ ĐỒ VÀ KIỂM TRA KẾT NỐI
# ===========================================================================
def print_network_info(net):
    info('\n' + '='*70 + '\n')
    info('  METRO ETHERNET MPLS BACKBONE – KẾT NỐI 3 CHI NHÁNH\n')
    info('='*70 + '\n')
    info('\n  SƠ ĐỒ ĐỊA CHỈ IP:\n')
    info('  Chi nhánh 1 (Flat):        10.1.0.0/24  – CE1: 10.1.0.254\n')
    info('  Chi nhánh 2 (3-tier):      10.2.0.0/24  – CE2: 10.2.0.254\n')
    info('  Chi nhánh 3 (Leaf-Spine):  10.3.0.0/24  – CE3: 10.3.0.254\n')
    info('\n  BACKBONE MPLS (ISP):\n')
    info('  PE1–P1:  10.0.12.0/30   PE1=.1  P1=.2\n')
    info('  PE2–P2:  10.0.23.0/30   PE2=.1  P2=.2\n')
    info('  PE3–P1:  10.0.31.0/30   PE3=.1  P1=.2\n')
    info('  P1–P2:   10.0.99.0/30   P1=.1   P2=.2\n')
    info('\n  LINK CE–PE:\n')
    info('  CE1–PE1: 10.100.1.0/30  CE1=.1  PE1=.2\n')
    info('  CE2–PE2: 10.100.2.0/30  CE2=.1  PE2=.2\n')
    info('  CE3–PE3: 10.100.3.0/30  CE3=.1  PE3=.2\n')
    info('\n  LỆNH KIỂM TRA:\n')
    info('  mininet> h1a ping h2a       (Branch1 ping Branch2)\n')
    info('  mininet> h1a ping h3a       (Branch1 ping Branch3)\n')
    info('  mininet> h2a ping h3a       (Branch2 ping Branch3)\n')
    info('  mininet> pingall            (Kiểm tra toàn bộ)\n')
    info('  mininet> net                (Xem topology)\n')
    info('  mininet> nodes              (Liệt kê tất cả node)\n')
    info('='*70 + '\n\n')


# ===========================================================================
#  MAIN
# ===========================================================================
def run():
    net = build_net()
    print_network_info(net)
    CLI(net)
    net.stop()
    cleanup_mininet()


# Đăng ký topo với Mininet để dùng --custom
topos = {'mpls_metro': (lambda: None)}  # placeholder


if __name__ == '__main__':
    setLogLevel('info')
    if os.geteuid() != 0:
        print('[LỖI] Cần chạy với quyền root: sudo python3 mpls_metro_topology.py')
        sys.exit(1)
    run()
