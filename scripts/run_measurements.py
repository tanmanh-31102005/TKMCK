#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: scripts/run_measurements.py
MÔ TẢ: Script đo hiệu năng tự động – chạy trong Mininet Python API.

        Thay thế cho các shell script (vì Mininet hoạt động tốt nhất
        khi kiểm soát từ Python, không phải shell bên ngoài).

        Đo 4 chỉ số theo đề bài:
          - Throughput  (iperf3 TCP)
          - Delay       (ping RTT avg)
          - Packet Loss (ping + iperf3 UDP)
          - Jitter      (iperf3 UDP)

CÁCH CHẠY:
  sudo python3 scripts/run_measurements.py --scenario flat
  sudo python3 scripts/run_measurements.py --scenario 3tier
  sudo python3 scripts/run_measurements.py --scenario leafspine
  sudo python3 scripts/run_measurements.py --scenario all

  Kết quả lưu tại:
    results/raw/<scenario>_<timestamp>/
    results/csv/results_<timestamp>.csv
=============================================================================
"""

import os
import sys
import re
import csv
import json
import argparse
import datetime
import time

# Thêm path của thư mục topology để import được
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'topology'))

from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info, error

# Import topology từ file riêng
from metro_full import MetroFullTopo, configure_full_network

# Thư mục gốc dự án
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR   = os.path.join(BASE_DIR, 'results', 'raw')
CSV_DIR   = os.path.join(BASE_DIR, 'results', 'csv')


# ===========================================================================
# Định nghĩa test cases (đồng bộ với config/tests.yaml)
# ===========================================================================
SCENARIOS = {
    'flat': {
        'name': 'Flat Network (Chi nhánh 1)',
        'pairs': [
            # (src_name, dst_ip, description, test_type)
            # test_type: 'both' | 'intra' | 'cross'
            ('host1', '10.1.0.102', 'host1→host2 [intra-flat]',     'intra'),
            ('host1', '10.1.0.103', 'host1→host3 [intra-flat]',     'intra'),
            ('host1', '10.2.10.11', 'host1→admin1 [flat→3tier]',    'cross'),
            ('host1', '10.3.10.11', 'host1→web1 [flat→leafspine]',  'cross'),
        ],
    },
    '3tier': {
        'name': '3-Tier Network (Chi nhánh 2)',
        'pairs': [
            ('admin1', '10.2.10.12', 'admin1→admin2 [same-VLAN10]',     'intra'),
            ('admin1', '10.2.20.21', 'admin1→lab1 [inter-VLAN]',        'intra'),
            ('admin1', '10.2.30.31', 'admin1→guest1 [inter-VLAN]',      'intra'),
            ('admin1', '10.1.0.101', 'admin1→host1 [3tier→flat]',       'cross'),
            ('admin1', '10.3.10.11', 'admin1→web1 [3tier→leafspine]',   'cross'),
        ],
    },
    'leafspine': {
        'name': 'Leaf-Spine Network (Chi nhánh 3)',
        'pairs': [
            ('web1', '10.3.10.12', 'web1→web2 [same-leaf1]',            'intra'),
            ('web1', '10.3.20.21', 'web1→dns1 [leaf1→leaf2, 2hop]',     'intra'),
            ('web1', '10.3.30.31', 'web1→db1 [leaf1→leaf3, 2hop]',      'intra'),
            ('web1', '10.1.0.101', 'web1→host1 [leafspine→flat]',       'cross'),
            ('web1', '10.2.10.11', 'web1→admin1 [leafspine→3tier]',     'cross'),
        ],
    },
}

LOAD_LEVELS = [
    ('10Mbps',  '10M'),
    ('50Mbps',  '50M'),
    ('100Mbps', '100M'),
]

PING_COUNT    = 100
IPERF_DURATION = 10
REPEAT        = 3


# ===========================================================================
# Hàm đo ping (Delay + Packet Loss)
# ===========================================================================
def measure_ping(src_node, dst_ip, count=PING_COUNT):
    """
    Chạy ping và trả về dict {avg_ms, min_ms, max_ms, mdev_ms, loss_pct}.
    """
    cmd = f'ping -c {count} -i 0.1 {dst_ip}'
    out = src_node.cmd(cmd)

    result = {
        'avg_ms':   None,
        'min_ms':   None,
        'max_ms':   None,
        'mdev_ms':  None,
        'loss_pct': None,
        'raw':      out,
    }

    # Trích packet loss: "X% packet loss"
    m = re.search(r'(\d+(?:\.\d+)?)% packet loss', out)
    if m:
        result['loss_pct'] = float(m.group(1))

    # Trích RTT: "rtt min/avg/max/mdev = 0.100/0.200/0.300/0.050 ms"
    m = re.search(r'rtt min/avg/max/mdev = '
                  r'([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms', out)
    if m:
        result['min_ms']  = float(m.group(1))
        result['avg_ms']  = float(m.group(2))
        result['max_ms']  = float(m.group(3))
        result['mdev_ms'] = float(m.group(4))

    return result


# ===========================================================================
# Hàm đo iperf3 UDP (Throughput + Jitter + Packet Loss)
# ===========================================================================
def measure_iperf_udp(src_node, dst_node, dst_ip,
                      bandwidth='100M', duration=IPERF_DURATION):
    """
    Chạy iperf3 UDP: server trên dst, client trên src.
    Trả về dict {throughput_mbps, jitter_ms, loss_pct}.
    """
    # Dọn dẹp iperf3 server cũ nếu còn
    dst_node.cmd('pkill -f "iperf3 -s" 2>/dev/null; sleep 0.3')

    # Khởi server iperf3 trên dst (background)
    dst_node.cmd(f'iperf3 -s -D --one-off 2>/dev/null')
    time.sleep(0.5)

    # Chạy client trên src (UDP, -b=bandwidth, -t=duration, -J=JSON output)
    cmd = (f'iperf3 -c {dst_ip} -u -b {bandwidth} '
           f'-t {duration} -J 2>/dev/null')
    out = src_node.cmd(cmd)

    result = {
        'throughput_mbps': None,
        'jitter_ms':       None,
        'loss_pct':        None,
        'raw':             out,
    }

    try:
        data = json.loads(out)
        end  = data.get('end', {})

        # UDP sender side
        sender = end.get('sum', {})
        if sender:
            bits_per_sec = sender.get('bits_per_second', 0)
            result['throughput_mbps'] = round(bits_per_sec / 1e6, 3)
            result['jitter_ms']       = round(sender.get('jitter_ms', 0), 4)
            lost    = sender.get('lost_packets', 0)
            total   = sender.get('packets', 1)
            result['loss_pct'] = round(lost / total * 100, 2) if total else 0
    except (json.JSONDecodeError, KeyError, TypeError):
        # Fallback: parse text output
        m = re.search(r'([\d.]+) Mbits/sec\s+[\d.]+\s+ms\s+\d+/\d+\s+\(([\d.]+)%\)', out)
        if m:
            result['throughput_mbps'] = float(m.group(1))
            result['loss_pct']        = float(m.group(2))
        m2 = re.search(r'([\d.]+) ms', out)
        if m2:
            result['jitter_ms'] = float(m2.group(1))

    # Kill server
    dst_node.cmd('pkill -f "iperf3 -s" 2>/dev/null')
    return result


# ===========================================================================
# Hàm đo iperf3 TCP (Throughput chính xác hơn)
# ===========================================================================
def measure_iperf_tcp(src_node, dst_node, dst_ip, duration=IPERF_DURATION):
    """Chạy iperf3 TCP và trả về throughput_mbps."""
    dst_node.cmd('pkill -f "iperf3 -s" 2>/dev/null; sleep 0.3')
    dst_node.cmd('iperf3 -s -D --one-off 2>/dev/null')
    time.sleep(0.5)

    cmd = f'iperf3 -c {dst_ip} -t {duration} -J 2>/dev/null'
    out = src_node.cmd(cmd)

    throughput_mbps = None
    try:
        data = json.loads(out)
        bits = data['end']['sum_received']['bits_per_second']
        throughput_mbps = round(bits / 1e6, 3)
    except (json.JSONDecodeError, KeyError, TypeError):
        m = re.search(r'([\d.]+) Mbits/sec', out)
        if m:
            throughput_mbps = float(m.group(1))

    dst_node.cmd('pkill -f "iperf3 -s" 2>/dev/null')
    return throughput_mbps


# ===========================================================================
# Hàm chạy toàn bộ test cho 1 scenario
# ===========================================================================
def run_scenario(net, scenario_key, ts, raw_dir):
    """
    Chạy tất cả test case cho 1 scenario.
    Trả về list of record dicts để lưu CSV.
    """
    scenario = SCENARIOS[scenario_key]
    records  = []

    info(f'\n{"="*60}\n')
    info(f'  SCENARIO: {scenario["name"]}\n')
    info(f'{"="*60}\n')

    for src_name, dst_ip, desc, test_type in scenario['pairs']:
        info(f'\n  >>> Test: {desc}\n')

        # Lấy node dst từ IP (cần biết tên node)
        dst_name = _ip_to_node(net, dst_ip)
        src_node = net[src_name]
        dst_node = net.get(dst_name) if dst_name else None

        # Chạy REPEAT lần, lấy trung bình
        ping_results   = []
        udp_results    = []
        tcp_throughputs = []

        for run in range(1, REPEAT + 1):
            info(f'    Run {run}/{REPEAT}: ping...')

            # ---- Ping test ----
            pr = measure_ping(src_node, dst_ip, count=PING_COUNT)
            ping_results.append(pr)
            _save_raw(raw_dir, f'{scenario_key}_ping_{src_name}_{dst_ip}_run{run}_{ts}.txt',
                      pr['raw'])
            info(f'  loss={pr["loss_pct"]}% avg={pr["avg_ms"]}ms\n')

            # ---- iperf3 UDP (từng mức tải) ----
            if dst_node:
                for load_label, bw in LOAD_LEVELS:
                    info(f'    Run {run}/{REPEAT}: iperf3 UDP {load_label}...')
                    ur = measure_iperf_udp(src_node, dst_node, dst_ip,
                                           bandwidth=bw,
                                           duration=IPERF_DURATION)
                    _save_raw(raw_dir,
                              f'{scenario_key}_udp_{src_name}_{dst_ip}_{load_label}_run{run}_{ts}.txt',
                              ur['raw'])
                    info(f'  tput={ur["throughput_mbps"]}Mbps '
                         f'jitter={ur["jitter_ms"]}ms '
                         f'loss={ur["loss_pct"]}%\n')
                    udp_results.append({
                        'load_label': load_label,
                        'bandwidth':  bw,
                        **ur,
                        'run': run,
                    })

                # ---- iperf3 TCP ----
                info(f'    Run {run}/{REPEAT}: iperf3 TCP...')
                tcp_tp = measure_iperf_tcp(src_node, dst_node, dst_ip,
                                            duration=IPERF_DURATION)
                tcp_throughputs.append(tcp_tp)
                info(f'  {tcp_tp} Mbps\n')

        # Tổng hợp kết quả ping
        avg_ping = _average_ping(ping_results)

        # Tổng hợp iperf3 UDP theo từng mức tải
        for load_label, bw in LOAD_LEVELS:
            runs_at_load = [r for r in udp_results if r['load_label'] == load_label]
            if runs_at_load:
                record = {
                    'scenario':         scenario_key,
                    'arch_name':        scenario['name'],
                    'test_type':        test_type,
                    'src_host':         src_name,
                    'dst_ip':           dst_ip,
                    'description':      desc,
                    'load_level':       load_label,
                    'bandwidth_target': bw,
                    # Ping metrics (trung bình qua REPEAT lần)
                    'avg_delay_ms':     avg_ping['avg_ms'],
                    'min_delay_ms':     avg_ping['min_ms'],
                    'max_delay_ms':     avg_ping['max_ms'],
                    'ping_loss_pct':    avg_ping['loss_pct'],
                    # iperf3 UDP metrics
                    'throughput_mbps':  _avg([r['throughput_mbps'] for r in runs_at_load]),
                    'jitter_ms':        _avg([r['jitter_ms'] for r in runs_at_load]),
                    'udp_loss_pct':     _avg([r['loss_pct'] for r in runs_at_load]),
                    # iperf3 TCP
                    'tcp_throughput_mbps': _avg(tcp_throughputs),
                    # Metadata
                    'timestamp': ts,
                    'repeat':    REPEAT,
                }
                records.append(record)
                info(f'  [OK] {desc} @ {load_label}: '
                     f'tput={record["throughput_mbps"]:.2f}Mbps '
                     f'delay={record["avg_delay_ms"]}ms '
                     f'loss={record["udp_loss_pct"]}% '
                     f'jitter={record["jitter_ms"]}ms\n')

    return records


# ===========================================================================
# Helper functions
# ===========================================================================
def _ip_to_node(net, ip):
    """Tìm tên node có IP địa chỉ cho trước (lấy phần IP của /24)."""
    prefix = '.'.join(ip.split('.')[:3])
    for node in net.hosts:
        for intf in node.intfs.values():
            if intf.ip and intf.ip.startswith(prefix):
                return node.name
    return None


def _save_raw(directory, filename, content):
    """Lưu raw output vào file."""
    os.makedirs(directory, exist_ok=True)
    filepath = os.path.join(directory, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content or '')


def _avg(values):
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def _average_ping(ping_results):
    return {
        'avg_ms':   _avg([r['avg_ms']   for r in ping_results]),
        'min_ms':   _avg([r['min_ms']   for r in ping_results]),
        'max_ms':   _avg([r['max_ms']   for r in ping_results]),
        'mdev_ms':  _avg([r['mdev_ms']  for r in ping_results]),
        'loss_pct': _avg([r['loss_pct'] for r in ping_results]),
    }


CSV_FIELDS = [
    'scenario', 'arch_name', 'test_type', 'src_host', 'dst_ip',
    'description', 'load_level', 'bandwidth_target',
    'avg_delay_ms', 'min_delay_ms', 'max_delay_ms', 'ping_loss_pct',
    'throughput_mbps', 'jitter_ms', 'udp_loss_pct',
    'tcp_throughput_mbps', 'timestamp', 'repeat',
]


def save_csv(records, csv_dir, ts):
    """Ghi tất cả record thành CSV."""
    os.makedirs(csv_dir, exist_ok=True)
    filepath = os.path.join(csv_dir, f'results_{ts}.csv')
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, '') for k in CSV_FIELDS})
    return filepath


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='Đo hiệu năng mạng Metro Ethernet MPLS')
    parser.add_argument('--scenario', default='all',
                        choices=['flat', '3tier', 'leafspine', 'all'],
                        help='Chọn scenario cần đo (default: all)')
    parser.add_argument('--verbose', action='store_true',
                        help='In chi tiết log Mininet')
    args = parser.parse_args()

    setLogLevel('info' if args.verbose else 'warning')

    ts      = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    raw_dir = os.path.join(RAW_DIR, f'{args.scenario}_{ts}')
    os.makedirs(raw_dir, exist_ok=True)

    info('*** Khởi tạo topology Metro Full\n')
    topo = MetroFullTopo()
    net  = Mininet(topo=topo, controller=None, link=TCLink)
    net.start()
    configure_full_network(net)

    scenarios_to_run = (
        list(SCENARIOS.keys()) if args.scenario == 'all'
        else [args.scenario]
    )

    all_records = []
    for sc in scenarios_to_run:
        records = run_scenario(net, sc, ts, raw_dir)
        all_records.extend(records)

    net.stop()

    if all_records:
        csv_path = save_csv(all_records, CSV_DIR, ts)
        print(f'\n{"="*60}')
        print(f'  ĐO XONG! Kết quả đã lưu:')
        print(f'    CSV    : {csv_path}')
        print(f'    Raw log: {raw_dir}/')
        print(f'  Tổng số record: {len(all_records)}')
        print(f'{"="*60}\n')
        print(f'  Bước tiếp theo: python3 scripts/plot_results.py --csv {csv_path}')
    else:
        print('\n  CẢNH BÁO: Không có dữ liệu nào được ghi lại!')

    return 0


if __name__ == '__main__':
    sys.exit(main())
