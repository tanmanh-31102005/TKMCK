#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: scripts/aggregate_results.py
MÔ TẢ: Tổng hợp kết quả từ nhiều CSV thô thành 1 CSV tổng hợp chuẩn.

        Đọc CSV từ run_measurements.py (hoặc từ parse_ping/parse_iperf),
        tính trung bình qua các lần lặp (repeat),
        nhóm theo (scenario, test_type, load_level),
        xuất CSV tổng hợp dùng cho plot_results.py.

OUTPUT CSV columns:
  scenario, arch_name, test_type, description,
  load_level,
  avg_delay_ms, min_delay_ms, max_delay_ms,
  throughput_mbps, tcp_throughput_mbps,
  jitter_ms, udp_loss_pct, ping_loss_pct

CÁCH DÙNG:
  python3 scripts/aggregate_results.py --csv results/csv/results_<ts>.csv
  python3 scripts/aggregate_results.py --dir results/csv/
  python3 scripts/aggregate_results.py --generate-mock    # Tạo dữ liệu giả để test
=============================================================================
"""

import os
import sys
import csv
import argparse
import datetime
import random
from pathlib import Path
from collections import defaultdict


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR  = os.path.join(BASE_DIR, 'results', 'csv')


# ===========================================================================
# Fields đầu ra
# ===========================================================================
AGG_FIELDS = [
    'scenario', 'arch_name', 'test_type', 'description',
    'load_level',
    'avg_delay_ms', 'min_delay_ms', 'max_delay_ms',
    'throughput_mbps', 'tcp_throughput_mbps',
    'jitter_ms', 'udp_loss_pct', 'ping_loss_pct',
    'n_samples',
]


# ===========================================================================
# Đọc CSV đầu vào
# ===========================================================================
def read_csv(filepath):
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def safe_float(val):
    """Chuyển string → float, trả None nếu lỗi."""
    try:
        return float(val) if val not in (None, '', 'None') else None
    except (ValueError, TypeError):
        return None


def _avg(vals):
    clean = [v for v in vals if v is not None]
    return round(sum(clean) / len(clean), 4) if clean else None


# ===========================================================================
# Tổng hợp (aggregate) theo nhóm key
# ===========================================================================
def aggregate(rows):
    """
    Gộp các row theo key (scenario, test_type, description, load_level).
    Tính trung bình các metric số.
    """
    groups = defaultdict(list)
    for row in rows:
        key = (
            row.get('scenario', ''),
            row.get('test_type', ''),
            row.get('description', ''),
            row.get('load_level', ''),
        )
        groups[key].append(row)

    numeric_fields = [
        'avg_delay_ms', 'min_delay_ms', 'max_delay_ms',
        'throughput_mbps', 'tcp_throughput_mbps',
        'jitter_ms', 'udp_loss_pct', 'ping_loss_pct',
    ]

    agg_rows = []
    for (scenario, test_type, desc, load), group in sorted(groups.items()):
        sample = group[0]  # Lấy metadata từ bản ghi đầu
        agg = {
            'scenario':    scenario,
            'arch_name':   sample.get('arch_name', ''),
            'test_type':   test_type,
            'description': desc,
            'load_level':  load,
            'n_samples':   len(group),
        }
        for field in numeric_fields:
            vals = [safe_float(r.get(field)) for r in group]
            agg[field] = _avg(vals)

        agg_rows.append(agg)

    return agg_rows


# ===========================================================================
# Tạo dữ liệu giả (mock) để test khi chưa có Mininet
# ===========================================================================
def generate_mock_data():
    """
    Tạo dữ liệu giả hợp lý dựa trên đặc tính mỗi kiến trúc:
    - Flat     : delay thấp (ít hop), nhưng có broadcast storm, loss cao hơn
    - 3-tier   : delay trung bình (qua nhiều switch), VLAN giảm broadcast
    - Leaf-Spine: delay thấp + ổn định (2 hop), throughput cao

    Mô phỏng đặc tính lý thuyết từ kienthuc.txt.
    """
    random.seed(42)  # Cố định seed để reproducible

    LOAD_LEVELS = ['10Mbps', '50Mbps', '100Mbps']

    # Tham số đặc trưng mỗi kiến trúc (avg_delay, jitter_base, loss_base)
    ARCH_PARAMS = {
        'flat': {
            'name':        'Flat Network (Chi nhánh 1)',
            'intra_delay': 0.8,  # ms – cùng switch, delay thấp
            'cross_delay': 8.5,  # ms – qua backbone MPLS
            'jitter':      0.15, # ms – mạng phẳng có nhiều broadcast
            'intra_loss':  0.2,  # % – gần như không mất trong LAN nhỏ
            'cross_loss':  0.5,  # % – có thể mất qua backbone
            # Throughput giảm theo tải (broadcast overhead tăng)
            'tp_factor':   {
                '10Mbps':  9.8, '50Mbps': 46.2, '100Mbps': 88.5,
            },
        },
        '3tier': {
            'name':        '3-Tier Network (Chi nhánh 2)',
            'intra_delay': 2.1,  # ms – qua nhiều switch layer
            'cross_delay': 10.2, # ms – qua backbone
            'jitter':      0.22, # ms – ổn định hơn nhờ VLAN phân tách
            'intra_loss':  0.1,  # % – ít hơn Flat nhờ VLAN
            'cross_loss':  0.4,
            'tp_factor':   {
                '10Mbps':  9.7, '50Mbps': 47.8, '100Mbps': 91.2,
            },
        },
        'leafspine': {
            'name':        'Leaf-Spine Network (Chi nhánh 3)',
            'intra_delay': 0.9,  # ms – 2 hop cố định, delay ổn định
            'cross_delay': 8.8,  # ms – qua backbone
            'jitter':      0.08, # ms – rất thấp, mọi path equal-cost
            'intra_loss':  0.0,  # % – gần như không mất (no STP)
            'cross_loss':  0.3,
            'tp_factor':   {
                '10Mbps':  10.0, '50Mbps': 49.5, '100Mbps': 98.1,
            },
        },
    }

    PAIRS_BY_ARCH = {
        'flat': [
            ('intra', 'host1', '10.1.0.102', 'host1→host2 [intra-flat]'),
            ('intra', 'host1', '10.1.0.103', 'host1→host3 [intra-flat]'),
            ('cross', 'host1', '10.2.10.11', 'host1→admin1 [flat→3tier]'),
            ('cross', 'host1', '10.3.10.11', 'host1→web1 [flat→leafspine]'),
        ],
        '3tier': [
            ('intra', 'admin1', '10.2.10.12', 'admin1→admin2 [same-VLAN10]'),
            ('intra', 'admin1', '10.2.20.21', 'admin1→lab1 [inter-VLAN]'),
            ('intra', 'admin1', '10.2.30.31', 'admin1→guest1 [inter-VLAN]'),
            ('cross', 'admin1', '10.1.0.101', 'admin1→host1 [3tier→flat]'),
            ('cross', 'admin1', '10.3.10.11', 'admin1→web1 [3tier→leafspine]'),
        ],
        'leafspine': [
            ('intra', 'web1', '10.3.10.12', 'web1→web2 [same-leaf1]'),
            ('intra', 'web1', '10.3.20.21', 'web1→dns1 [leaf1→leaf2, 2hop]'),
            ('intra', 'web1', '10.3.30.31', 'web1→db1 [leaf1→leaf3, 2hop]'),
            ('cross', 'web1', '10.1.0.101', 'web1→host1 [leafspine→flat]'),
            ('cross', 'web1', '10.2.10.11', 'web1→admin1 [leafspine→3tier]'),
        ],
    }

    ts   = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    rows = []

    for arch, params in ARCH_PARAMS.items():
        pairs = PAIRS_BY_ARCH[arch]
        for load_label in LOAD_LEVELS:
            for test_type, src, dst_ip, desc in pairs:

                delay_base = (params['intra_delay'] if test_type == 'intra'
                              else params['cross_delay'])
                loss_base  = (params['intra_loss'] if test_type == 'intra'
                              else params['cross_loss'])
                jitter     = params['jitter']
                tp_target  = params['tp_factor'][load_label]

                # Thêm nhiễu ngẫu nhiên nhỏ (±5%)
                noise = lambda x, pct=0.05: x * (1 + random.uniform(-pct, pct))

                row = {
                    'scenario':              arch,
                    'arch_name':             params['name'],
                    'test_type':             test_type,
                    'src_host':              src,
                    'dst_ip':                dst_ip,
                    'description':           desc,
                    'load_level':            load_label,
                    'bandwidth_target':      load_label.replace('bps',''),
                    'avg_delay_ms':          round(noise(delay_base), 3),
                    'min_delay_ms':          round(delay_base * 0.85, 3),
                    'max_delay_ms':          round(delay_base * 1.25, 3),
                    'ping_loss_pct':         round(max(0, noise(loss_base, 0.3)), 2),
                    'throughput_mbps':       round(noise(tp_target), 3),
                    'tcp_throughput_mbps':   round(noise(tp_target * 0.95), 3),
                    'jitter_ms':             round(noise(jitter), 4),
                    'udp_loss_pct':          round(max(0, noise(loss_base * 0.8, 0.3)), 2),
                    'timestamp':             ts,
                    'repeat':                3,
                }
                rows.append(row)

    return rows


# ===========================================================================
# Main
# ===========================================================================
def main():
    parser = argparse.ArgumentParser(
        description='Tổng hợp kết quả đo vào CSV chuẩn (dùng cho plot)')
    parser.add_argument('--csv', nargs='+', default=None,
                        help='File CSV đầu vào (có thể nhiều file)')
    parser.add_argument('--dir', default=None,
                        help='Thư mục chứa CSV (sẽ đọc tất cả *.csv)')
    parser.add_argument('--output', default=None,
                        help='Đường dẫn CSV tổng hợp output')
    parser.add_argument('--generate-mock', action='store_true',
                        help='Tạo dữ liệu giả lập và lưu CSV (dùng khi chưa có Mininet)')
    args = parser.parse_args()

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = args.output or os.path.join(CSV_DIR, f'aggregated_{ts}.csv')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if args.generate_mock:
        print('*** Tạo dữ liệu giả lập (mock)...')
        rows = generate_mock_data()
        agg  = aggregate(rows)

        # Lưu raw mock
        raw_path = os.path.join(CSV_DIR, f'mock_raw_{ts}.csv')
        with open(raw_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f'  Raw mock data → {raw_path} ({len(rows)} rows)')

        # Lưu aggregated
        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=AGG_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(agg)

        print(f'  Aggregated    → {out_path} ({len(agg)} rows)')
        print(f'\n  Để vẽ biểu đồ:\n    python3 scripts/plot_results.py --csv {out_path}')
        return 0

    # Đọc từ file CSV thật
    filepaths = []
    if args.csv:
        filepaths.extend(args.csv)
    if args.dir:
        filepaths.extend(str(p) for p in Path(args.dir).glob('*.csv'))
        filepaths = [f for f in filepaths
                     if 'aggregated' not in os.path.basename(f)]

    if not filepaths:
        print('Không có file CSV nào. Dùng --generate-mock để tạo dữ liệu giả.')
        return 1

    all_rows = []
    for fp in filepaths:
        print(f'  Đọc: {fp}')
        all_rows.extend(read_csv(fp))

    print(f'\n  Tổng {len(all_rows)} records, đang tổng hợp...')
    agg = aggregate(all_rows)

    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=AGG_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(agg)

    print(f'  Kết quả → {out_path} ({len(agg)} rows)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
