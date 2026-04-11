#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
THAM KHẢO – CHI NHÁNH 2: MẠNG 3 LỚP (CORE – DISTRIBUTION – ACCESS)
=============================================================================
Đề tài: Thiết kế và triển khai mạng Metro Ethernet sử dụng MPLS
        cho kết nối đa chi nhánh doanh nghiệp
Sinh viên: Huỳnh Văn Dũng – MSSV: 52300190
GVHD    : ThS. Lê Viết Thanh
Trường  : Đại học Tôn Đức Thắng – Khoa CNTT
=============================================================================

MỤC ĐÍCH FILE NÀY:
  File THAM KHẢO standalone cho Chi nhánh 2 – Mạng 3 lớp truyền thống.
  Dùng để kiểm tra riêng kiến trúc 3 lớp trước khi tích hợp vào
  topology tổng thể (mpls_metro_topology.py).

KIẾN TRÚC 3 LỚP (HIERARCHICAL / 3-TIER):
  ┌─────────────────────────────────────────────────────┐
  │                  CHI NHÁNH 2                        │
  │                                                     │
  │  h2a ─┐           ┌── b2acc1 ─── b2dist            │
  │  h2b ─┴─ b2acc1 ──┤              │                  │
  │                    └── b2acc2 ─── b2dist ─── b2core │──► PE2
  │  h2c ─┐                          │                  │
  │  h2d ─┴─ b2acc2 ─────────────────┘                  │
  │                                                     │
  │  Access → Distribution → Core → CE2                 │
  │  Subnet: 10.2.0.0/24                                │
  └─────────────────────────────────────────────────────┘

CÁC LỚP (TIERS):
  ┌─ ACCESS (Tầng truy cập) ──────────────────────────────┐
  │  • 2 switch access: b2acc1, b2acc2                    │
  │  • Kết nối trực tiếp với host đầu cuối (100 Mbps)     │
  │  • b2acc1: h2a, h2b | b2acc2: h2c, h2d               │
  └───────────────────────────────────────────────────────┘
  ┌─ DISTRIBUTION (Tầng phân phối) ───────────────────────┐
  │  • 1 switch distribution: b2dist                      │
  │  • Kết nối các switch Access (1 Gbps uplink)          │
  │  • Nơi áp dụng chính sách định tuyến, QoS             │
  └───────────────────────────────────────────────────────┘
  ┌─ CORE (Tầng lõi) ─────────────────────────────────────┐
  │  • 1 switch core: b2core                              │
  │  • Đường truyền tốc độ cao (10 Gbps)                  │
  │  • Kết nối CE2 đi ra ISP backbone                     │
  └───────────────────────────────────────────────────────┘

ĐẶC ĐIỂM MẠNG 3 LỚP:
  + Phân cấp rõ ràng, dễ quản lý
  + Phù hợp với doanh nghiệp trung bình đến lớn
  + Áp dụng được STP, VLAN, chính sách bảo mật tại Distribution
  - Nhiều hop hơn → latency cao hơn Flat/Leaf-Spine (3–5 hop)
  - Phụ thuộc STP → có thể block đường dự phòng

