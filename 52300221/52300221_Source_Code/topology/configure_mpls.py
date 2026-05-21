#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: configure_mpls.py
MÔ TẢ: Cấu hình Linux Kernel MPLS (iproute2) cho backbone Metro Ethernet.

Cơ chế MPLS theo kienthuc.txt:
  - PE (Provider Edge) thực hiện PUSH: dán nhãn vào gói IP đầu vào
  - P  (Provider Core) thực hiện SWAP: hoán đổi nhãn khi chuyển tiếp  
  - PE đích thực hiện POP : gỡ nhãn, trả gói IP gốc về CE

Yêu cầu kernel:
  - Linux >= 4.1 (có module mpls_router, mpls_iptunnel)
  - Package iproute2 >= 4.x

Sơ đồ label (LSP – Label Switched Path):
  ┌─────────────────────────────────────────────────────────────────┐
  │  LAN1→LAN2:  PE1─(push 200)─P1─(swap 201)─P3─(pop)─PE2─CE2   │
  │  LAN1→LAN3:  PE1─(push 300)─P1─(swap 301)─P2─(pop)─PE3─CE3   │
  │  LAN2→LAN1:  PE2─(push 100)─P3─(swap 101)─P1─(pop)─PE1─CE1   │
  │  LAN2→LAN3:  PE2─(push 310)─P4─(swap 311)─PE3─CE3            │
  │  LAN3→LAN1:  PE3─(push 110)─P2─(swap 111)─P1─(pop)─PE1─CE1  │
  │  LAN3→LAN2:  PE3─(push 210)─P4─(swap 211)─PE2─CE2            │
  └─────────────────────────────────────────────────────────────────┘

Bảng phân phối nhãn (LFIB – Label Forwarding Information Base):
  Label 100: LAN1 → PE1 direction
  Label 200: LAN2 → PE2 direction
  Label 300: LAN3 → PE3 direction
  (các swap label dùng giá trị liên tiếp)

CÁCH SỬ DỤNG:
  from configure_mpls import configure_mpls
  configure_mpls(net)   # Truyền Mininet object đang chạy
