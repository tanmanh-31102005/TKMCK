#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
THAM KHẢO – CHI NHÁNH 1: MẠNG PHẲNG (FLAT NETWORK)
=============================================================================
Đề tài: Thiết kế và triển khai mạng Metro Ethernet sử dụng MPLS
        cho kết nối đa chi nhánh doanh nghiệp
Sinh viên: Huỳnh Văn Dũng – MSSV: 52300190
GVHD    : ThS. Lê Viết Thanh
Trường  : Đại học Tôn Đức Thắng – Khoa CNTT
=============================================================================

MỤC ĐÍCH FILE NÀY:
  Đây là file THAM KHẢO, mô phỏng STANDALONE (độc lập) cho Chi nhánh 1.
  Dùng để kiểm tra riêng lẻ kiến trúc mạng phẳng trước khi tích hợp
  vào topology tổng thể (mpls_metro_topology.py).

KIẾN TRÚC MẠNG PHẲNG (FLAT NETWORK):
  ┌──────────────────────────────────────┐
  │           CHI NHÁNH 1                │
  │                                      │
  │  h1a ─┐                             │
  │  h1b ─┼─── b1sw (L2 Switch) ─── ce1 │──► PE1 (MPLS Backbone)
  │  h1c ─┘                             │
  │                                      │
  │  Subnet: 10.1.0.0/24                 │
  │  Gateway: 10.1.0.254 (CE1)           │
  └──────────────────────────────────────┘

ĐẶC ĐIỂM MẠNG PHẲNG:
  + Đơn giản, dễ cấu hình
  + Tất cả host chung 1 broadcast domain (Layer 2)
  - Không có phân cấp, kém mở rộng
  - Lưu lượng broadcast lớn khi có nhiều host

CHẠY:
  sudo python3 flat.py
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
    """Router Linux đơn giản – bật ip_forward khi khởi động."""

    def config(self, **params):
        super().config(**params)
        self.cmd('sysctl -w net.ipv4.ip_forward=1')
        # Tắt RP filter tránh drop gói hợp lệ đến từ nhiều interface
        self.cmd('for f in /proc/sys/net/ipv4/conf/*/rp_filter; do echo 0 > $f; done')

    def terminate(self):
        self.cmd('sysctl -w net.ipv4.ip_forward=0')
        super().terminate()


def cleanup():
    """Dọn dẹp Mininet cũ."""
    info('*** Dọn dẹp Mininet cũ...\n')
    subprocess.run(['sudo', 'mn', '-c'], capture_output=True, timeout=30)


