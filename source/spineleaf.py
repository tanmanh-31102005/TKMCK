#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
THAM KHẢO – CHI NHÁNH 3: MẠNG 2 LỚP LEAF-SPINE
=============================================================================
Đề tài: Thiết kế và triển khai mạng Metro Ethernet sử dụng MPLS
        cho kết nối đa chi nhánh doanh nghiệp
Sinh viên: Huỳnh Văn Dũng – MSSV: 52300190
GVHD    : ThS. Lê Viết Thanh
Trường  : Đại học Tôn Đức Thắng – Khoa CNTT
=============================================================================

MỤC ĐÍCH FILE NÀY:
  File THAM KHẢO standalone cho Chi nhánh 3 – Mạng Leaf-Spine.
  Dùng để kiểm tra riêng kiến trúc Leaf-Spine trước khi tích hợp
  vào topology tổng thể (mpls_metro_topology.py).

KIẾN TRÚC LEAF-SPINE (2-TIER):
  ┌─────────────────────────────────────────────────┐
  │              CHI NHÁNH 3                        │
  │                                                 │
  │       ┌── b3sp1 ──── b3sp2 ──┐                 │
  │       │   (Spine1)  (Spine2)  │                 │
  │       │  ╱   ╲    ╱    ╲     │                 │
  │    b3lf1   b3lf2           [ce3] ──► PE3        │
  │   (Leaf1) (Leaf2)                               │
  │     │  │     │  │                               │
  │    h3a h3b  h3c h3d                             │
  │                                                 │
  │  Subnet: 10.3.0.0/24                            │
  └─────────────────────────────────────────────────┘

NGUYÊN LÝ LEAF-SPINE:
  ┌─ SPINE (Khung xương sống) ──────────────────────────┐
  │  • 2 switch spine: b3sp1, b3sp2                     │
  │  • Mọi Leaf đều kết nối với MỌI Spine (Full-Mesh)  │
  │  • Không có kết nối Leaf-Leaf trực tiếp             │
  │  • Băng thông cực cao (10–40 Gbps)                  │
  └─────────────────────────────────────────────────────┘
  ┌─ LEAF (Tầng truy cập) ──────────────────────────────┐
  │  • 2 switch leaf: b3lf1, b3lf2                      │
  │  • Kết nối host đầu cuối và CE router               │
  │  • b3lf1: h3a, h3b | b3lf2: h3c, h3d               │
  └─────────────────────────────────────────────────────┘

ĐẶC ĐIỂM LEAF-SPINE:
  + Băng thông rất cao (full bisection bandwidth)
  + Latency thấp nhất trong 3 kiến trúc (tối đa 2 hop giữa host)
  + Không phụ thuộc STP – dùng ECMP load balancing
  + Dễ mở rộng (thêm Leaf mà không ảnh hưởng đến Spine)
  - Chi phí cao hơn (nhiều link Spine-Leaf hơn)
  - Phức tạp hơn Flat nhưng đơn giản hơn 3-Tier

LƯU Ý VỀ ECMP TRONG MININET:
  Linux OVS mặc định dùng STP, không phải ECMP.
  Để đạt full ECMP thực sự cần dùng FRRouting hoặc OpenFlow controller.
  Trong mô phỏng này, STP sẽ block 1 đường Spine-Leaf nhưng vẫn
  duy trì tính đúng đắn của topology và kết nối.

CHẠY:
  sudo python3 spineleaf.py
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


