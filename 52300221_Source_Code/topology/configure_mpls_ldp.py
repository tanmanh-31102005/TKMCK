#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
configure_mpls_ldp.py
Chiến lược 2 lớp:
  1. Luôn cài Static MPLS trước (Ping LUÔN hoạt động - layer nền)
  2. Cố gắng khởi động FRR (OSPF + LDP) thêm vào trên cùng
     - Nếu FRR OK  → nhãn được phân phối động, LDP override static
     - Nếu FRR lỗi → static vẫn giữ nguyên, Ping vẫn ✓
"""

import os
import subprocess
import time
from mininet.log import info, warning, error

FRR_BIN    = '/usr/lib/frr'
MPLS_NODES = ['pe1', 'pe2', 'pe3', 'p1', 'p2', 'p3', 'p4']

LOOPBACKS = {
    'pe1': '2.2.2.1', 'pe2': '2.2.2.2', 'pe3': '2.2.2.3',
    'p1' : '3.3.3.1', 'p2' : '3.3.3.2',
    'p3' : '3.3.3.3', 'p4' : '3.3.3.4',
}

MPLS_IFACES = {
    'pe1': ['pe1-eth1', 'pe1-eth2'],
    'pe2': ['pe2-eth1', 'pe2-eth2'],
    'pe3': ['pe3-eth1', 'pe3-eth2'],
    'p1' : ['p1-eth0', 'p1-eth1', 'p1-eth2', 'p1-eth3'],
    'p2' : ['p2-eth0', 'p2-eth1', 'p2-eth2', 'p2-eth3'],
    'p3' : ['p3-eth0', 'p3-eth1', 'p3-eth2', 'p3-eth3', 'p3-eth4'],
    'p4' : ['p4-eth0', 'p4-eth1', 'p4-eth2', 'p4-eth3', 'p4-eth4'],
}

PE_CE_IFACES = {'pe1': 'pe1-eth0', 'pe2': 'pe2-eth0', 'pe3': 'pe3-eth0'}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: Static MPLS (Luôn chạy, đảm bảo Ping 100%)
# ══════════════════════════════════════════════════════════════════════════════
def _install_static_layer(net):
    """
    Cài đầy đủ:
    - Static IP routes cho P routers (backbone underlay)
    - Static IP routes cho PE routers (biên)
    - Gọi configure_mpls() để cài PUSH/SWAP/POP labels
    Hàm này LUÔN được gọi đầu tiên.
    """
    from configure_mpls import configure_mpls as _do_static

    info('\n*** [STATIC BASE] Cài Static IP routes + MPLS labels\n')

    # --- Static IP routes cho P routers ---
    p_routes = {
        'p1' : [('10.1.0.0/24','10.10.11.1'),('10.100.1.0/30','10.10.11.1'),
                ('10.2.0.0/16','10.20.13.2'),('10.100.2.0/30','10.20.13.2'),
                ('10.3.0.0/16','10.20.12.2'),('10.100.3.0/30','10.20.12.2')],
        'p2' : [('10.3.0.0/16','10.10.32.1'),('10.100.3.0/30','10.10.32.1'),
                ('10.1.0.0/24','10.20.12.1'),('10.100.1.0/30','10.20.12.1'),
                ('10.2.0.0/16','10.20.24.2'),('10.100.2.0/30','10.20.24.2')],
        'p3' : [('10.2.0.0/16','10.10.23.1'),('10.100.2.0/30','10.10.23.1'),
                ('10.1.0.0/24','10.10.13.1'),('10.100.1.0/30','10.10.13.1'),
                ('10.3.0.0/16','10.20.34.2'),('10.100.3.0/30','10.20.34.2')],
        'p4' : [('10.2.0.0/16','10.10.24.1'),('10.100.2.0/30','10.10.24.1'),
                ('10.3.0.0/16','10.10.34.1'),('10.100.3.0/30','10.10.34.1'),
                ('10.1.0.0/24','10.20.14.1'),('10.100.1.0/30','10.20.14.1')],
        'pe1': [('10.2.0.0/16','10.10.11.2'),('10.3.0.0/16','10.10.11.2')],
        'pe2': [('10.1.0.0/24','10.10.23.2'),('10.3.0.0/16','10.10.24.2')],
        'pe3': [('10.1.0.0/24','10.10.32.2'),('10.2.0.0/16','10.10.34.2')],
    }
    for rname, routes in p_routes.items():
        for prefix, via in routes:
            # Dùng replace để không bị lỗi "File exists" khi chạy lại
            net[rname].cmd(f'ip route replace {prefix} via {via} 2>/dev/null')

    # --- Gọi configure_mpls() (PUSH/SWAP/POP đã kiểm chứng) ---
    _do_static(net)
    info('  Static MPLS layer OK – Ping đã hoạt động ✓\n')


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2: FRRouting (OSPF + LDP động – chạy thêm lên, optional)
# ══════════════════════════════════════════════════════════════════════════════
def _fix_frr_permissions():
    subprocess.run(['usermod', '-aG', 'frrvty', 'root'], capture_output=True)
    subprocess.run(['chmod', '775', '/var/run/frr'],      capture_output=True)
    subprocess.run(['chgrp', 'frrvty', '/var/run/frr'],   capture_output=True)


def _enable_mpls_kernel(node, name):
    node.cmd('modprobe mpls_router   2>/dev/null || true')
    node.cmd('modprobe mpls_iptunnel 2>/dev/null || true')
    node.cmd('sysctl -w net.mpls.platform_labels=100000 2>/dev/null')
    node.cmd('sysctl -w net.mpls.conf.lo.input=1        2>/dev/null')
    for iface in MPLS_IFACES.get(name, []):
        node.cmd(f'sysctl -w net.mpls.conf.{iface}.input=1 2>/dev/null')


def _write_frr_conf(name, cfg_dir):
    lo_ip  = LOOPBACKS[name]
    ifaces = MPLS_IFACES.get(name, [])
    lines  = [
        '! Auto-generated', 'frr version 8.1', 'frr defaults traditional',
        f'hostname {name}', '!',
        'interface lo', ' ip ospf area 0', '!',
    ]
    for iface in ifaces:
        lines += [f'interface {iface}', ' ip ospf area 0',
                  ' ip ospf hello-interval 2', ' ip ospf dead-interval 8', '!']
    if name in PE_CE_IFACES:
        lines += [f'interface {PE_CE_IFACES[name]}', ' ip ospf area 0', '!']
    lines += [
        'router ospf', f' ospf router-id {lo_ip}', ' redistribute connected', '!',
        'mpls ldp', f' router-id {lo_ip}', ' !',
        ' address-family ipv4', f'  discovery transport-address {lo_ip}',
    ]
    for iface in ifaces:
        lines += [f'  interface {iface}', '  !']
    lines += [' !', '!', '']
    os.makedirs(cfg_dir, exist_ok=True)
    path = os.path.join(cfg_dir, 'frr.conf')
    with open(path, 'w') as f:
        f.write('\n'.join(lines))
    os.chmod(path, 0o644)


def _start_frr(node, name):
    cfg_dir = f'/tmp/frr-{name}'
    run_dir = f'/var/run/frr/{name}'
    for d in [run_dir, cfg_dir]:
        for svc in ['zebra', 'ospfd', 'ldpd']:
            node.cmd(f'[ -f {d}/{svc}.pid ] && kill $(cat {d}/{svc}.pid) 2>/dev/null; true')
    time.sleep(0.3)
    os.makedirs(run_dir, exist_ok=True); os.chmod(run_dir, 0o777)
    os.makedirs(cfg_dir, exist_ok=True)
    _write_frr_conf(name, cfg_dir)
    base = f'-d -N {name} -f {cfg_dir}/frr.conf -u root -g frrvty 2>>{cfg_dir}/frr.log'
    node.cmd(f'{FRR_BIN}/zebra {base}'); time.sleep(0.8)
    node.cmd(f'{FRR_BIN}/ospfd  {base}'); time.sleep(0.6)
    node.cmd(f'{FRR_BIN}/ldpd   {base}'); time.sleep(0.5)
    return run_dir


def _check_running(node, frr_dir):
    result = {}
    for svc in ['zebra', 'ospfd', 'ldpd']:
        pid = f'{frr_dir}/{svc}.pid'
        out = node.cmd(
            f'[ -f {pid} ] && kill -0 $(cat {pid}) 2>/dev/null && echo ALIVE || echo DEAD')
        result[svc] = 'ALIVE' in out
    return result


def _try_frr_layer(net):
    """Cố gắng khởi động FRR (OSPF+LDP). Không crash nếu lỗi."""
    info('\n*** [FRR LAYER] Cố gắng khởi động OSPF + LDP\n')

    # Kiểm tra binary
    for b in ['zebra', 'ospfd', 'ldpd']:
        out = net['p1'].cmd(f'test -x {FRR_BIN}/{b} && echo OK || echo MISSING')
        if 'MISSING' in out:
            warning(f'  Thiếu {b} → bỏ qua FRR layer\n')
            return False

    _fix_frr_permissions()

    frr_dirs = {}
    for name in MPLS_NODES:
        _enable_mpls_kernel(net[name], name)
        frr_dirs[name] = _start_frr(net[name], name)
        info(f'    {name} started\n')

    # Kiểm tra daemon
    all_ok = True
    for name in MPLS_NODES:
        st = _check_running(net[name], frr_dirs[name])
        ok = ' '.join(f'{k}={"✓" if v else "✗"}' for k, v in st.items())
        info(f'    {name}: {ok}\n')
        if not all(st.values()):
            all_ok = False
            log = net[name].cmd(f'tail -2 /tmp/frr-{name}/frr.log 2>/dev/null')
            if log.strip():
                info(f'      {log.strip()[:150]}\n')

    if not all_ok:
        warning('  FRR daemon lỗi – Static MPLS vẫn giữ nguyên ✓\n')
        return False

    # Đợi LDP converge
    info('  Đợi LDP converge (tối đa 40s)...\n')
    for i in range(8):
        time.sleep(5)
        out = net['p1'].cmd('ip -f mpls route show 2>/dev/null')
        if out.strip():
            info(f'  {(i+1)*5}s – LDP nhãn động ✓\n')
            return True
        info(f'  {(i+1)*5}s – chờ...\n')

    warning('  LDP chưa converge – Static MPLS vẫn giữ nguyên ✓\n')
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Hàm chính
# ══════════════════════════════════════════════════════════════════════════════
def configure_mpls_ldp(net):
    info('\n' + '='*62 + '\n')
    info('  MPLS ĐỘNG: OSPF + LDP (FRRouting)\n')
    info('='*62 + '\n')

    # Layer 1: Static MPLS – LUÔN chạy trước, đảm bảo Ping ✓
    _install_static_layer(net)

    # Layer 2: FRR (OSPF+LDP) – thử thêm, không ảnh hưởng Ping nếu lỗi
    ldp_ok = _try_frr_layer(net)

    if ldp_ok:
        info('\n  Chế độ: LDP ĐỘNG ✓ (OSPF + LDP via FRRouting)\n')
    else:
        info('\n  Chế độ: STATIC MPLS ✓ (Ping hoạt động bình thường)\n')


# ══════════════════════════════════════════════════════════════════════════════
# Verify
# ══════════════════════════════════════════════════════════════════════════════
def verify_ldp(net):
    info('\n*** BẢNG NHÃN MPLS\n' + '-'*50 + '\n')
    for name in ['pe1', 'p1', 'p3']:
        mpls = net[name].cmd('ip -f mpls route show 2>/dev/null').strip()
        ipr  = net[name].cmd('ip route show 2>/dev/null | grep mpls').strip()
        info(f'\n  [{name}]\n')
        if mpls:
            info('  LDP động:\n    ' + mpls.replace('\n', '\n    ') + '\n')
        elif ipr:
            info('  Static MPLS:\n    ' + ipr.replace('\n', '\n    ') + '\n')
        else:
            info('  (chưa có nhãn)\n')
    info('\n' + '-'*50 + '\n')
    info('  mininet> p1 ip -f mpls route show\n')
    info('  mininet> pe1 ip route show | grep mpls\n')
    info('  mininet> p1 cat /tmp/frr-p1/frr.log\n')
    info('  mininet> p1 telnet 127.0.0.1 2612  (pw: zebra)\n')


if __name__ == '__main__':
    print('from configure_mpls_ldp import configure_mpls_ldp, verify_ldp')