# ===========================================================================
#  XÂY DỰNG TOPOLOGY CHI NHÁNH 1 – MẠNG PHẲNG
# ===========================================================================
def build_branch1_flat():
    """
    Xây dựng standalone topology mạng phẳng cho chi nhánh 1.

    BẢNG ĐỊA CHỈ IP:
    ┌─────────┬─────────────────┬────────────────────────┐
    │ Thiết bị│ Interface       │ Địa chỉ IP              │
    ├─────────┼─────────────────┼────────────────────────┤
    │ h1a     │ h1a-eth0        │ 10.1.0.1/24             │
    │ h1b     │ h1b-eth0        │ 10.1.0.2/24             │
    │ h1c     │ h1c-eth0        │ 10.1.0.3/24             │
    │ b1sw    │ (L2 Switch)     │ –                       │
    │ ce1     │ ce1-lan (LAN)   │ 10.1.0.254/24 (Gateway) │
    │         │ ce1-wan (WAN)   │ 10.100.1.1/30 (→ PE1)   │
    └─────────┴─────────────────┴────────────────────────┘
    """
    cleanup()

    # Khởi tạo Mininet không dùng controller (standalone)
    net = Mininet(controller=None, link=TCLink, autoSetMacs=True)

    info('*** Tạo Switch tầng truy cập duy nhất (Flat – 1 Broadcast Domain)\n')
    # b1sw: switch L2 duy nhất, tất cả host kết nối vào đây
    b1sw = net.addSwitch('b1sw', cls=OVSSwitch, failMode='standalone',
                         dpid='0000000000000001')

    info('*** Tạo các Host thuộc chi nhánh 1\n')
    # 3 host – tất cả cùng subnet 10.1.0.0/24, default gateway là CE1
    h1a = net.addHost('h1a', ip='10.1.0.1/24', defaultRoute='via 10.1.0.254')
    h1b = net.addHost('h1b', ip='10.1.0.2/24', defaultRoute='via 10.1.0.254')
    h1c = net.addHost('h1c', ip='10.1.0.3/24', defaultRoute='via 10.1.0.254')

    info('*** Tạo CE1 (Customer Edge Router – cửa ngõ ra ISP)\n')
    # CE1 có 2 interface: LAN (nối switch) và WAN (nối PE1 của ISP)
    ce1 = net.addHost('ce1', cls=LinuxRouter, ip='10.1.0.254/24')

    info('*** Tạo PE1 giả lập (Provider Edge – để test standalone)\n')
    # PE1 giả để test routing CE → PE trong môi trường standalone
    pe1_stub = net.addHost('pe1_stub', cls=LinuxRouter, ip='10.100.1.2/30')

    # ─── Kết nối: Host → Switch ─────────────────────────────────────────────
    # Băng thông 100 Mbps – mô phỏng LAN thông thường
    net.addLink(h1a, b1sw, bw=100)
    net.addLink(h1b, b1sw, bw=100)
    net.addLink(h1c, b1sw, bw=100)

    # ─── Kết nối: Switch → CE1 ──────────────────────────────────────────────
    # Uplink 1 Gbps từ switch lên CE (giống đường Gigabit Uplink)
    net.addLink(b1sw, ce1, intfName2='ce1-lan', bw=1000)

    # ─── Kết nối: CE1 → PE1 (giả lập đường Metro Ethernet) ─────────────────
    # 100 Mbps, delay 5 ms – mô phỏng đường Metro Ethernet đến ISP
    net.addLink(ce1, pe1_stub,
                intfName1='ce1-wan', intfName2='pe1-stub-ce1',
                bw=100, delay='5ms')

    # ─── Khởi động mạng ──────────────────────────────────────────────────────
    info('*** Khởi động mạng...\n')
    net.start()

    # ─── Cấu hình IP thủ công cho CE1 ───────────────────────────────────────
    # Mininet không tự gán IP cho multi-interface host → phải cấu hình thủ công
    info('*** Cấu hình IP cho CE1 và PE1 stub...\n')
    ce1.cmd('ip addr flush dev ce1-lan 2>/dev/null')
    ce1.cmd('ip addr flush dev ce1-wan 2>/dev/null')
    ce1.cmd('ip addr add 10.1.0.254/24 dev ce1-lan')
    ce1.cmd('ip addr add 10.100.1.1/30  dev ce1-wan')
    ce1.cmd('ip link set ce1-lan up && ip link set ce1-wan up')

    pe1_stub.cmd('ip addr flush dev pe1-stub-ce1 2>/dev/null')
    pe1_stub.cmd('ip addr add 10.100.1.2/30 dev pe1-stub-ce1')
    pe1_stub.cmd('ip link set pe1-stub-ce1 up')

    # ─── Routing ─────────────────────────────────────────────────────────────
    # CE1 chuyển hướng tất cả traffic ra ngoài qua PE1
    ce1.cmd('ip route add default via 10.100.1.2 dev ce1-wan')

    info('*** Mạng phẳng Chi nhánh 1 đã sẵn sàng!\n')
    time.sleep(2)

    return net


def run():
    """Hàm chính: khởi chạy topology và mở CLI."""
    net = build_branch1_flat()

    # In thông tin tóm tắt
    info('\n' + '='*60 + '\n')
    info('  CHI NHÁNH 1 – MẠNG PHẲNG (FLAT NETWORK)\n')
    info('='*60 + '\n')
    info('  Kiến trúc: 1 Switch L2 + 3 Host + 1 CE Router\n')
    info('  Subnet   : 10.1.0.0/24\n')
    info('  Gateway  : 10.1.0.254 (CE1)\n')
    info('  WAN link : CE1 → PE1_stub (10.100.1.0/30)\n')
    info('\n  Lệnh kiểm tra:\n')
    info('    mininet> pingall\n')
    info('    mininet> h1a ping h1b          (cùng chi nhánh)\n')
    info('    mininet> h1a ping 10.100.1.2   (ping đến PE1 giả)\n')
    info('    mininet> h1a traceroute h1c    (xem đường đi L2)\n')
    info('    mininet> ce1 ip route          (bảng định tuyến CE1)\n')
    info('    mininet> b1sw dpctl dump-flows (xem flow table switch)\n')
    info('='*60 + '\n\n')

    CLI(net)
    net.stop()
    cleanup()


if __name__ == '__main__':
    setLogLevel('info')
    if os.geteuid() != 0:
        print('[LỖI] Cần chạy với quyền root: sudo python3 flat.py')
        sys.exit(1)
    run()