# ===========================================================================
#  LinuxRouter: Host đóng vai Router với IP Forwarding bật sẵn
# ===========================================================================
class LinuxRouter(Host):
    """Router Linux – bật ip_forward để chuyển tiếp gói tin."""

    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        self.cmd('for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


def cleanup():
    """Dọn dẹp Mininet cũ."""
    info('*** Dọn dẹp Mininet cũ...\n')
    subprocess.run(['sudo', 'mn', '-c'], capture_output=True, timeout=30)


# ===========================================================================
#  XÂY DỰNG TOPOLOGY CHI NHÁNH 3 – LEAF-SPINE
# ===========================================================================
def build_branch3_leafspine():
    """
    Xây dựng standalone topology Leaf-Spine cho chi nhánh 3.

    Sơ đồ kết nối Full-Mesh Spine-Leaf:
      b3sp1 ─── b3sp2          (Inter-Spine link, 40 Gbps)
       │  ╲   ╱  │
       │   ╲ ╱   │
      b3lf1   b3lf2            (Mỗi Leaf kết nối CẢ 2 Spine, 10 Gbps)
       │  │     │  │
      h3a h3b  h3c h3d         (Host kết nối vào Leaf, 1 Gbps)

    BẢNG ĐỊA CHỈ IP:
    ┌───────────┬─────────────────┬────────────────────────┐
    │ Thiết bị  │ Interface       │ Địa chỉ IP              │
    ├───────────┼─────────────────┼────────────────────────┤
    │ h3a       │ h3a-eth0        │ 10.3.0.1/24             │
    │ h3b       │ h3b-eth0        │ 10.3.0.2/24             │
    │ h3c       │ h3c-eth0        │ 10.3.0.3/24             │
    │ h3d       │ h3d-eth0        │ 10.3.0.4/24             │
    │ b3lf1     │ (Leaf switch 1) │ –                       │
    │ b3lf2     │ (Leaf switch 2) │ –                       │
    │ b3sp1     │ (Spine switch 1)│ –                       │
    │ b3sp2     │ (Spine switch 2)│ –                       │
    │ ce3       │ ce3-lan         │ 10.3.0.254/24 (Gateway) │
    │           │ ce3-wan         │ 10.100.3.1/30 (→ PE3)   │
    └───────────┴─────────────────┴────────────────────────┘
    """
    cleanup()

    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)

    # ─── SPINE SWITCHES (Khung xương sống – tốc độ cực cao) ──────────────────
    info('*** [Spine] Tạo 2 Spine switch (lõi băng thông cao)...\n')
    # Spine 1 và Spine 2 – kết nối full mesh với tất cả Leaf
    # dpid riêng biệt để Mininet không bị trùng
    b3sp1 = net.addSwitch('b3sp1', cls=OVSSwitch, failMode='standalone',
                           dpid='0000000000000041')
    b3sp2 = net.addSwitch('b3sp2', cls=OVSSwitch, failMode='standalone',
                           dpid='0000000000000042')

    # ─── LEAF SWITCHES (Tầng truy cập) ───────────────────────────────────────
    info('*** [Leaf] Tạo 2 Leaf switch (truy cập host)...\n')
    # Leaf 1 và Leaf 2 – kết nối host đầu cuối
    b3lf1 = net.addSwitch('b3lf1', cls=OVSSwitch, failMode='standalone',
                           dpid='0000000000000051')
    b3lf2 = net.addSwitch('b3lf2', cls=OVSSwitch, failMode='standalone',
                           dpid='0000000000000052')

    # ─── HOST (đầu cuối) ─────────────────────────────────────────────────────
    info('*** Tạo 4 host cho chi nhánh 3...\n')
    h3a = net.addHost('h3a', ip='10.3.0.1/24', defaultRoute='via 10.3.0.254')
    h3b = net.addHost('h3b', ip='10.3.0.2/24', defaultRoute='via 10.3.0.254')
    h3c = net.addHost('h3c', ip='10.3.0.3/24', defaultRoute='via 10.3.0.254')
    h3d = net.addHost('h3d', ip='10.3.0.4/24', defaultRoute='via 10.3.0.254')

    # ─── CE3 và PE3 stub ─────────────────────────────────────────────────────
    info('*** Tạo CE3 (Customer Edge) kết nối PE3 stub...\n')
    ce3      = net.addHost('ce3',      cls=LinuxRouter, ip='10.3.0.254/24')
    pe3_stub = net.addHost('pe3_stub', cls=LinuxRouter, ip='10.100.3.2/30')

    # ─── KẾT NỐI: FULL-MESH Leaf-Spine ──────────────────────────────────────
    # ĐÂY là đặc trưng quan trọng nhất của Leaf-Spine:
    # Mỗi Leaf kết nối với TẤT CẢ Spine → không bao giờ có bottleneck
    # Tốc độ 10 Gbps – đường trục nội bộ Leaf-Spine
    info('*** Kết nối Full-Mesh Leaf ↔ Spine (mỗi Leaf nối cả 2 Spine)...\n')
    net.addLink(b3lf1, b3sp1, bw=10000)   # Leaf1 → Spine1
    net.addLink(b3lf1, b3sp2, bw=10000)   # Leaf1 → Spine2 (đây làm full-mesh)
    net.addLink(b3lf2, b3sp1, bw=10000)   # Leaf2 → Spine1
    net.addLink(b3lf2, b3sp2, bw=10000)   # Leaf2 → Spine2 (full-mesh)

    # ─── KẾT NỐI: Inter-Spine ────────────────────────────────────────────────
    # Đường nối giữa 2 Spine (dùng cho uplink ra CE/ngoài)
    # Tốc độ 40 Gbps – đường backbone Spine
    net.addLink(b3sp1, b3sp2, bw=40000)

    # ─── KẾT NỐI: Host → Leaf ────────────────────────────────────────────────
    # Tốc độ 1 Gbps – cổng server/workstation cao cấp
    info('*** Kết nối Host vào Leaf...\n')
    net.addLink(h3a, b3lf1, bw=1000)
    net.addLink(h3b, b3lf1, bw=1000)
    net.addLink(h3c, b3lf2, bw=1000)
    net.addLink(h3d, b3lf2, bw=1000)

    # ─── KẾT NỐI: Spine1 → CE3 (uplink ra ngoài) ────────────────────────────
    # CE3 kết nối vào Spine1 để ra ISP (10 Gbps uplink)
    # Trong thực tế, CE thường kết nối vào switch Border/Edge
    net.addLink(b3sp1, ce3, intfName2='ce3-lan', bw=10000)

    # ─── KẾT NỐI: CE3 → PE3 stub (Metro Ethernet link) ──────────────────────
    net.addLink(ce3, pe3_stub,
                intfName1='ce3-wan', intfName2='pe3-stub-ce3',
                bw=100, delay='5ms')

    # ─── Khởi động mạng ──────────────────────────────────────────────────────
    info('*** Khởi động mạng...\n')
    net.start()

    # ─── Cấu hình IP cho CE3 ─────────────────────────────────────────────────
    info('*** Cấu hình IP cho CE3...\n')
    ce3.cmd('ip addr flush dev ce3-lan 2>/dev/null')
    ce3.cmd('ip addr flush dev ce3-wan 2>/dev/null')
    ce3.cmd('ip addr add 10.3.0.254/24 dev ce3-lan')
    ce3.cmd('ip addr add 10.100.3.1/30  dev ce3-wan')
    ce3.cmd('ip link set ce3-lan up && ip link set ce3-wan up')

    pe3_stub.cmd('ip addr flush dev pe3-stub-ce3 2>/dev/null')
    pe3_stub.cmd('ip addr add 10.100.3.2/30 dev pe3-stub-ce3')
    pe3_stub.cmd('ip link set pe3-stub-ce3 up')

    # CE3 default route ra PE3
    ce3.cmd('ip route add default via 10.100.3.2 dev ce3-wan')

    info('*** Mạng Leaf-Spine Chi nhánh 3 đã sẵn sàng!\n')
    time.sleep(2)

    return net