CHẠY:
  sudo python3 coreditrubutionaccess.py
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
    """Router Linux – bật ip_forward để chuyển tiếp gói tin giữa các interface."""

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
#  XÂY DỰNG TOPOLOGY CHI NHÁNH 2 – 3 LỚP
# ===========================================================================
def build_branch2_3tier():
    """
    Xây dựng standalone topology mạng 3 lớp cho chi nhánh 2.

    BẢNG ĐỊA CHỈ IP:
    ┌───────────┬─────────────────┬────────────────────────┐
    │ Thiết bị  │ Interface       │ Địa chỉ IP              │
    ├───────────┼─────────────────┼────────────────────────┤
    │ h2a       │ h2a-eth0        │ 10.2.0.1/24             │
    │ h2b       │ h2b-eth0        │ 10.2.0.2/24             │
    │ h2c       │ h2c-eth0        │ 10.2.0.3/24             │
    │ h2d       │ h2d-eth0        │ 10.2.0.4/24             │
    │ b2acc1    │ (Access switch) │ –                       │
    │ b2acc2    │ (Access switch) │ –                       │
    │ b2dist    │ (Distribution)  │ –                       │
    │ b2core    │ (Core switch)   │ –                       │
    │ ce2       │ ce2-lan         │ 10.2.0.254/24 (Gateway) │
    │           │ ce2-wan         │ 10.100.2.1/30 (→ PE2)   │
    └───────────┴─────────────────┴────────────────────────┘
    """
    cleanup()

    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)

    # ─── TẦNG ACCESS (Access Layer) ──────────────────────────────────────────
    info('*** [Tầng Access] Tạo 2 switch truy cập...\n')
    # b2acc1: switch access 1, kết nối h2a, h2b
    b2acc1 = net.addSwitch('b2acc1', cls=OVSSwitch, failMode='standalone',
                            dpid='0000000000000011')
    # b2acc2: switch access 2, kết nối h2c, h2d
    b2acc2 = net.addSwitch('b2acc2', cls=OVSSwitch, failMode='standalone',
                            dpid='0000000000000012')

    # ─── TẦNG DISTRIBUTION (Distribution Layer) ──────────────────────────────
    info('*** [Tầng Distribution] Tạo switch phân phối...\n')
    # b2dist: nhận uplink từ cả 2 access switch, gom lưu lượng lên core
    b2dist = net.addSwitch('b2dist', cls=OVSSwitch, failMode='standalone',
                            dpid='0000000000000021')

    # ─── TẦNG CORE (Core Layer) ──────────────────────────────────────────────
    info('*** [Tầng Core] Tạo switch lõi tốc độ cao...\n')
    # b2core: chuyển mạch tốc độ cao, kết nối CE2 đi ra ISP
    b2core = net.addSwitch('b2core', cls=OVSSwitch, failMode='standalone',
                            dpid='0000000000000031')

    # ─── HOST (đầu cuối) ─────────────────────────────────────────────────────
    info('*** Tạo 4 host cho chi nhánh 2...\n')
    # 4 host, phân bổ đều 2 host mỗi switch access
    h2a = net.addHost('h2a', ip='10.2.0.1/24', defaultRoute='via 10.2.0.254')
    h2b = net.addHost('h2b', ip='10.2.0.2/24', defaultRoute='via 10.2.0.254')
    h2c = net.addHost('h2c', ip='10.2.0.3/24', defaultRoute='via 10.2.0.254')
    h2d = net.addHost('h2d', ip='10.2.0.4/24', defaultRoute='via 10.2.0.254')

    # ─── CE2 và PE2 stub ─────────────────────────────────────────────────────
    info('*** Tạo CE2 (Customer Edge) và PE2 stub...\n')
    ce2      = net.addHost('ce2',      cls=LinuxRouter, ip='10.2.0.254/24')
    pe2_stub = net.addHost('pe2_stub', cls=LinuxRouter, ip='10.100.2.2/30')

    # ─── KẾT NỐI: Host → Access ──────────────────────────────────────────────
    # Tốc độ 100 Mbps – mô phỏng cổng người dùng thông thường
    net.addLink(h2a, b2acc1, bw=100)
    net.addLink(h2b, b2acc1, bw=100)
    net.addLink(h2c, b2acc2, bw=100)
    net.addLink(h2d, b2acc2, bw=100)

    # ─── KẾT NỐI: Access → Distribution ─────────────────────────────────────
    # Uplink 1 Gbps – đường truy cập lên tầng phân phối
    net.addLink(b2acc1, b2dist, bw=1000)
    net.addLink(b2acc2, b2dist, bw=1000)

    # ─── KẾT NỐI: Distribution → Core ───────────────────────────────────────
    # Uplink 10 Gbps – đường trục tốc độ cao
    net.addLink(b2dist, b2core, bw=10000)

    # ─── KẾT NỐI: Core → CE2 ────────────────────────────────────────────────
    # Uplink 1 Gbps từ Core lên CE2 (ra ISP)
    net.addLink(b2core, ce2, intfName2='ce2-lan', bw=1000)

    # ─── KẾT NỐI: CE2 → PE2 stub (Metro Ethernet link) ──────────────────────
    # 100 Mbps, delay 5 ms – mô phỏng đường Metro Ethernet đến ISP
    net.addLink(ce2, pe2_stub,
                intfName1='ce2-wan', intfName2='pe2-stub-ce2',
                bw=100, delay='5ms')

    # ─── Khởi động mạng ──────────────────────────────────────────────────────
    info('*** Khởi động mạng...\n')
    net.start()

    # ─── Cấu hình IP cho CE2 ─────────────────────────────────────────────────
    info('*** Cấu hình IP cho CE2...\n')
    ce2.cmd('ip addr flush dev ce2-lan 2>/dev/null')
    ce2.cmd('ip addr flush dev ce2-wan 2>/dev/null')
    ce2.cmd('ip addr add 10.2.0.254/24 dev ce2-lan')
    ce2.cmd('ip addr add 10.100.2.1/30  dev ce2-wan')
    ce2.cmd('ip link set ce2-lan up && ip link set ce2-wan up')

    pe2_stub.cmd('ip addr flush dev pe2-stub-ce2 2>/dev/null')
    pe2_stub.cmd('ip addr add 10.100.2.2/30 dev pe2-stub-ce2')
    pe2_stub.cmd('ip link set pe2-stub-ce2 up')

    # CE2 default route ra PE2
    ce2.cmd('ip route add default via 10.100.2.2 dev ce2-wan')

    info('*** Mạng 3 lớp Chi nhánh 2 đã sẵn sàng!\n')
    time.sleep(2)

    return net


def run():
    """Hàm chính: khởi chạy topology và mở CLI."""
    net = build_branch2_3tier()

    # In thông tin tóm tắt
    info('\n' + '='*65 + '\n')
    info('  CHI NHÁNH 2 – MẠNG 3 LỚP (CORE–DISTRIBUTION–ACCESS)\n')
    info('='*65 + '\n')
    info('  Tầng Access     : b2acc1 (h2a,h2b) | b2acc2 (h2c,h2d)\n')
    info('  Tầng Distribution: b2dist\n')
    info('  Tầng Core       : b2core\n')
    info('  Subnet          : 10.2.0.0/24\n')
    info('  Gateway         : 10.2.0.254 (CE2)\n')
    info('  WAN link        : CE2 → PE2_stub (10.100.2.0/30)\n')
    info('\n  Số hop tối đa: Host → Access → Dist → Core → CE2 (4 hop)\n')
    info('\n  Lệnh kiểm tra:\n')
    info('    mininet> pingall\n')
    info('    mininet> h2a ping h2d          (cùng subnet, qua 2 acc + dist)\n')
    info('    mininet> h2a ping 10.100.2.2   (ping đến PE2 giả)\n')
    info('    mininet> h2a traceroute h2c    (xem số hop)\n')
    info('    mininet> ce2 ip route          (bảng định tuyến CE2)\n')
    info('='*65 + '\n\n')

    CLI(net)
    net.stop()
    cleanup()


if __name__ == '__main__':
    setLogLevel('info')
    if os.geteuid() != 0:
        print('[LỖI] Cần chạy với quyền root: sudo python3 coreditrubutionaccess.py')
        sys.exit(1)
    run()