=============================================================================
"""

from mininet.log import info, warning


# ===========================================================================
# Tên interface theo topo_backbone_mpls.py / metro_full.py
# ===========================================================================
# PE1: pe1-eth1=P1, pe1-eth2=P3
# PE2: pe2-eth1=P3, pe2-eth2=P4
# PE3: pe3-eth1=P2, pe3-eth2=P4
# P1 : p1-eth0=PE1, p1-eth1=P2, p1-eth2=P3, p1-eth3=P4
# P2 : p2-eth0=PE3, p2-eth1=P1, p2-eth2=P3, p2-eth3=P4
# P3 : p3-eth0=PE1, p3-eth1=PE2, p3-eth2=P1, p3-eth3=P2, p3-eth4=P4
# P4 : p4-eth0=PE2, p4-eth1=PE3, p4-eth2=P1, p4-eth3=P2, p4-eth4=P3


MPLS_NODES = ['pe1', 'pe2', 'pe3', 'p1', 'p2', 'p3', 'p4']

# Map node → danh sách interface tham gia MPLS (không tính uplink CE)
MPLS_INTERFACES = {
    'pe1': ['pe1-eth1', 'pe1-eth2'],
    'pe2': ['pe2-eth1', 'pe2-eth2'],
    'pe3': ['pe3-eth1', 'pe3-eth2'],
    'p1':  ['p1-eth0', 'p1-eth1', 'p1-eth2', 'p1-eth3'],
    'p2':  ['p2-eth0', 'p2-eth1', 'p2-eth2', 'p2-eth3'],
    'p3':  ['p3-eth0', 'p3-eth1', 'p3-eth2', 'p3-eth3', 'p3-eth4'],
    'p4':  ['p4-eth0', 'p4-eth1', 'p4-eth2', 'p4-eth3', 'p4-eth4'],
}


def _load_mpls_modules(node):
    """Tải kernel module MPLS nếu chưa có."""
    node.cmd('modprobe mpls_router   2>/dev/null || true')
    node.cmd('modprobe mpls_iptunnel 2>/dev/null || true')
    node.cmd('modprobe mpls_gso      2>/dev/null || true')


def _enable_mpls_platform(node):
    """Bật MPLS platform labels (tối đa 100000 nhãn)."""
    node.cmd('sysctl -w net.mpls.platform_labels=100000 2>/dev/null')
    node.cmd('sysctl -w net.mpls.conf.lo.input=1        2>/dev/null')


def _enable_mpls_on_interfaces(node, ifaces):
    """Bật MPLS input trên từng interface."""
    for iface in ifaces:
        node.cmd(f'sysctl -w net.mpls.conf.{iface}.input=1 2>/dev/null')


def configure_mpls(net):
    """
    Hàm chính: cấu hình Linux Kernel MPLS trên toàn backbone.
    
    Gọi sau khi net.start() đã chạy xong và IP đã được gán.
    Thực hiện 4 bước:
      1) Tải kernel module
      2) Bật MPLS platform + interface
      3) Cấu hình LFIB (Label Forwarding Information Base) cho P routers
      4) Cấu hình PUSH/POP tại PE routers
    """
    info('\n*** Bắt đầu cấu hình Linux Kernel MPLS\n')

    # ------------------------------------------------------------------
    # Bước 1: Load module + bật MPLS trên mỗi node backbone
    # ------------------------------------------------------------------
    info('*** [MPLS 1/4] Tải kernel module và bật platform labels\n')
    for name in MPLS_NODES:
        node = net[name]
        _load_mpls_modules(node)
        _enable_mpls_platform(node)
        _enable_mpls_on_interfaces(node, MPLS_INTERFACES.get(name, []))
        info(f'    {name}: MPLS enabled trên {len(MPLS_INTERFACES.get(name,[]))} interfaces\n')

    # ------------------------------------------------------------------
    # Bước 2: Cấu hình LFIB tại P routers (SWAP)
    # ------------------------------------------------------------------
    info('*** [MPLS 2/4] Cấu hình LFIB tại P routers (SWAP operation)\n')
    _configure_p_lfib(net)

    # ------------------------------------------------------------------
    # Bước 3: Cấu hình PUSH tại PE routers (ingress LER)
    # ------------------------------------------------------------------
    info('*** [MPLS 3/4] Cấu hình PUSH tại PE routers (ingress LER)\n')
    _configure_pe_push(net)

    # ------------------------------------------------------------------
    # Bước 4: Cấu hình POP tại PE routers (egress LER)
    # ------------------------------------------------------------------
    info('*** [MPLS 4/4] Cấu hình POP tại PE routers (egress LER)\n')
    _configure_pe_pop(net)

    info('\n*** Cấu hình MPLS hoàn tất!\n')
    _print_lfib_summary()


# ===========================================================================
# BƯỚC 2: LFIB tại P routers (SWAP)
# ===========================================================================
def _configure_p_lfib(net):
    """
    SWAP: P nhận gói có nhãn vào, thay bằng nhãn mới, đẩy ra interface khác.
    
    Sơ đồ LSP (Label Switched Path):
      LAN1 → LAN2: PE1─[push 200]─P1─[swap 200→201]─P3─[pop]─PE2
      LAN1 → LAN3: PE1─[push 300]─P1─[swap 300→301]─P2─[pop]─PE3
      LAN2 → LAN1: PE2─[push 100]─P3─[swap 100→101]─P1─[pop]─PE1
      LAN2 → LAN3: PE2─[push 310]─P4─[swap 310→311]─PE3
      LAN3 → LAN1: PE3─[push 110]─P2─[swap 110→111]─P1─[pop]─PE1
      LAN3 → LAN2: PE3─[push 210]─P4─[swap 210→211]─PE2
    """
    p1, p2, p3, p4 = net['p1'], net['p2'], net['p3'], net['p4']

    # ---- P1: SWAP ----
    # Nhận label 200 (từ PE1, hướng LAN2): swap→201, forward qua p1-eth2 → P3
    p1.cmd('ip -f mpls route add 200 as 201 via inet 10.20.13.2 dev p1-eth2')
    # Nhận label 300 (từ PE1, hướng LAN3): swap→301, forward qua p1-eth1 → P2
    p1.cmd('ip -f mpls route add 300 as 301 via inet 10.20.12.2 dev p1-eth1')
    # Nhận label 101 (từ P3, hướng LAN1): swap→101, pop ở PE1 (explicit-null / swap lại)
    p1.cmd('ip -f mpls route add 101 as 0   via inet 10.10.11.1 dev p1-eth0')
    # Nhận label 111 (từ P2, LAN3→LAN1): forward đến PE1 (pop)
    p1.cmd('ip -f mpls route add 111 as 0   via inet 10.10.11.1 dev p1-eth0')
    info('    P1: SWAP 200→201(P3), 300→301(P2), 101→pop(PE1), 111→pop(PE1)\n')

    # ---- P2: SWAP ----
    # Nhận label 110 (từ PE3, hướng LAN1): swap→111, forward qua P1
    p2.cmd('ip -f mpls route add 110 as 111 via inet 10.20.12.1 dev p2-eth1')
    # Nhận label 210 (từ PE3, hướng LAN2): swap→211, forward qua P4
    p2.cmd('ip -f mpls route add 210 as 211 via inet 10.20.24.2 dev p2-eth3')
    # Nhận label 301 (từ P1, LAN1→LAN3): forward đến PE3 (pop)
    p2.cmd('ip -f mpls route add 301 as 0   via inet 10.10.32.1 dev p2-eth0')
    info('    P2: SWAP 110→111(P1), 210→211(P4), 301→pop(PE3)\n')

    # ---- P3: SWAP ----
    # Nhận label 100 (từ PE2, hướng LAN1): swap→101, forward qua P1
    p3.cmd('ip -f mpls route add 100 as 101 via inet 10.20.13.1 dev p3-eth2')
    # Nhận label 201 (từ P1, LAN1→LAN2): forward đến PE2 (pop)
    p3.cmd('ip -f mpls route add 201 as 0   via inet 10.10.23.1 dev p3-eth1')
    # Nhận label 310 (từ PE2, hướng LAN3): swap, forward qua P4
    p3.cmd('ip -f mpls route add 310 as 311 via inet 10.20.34.2 dev p3-eth4')
    info('    P3: SWAP 100→101(P1), 201→pop(PE2), 310→311(P4)\n')

    # ---- P4: SWAP ----
    # Nhận label 311 (từ P3, LAN2→LAN3): forward đến PE3 (pop)
    p4.cmd('ip -f mpls route add 311 as 0   via inet 10.10.34.1 dev p4-eth1')
    # Nhận label 211 (từ P2, LAN3→LAN2): forward đến PE2 (pop)
    p4.cmd('ip -f mpls route add 211 as 0   via inet 10.10.24.1 dev p4-eth0')
    info('    P4: SWAP 311→pop(PE3), 211→pop(PE2)\n')


# ===========================================================================
# BƯỚC 3: PUSH tại PE routers (Ingress LER)
# ===========================================================================
def _configure_pe_push(net):
    """
    PUSH: PE nhận gói IP từ CE, dán nhãn MPLS, đẩy vào MPLS domain.
    Dùng lệnh: ip route add <prefix> encap mpls <label> via <next-hop>
    """
    pe1, pe2, pe3 = net['pe1'], net['pe2'], net['pe3']

    # PE1: push nhãn cho traffic đi về LAN2 và LAN3
    pe1.cmd('ip route add 10.2.0.0/16  encap mpls 200 via 10.10.11.2 dev pe1-eth1')
    pe1.cmd('ip route add 10.100.2.0/30 encap mpls 200 via 10.10.11.2 dev pe1-eth1')
    pe1.cmd('ip route add 10.3.0.0/16  encap mpls 300 via 10.10.11.2 dev pe1-eth1')
    pe1.cmd('ip route add 10.100.3.0/30 encap mpls 300 via 10.10.11.2 dev pe1-eth1')
    info('    PE1 PUSH: 10.2.0.0/16→label200, 10.3.0.0/16→label300 (via P1)\n')

    # PE2: push nhãn cho traffic đi về LAN1 và LAN3
    pe2.cmd('ip route add 10.1.0.0/24  encap mpls 100 via 10.10.23.2 dev pe2-eth1')
    pe2.cmd('ip route add 10.100.1.0/30 encap mpls 100 via 10.10.23.2 dev pe2-eth1')
    pe2.cmd('ip route add 10.3.0.0/16  encap mpls 310 via 10.10.24.2 dev pe2-eth2')
    pe2.cmd('ip route add 10.100.3.0/30 encap mpls 310 via 10.10.24.2 dev pe2-eth2')
    info('    PE2 PUSH: 10.1.0.0/24→label100, 10.3.0.0/16→label310 (via P3/P4)\n')

    # PE3: push nhãn cho traffic đi về LAN1 và LAN2
    pe3.cmd('ip route add 10.1.0.0/24  encap mpls 110 via 10.10.32.2 dev pe3-eth1')
    pe3.cmd('ip route add 10.100.1.0/30 encap mpls 110 via 10.10.32.2 dev pe3-eth1')
    pe3.cmd('ip route add 10.2.0.0/16  encap mpls 210 via 10.10.32.2 dev pe3-eth1')
    pe3.cmd('ip route add 10.100.2.0/30 encap mpls 210 via 10.10.32.2 dev pe3-eth1')
    info('    PE3 PUSH: 10.1.0.0/24→label110, 10.2.0.0/16→label210 (via P2)\n')


# ===========================================================================
# BƯỚC 4: POP tại PE routers (Egress LER)
# ===========================================================================
def _configure_pe_pop(net):
    """
    POP: khi nhận label=0 (explicit-null), PE gỡ nhãn và forward gói IP gốc.
    Linux kernel MPLS tự xử lý label=0; chỉ cần đảm bảo IP route về CE tồn tại.
    """
    pe1, pe2, pe3 = net['pe1'], net['pe2'], net['pe3']

    # PE1: khi gói đến (label đã pop bởi P hoặc implicit-null), route về CE1
    pe1.cmd('ip route add 10.1.0.0/24  via 10.0.1.1 dev pe1-eth0 2>/dev/null || true')
    pe1.cmd('ip route add 10.100.1.0/30 via 10.0.1.1 dev pe1-eth0 2>/dev/null || true')

    # PE2: route về CE2
    pe2.cmd('ip route add 10.2.0.0/16  via 10.0.2.1 dev pe2-eth0 2>/dev/null || true')
    pe2.cmd('ip route add 10.100.2.0/30 via 10.0.2.1 dev pe2-eth0 2>/dev/null || true')

    # PE3: route về CE3
    pe3.cmd('ip route add 10.3.0.0/16  via 10.0.3.1 dev pe3-eth0 2>/dev/null || true')
    pe3.cmd('ip route add 10.100.3.0/30 via 10.0.3.1 dev pe3-eth0 2>/dev/null || true')

    info('    PE1/PE2/PE3: POP configured (label=0 → IP forwarding to CE)\n')


# ===========================================================================
# In bảng tóm tắt LFIB
# ===========================================================================
def _print_lfib_summary():
    info('\n' + '='*65 + '\n')
    info('  MPLS LABEL FORWARDING TABLE (LFIB) TÓM TẮT\n')
    info('='*65 + '\n')
    rows = [
        ('PE1 PUSH', '10.2.0.0/16 → label 200', 'P1 (pe1-eth1)'),
        ('PE1 PUSH', '10.3.0.0/16 → label 300', 'P1 (pe1-eth1)'),
        ('PE2 PUSH', '10.1.0.0/24 → label 100', 'P3 (pe2-eth1)'),
        ('PE2 PUSH', '10.3.0.0/16 → label 310', 'P4 (pe2-eth2)'),
        ('PE3 PUSH', '10.1.0.0/24 → label 110', 'P2 (pe3-eth1)'),
        ('PE3 PUSH', '10.2.0.0/16 → label 210', 'P2 (pe3-eth1)'),
        ('P1  SWAP', '200 → 201', 'P3 (p1-eth2)'),
        ('P1  SWAP', '300 → 301', 'P2 (p1-eth1)'),
        ('P2  SWAP', '110 → 111', 'P1 (p2-eth1)'),
        ('P2  SWAP', '210 → 211', 'P4 (p2-eth3)'),
        ('P3  SWAP', '100 → 101', 'P1 (p3-eth2)'),
        ('P3  SWAP', '310 → 311', 'P4 (p3-eth4)'),
        ('P1  POP ', '101 → 0 (pop)', 'PE1 (p1-eth0)'),
        ('P3  POP ', '201 → 0 (pop)', 'PE2 (p3-eth1)'),
        ('P2  POP ', '301 → 0 (pop)', 'PE3 (p2-eth0)'),
        ('P4  POP ', '311 → 0 (pop)', 'PE3 (p4-eth1)'),
        ('P4  POP ', '211 → 0 (pop)', 'PE2 (p4-eth0)'),
    ]
    info(f"  {'Node':<10} {'Operation':<28} {'Next-hop'}\n")
    info('-'*65 + '\n')
    for node, op, nh in rows:
        info(f"  {node:<10} {op:<28} {nh}\n")
    info('='*65 + '\n')


# ===========================================================================
# Hàm kiểm tra MPLS đã cấu hình đúng chưa
# ===========================================================================
def verify_mpls(net):
    """
    Kiểm tra bảng MPLS route trên từng node và in kết quả.
    Chạy lệnh: ip -f mpls route show
    """
    info('\n*** Xác minh bảng MPLS route\n')
    for node_name in MPLS_NODES:
        node = net[node_name]
        out = node.cmd('ip -f mpls route show 2>/dev/null')
        if out.strip():
            info(f'\n  [{node_name}] MPLS routes:\n')
            for line in out.strip().split('\n'):
                info(f'    {line}\n')
        else:
            warning(f'  [{node_name}] CẢNH BÁO: Không có MPLS route (kernel module chưa load?)\n')


# ===========================================================================
# Standalone test
# ===========================================================================
if __name__ == '__main__':
    print("configure_mpls.py – import module này vào metro_full.py hoặc topo_backbone_mpls.py")
    print("Cách dùng:")
    print("  from configure_mpls import configure_mpls, verify_mpls")
    print("  configure_mpls(net)   # Sau khi net.start()")
    print("  verify_mpls(net)      # Kiểm tra bảng route")