def demonstrate_leaf_spine_paths(net):
    """
    Giải thích các đường đi trong mạng Leaf-Spine.
    Hàm này in ra thông tin để minh họa ECMP trong báo cáo.
    """
    info('\n--- ĐƯỜNG ĐI TRONG LEAF-SPINE ---\n')
    info('h3a (Leaf1) → h3c (Leaf2):\n')
    info('  Path 1: h3a → Leaf1 → Spine1 → Leaf2 → h3c\n')
    info('  Path 2: h3a → Leaf1 → Spine2 → Leaf2 → h3c\n')
    info('  → ECMP: Tải chia đều trên cả 2 đường (nếu dùng FRRouting)\n')
    info('  → STP: 1 đường bị block (trong mô phỏng OVS)\n')
    info('\nh3a (Leaf1) → h3b (Leaf1 – cùng Leaf):\n')
    info('  Path: h3a → Leaf1 → h3b (chỉ 1 hop, không qua Spine)\n')
    info('  → Đây là lợi thế lớn của Leaf-Spine: intra-Leaf traffic cực nhanh\n')


def run():
    """Hàm chính: khởi chạy topology và mở CLI."""
    net = build_branch3_leafspine()
    demonstrate_leaf_spine_paths(net)

    # In thông tin tóm tắt
    info('\n' + '='*65 + '\n')
    info('  CHI NHÁNH 3 – MẠNG LEAF-SPINE (2-TIER)\n')
    info('='*65 + '\n')
    info('  Spine  : b3sp1, b3sp2 (Full-Mesh, 40 Gbps inter-spine)\n')
    info('  Leaf   : b3lf1 (h3a,h3b) | b3lf2 (h3c,h3d)\n')
    info('  Links  : Leaf1↔Spine1 | Leaf1↔Spine2 | Leaf2↔Spine1 | Leaf2↔Spine2\n')
    info('  Subnet : 10.3.0.0/24\n')
    info('  Gateway: 10.3.0.254 (CE3)\n')
    info('  WAN    : CE3 → PE3_stub (10.100.3.0/30, 5ms)\n')
    info('\n  Số hop tối đa: Host → Leaf → Spine → Leaf → Host (2 hop)\n')
    info('  (So với 3-Tier: 4-5 hop, Flat: 1 hop trong cùng L2)\n')
    info('\n  Lệnh kiểm tra:\n')
    info('    mininet> pingall\n')
    info('    mininet> h3a ping h3d          (cross-Leaf qua Spine)\n')
    info('    mininet> h3a ping h3b          (cùng Leaf – 1 hop)\n')
    info('    mininet> h3a traceroute h3c    (xem số hop qua Spine)\n')
    info('    mininet> h3a ping 10.100.3.2   (ping đến PE3 giả)\n')
    info('    mininet> ce3 ip route          (bảng định tuyến CE3)\n')
    info('='*65 + '\n\n')

    CLI(net)
    net.stop()
    cleanup()


if __name__ == '__main__':
    setLogLevel('info')
    if os.geteuid() != 0:
        print('[LỖI] Cần chạy với quyền root: sudo python3 spineleaf.py')
        sys.exit(1)
    run()
