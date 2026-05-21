#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: scripts/parse_iperf.py
MÔ TẢ: Parser cho kết quả iperf3 – trích Throughput, Jitter, Packet Loss

INPUT : File text chứa output JSON của iperf3 (-J flag)
         hoặc output text thường của iperf3
OUTPUT: Dict với các trường:
          protocol (tcp/udp)
          bits_per_second, throughput_mbps
          jitter_ms (UDP only)
          lost_packets, total_packets, loss_pct (UDP only)
          retransmits (TCP only)

CÔNG THỨC JITTER (theo RFC 3550):
  J(i) = J(i-1) + (|D(i-1,i)| - J(i-1)) / 16
  Trong đó D(i-1,i) là hiệu transit time giữa 2 gói liên tiếp.
  iperf3 UDP tự tính jitter này và báo cáo trong output.

CÁCH DÙNG:
  python3 scripts/parse_iperf.py results/raw/flat_udp_host1_10.1.0.102_10Mbps_run1.txt
  python3 scripts/parse_iperf.py results/raw/*.txt --csv results/csv/iperf.csv
=============================================================================
"""

import re
import sys
import os
import csv
import json
import argparse
from pathlib import Path


# ===========================================================================
# Parse JSON output (từ iperf3 -J)
# ===========================================================================
def parse_iperf_json(text: str) -> dict:
    """
    Parse iperf3 JSON output.
    Ưu tiên dùng cách này vì đủ thông tin nhất.
    """
    result = {
        'protocol':       None,
        'throughput_mbps':None,
        'bits_per_second':None,
        'jitter_ms':      None,
        'lost_packets':   None,
        'total_packets':  None,
        'loss_pct':       None,
        'retransmits':    None,
        'duration_sec':   None,
        'bytes_sent':     None,
        'error':          None,
        'valid':          False,
    }

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as e:
        result['error'] = str(e)
        return result

    # Kiểm tra lỗi iperf3
    if 'error' in data:
        result['error'] = data['error']
        return result

    start = data.get('start', {})
    end   = data.get('end', {})

    # Xác định protocol
    test_info = start.get('test_start', {})
    protocol  = 'udp' if test_info.get('protocol') == 'UDP' else 'tcp'
    result['protocol'] = protocol

    if protocol == 'udp':
        # UDP: từ sum (receiver side)
        udp_sum = end.get('sum', {})
        if udp_sum:
            bps = udp_sum.get('bits_per_second', 0)
            result['bits_per_second'] = bps
            result['throughput_mbps'] = round(bps / 1e6, 4)
            result['jitter_ms']       = round(udp_sum.get('jitter_ms', 0), 4)
            result['lost_packets']    = udp_sum.get('lost_packets', 0)
            result['total_packets']   = udp_sum.get('packets', 0)
            result['bytes_sent']      = udp_sum.get('bytes', 0)
            total = result['total_packets']
            lost  = result['lost_packets']
            result['loss_pct'] = round(lost / total * 100, 2) if total > 0 else 0
            result['valid'] = True
    else:
        # TCP: từ sum_received (throughput chính xác hơn ở receiver)
        tcp_sum = end.get('sum_received', end.get('sum', {}))
        if tcp_sum:
            bps = tcp_sum.get('bits_per_second', 0)
            result['bits_per_second'] = bps
            result['throughput_mbps'] = round(bps / 1e6, 4)
            result['bytes_sent']      = tcp_sum.get('bytes', 0)
            result['retransmits']     = end.get('sum_sent', {}).get('retransmits', 0)
            result['valid'] = True

    return result


# ===========================================================================
# Parse text output (fallback khi không có JSON)
# ===========================================================================
# Ví dụ text UDP:
# [ 5]  0.00-10.00 sec  12.5 MBytes  10.5 Mbits/sec  0.143 ms  0/8928 (0%)
UDP_LINE_RE = re.compile(
    r'\[\s*\d+\]\s+[\d.]+-[\d.]+\s+sec\s+'
    r'[\d.]+\s+\w+Bytes\s+'
    r'([\d.]+)\s+Mbits/sec\s+'
    r'([\d.]+)\s+ms\s+'
    r'(\d+)/(\d+)\s+\(([\d.]+)%\)'
)

# Ví dụ text TCP:
# [ 5]  0.00-10.00 sec  119 MBytes  99.8 Mbits/sec
TCP_LINE_RE = re.compile(
    r'\[\s*\d+\]\s+[\d.]+-[\d.]+\s+sec\s+'
    r'[\d.]+\s+\w+Bytes\s+'
    r'([\d.]+)\s+Mbits/sec'
)


def parse_iperf_text(text: str) -> dict:
    """
    Fallback parser cho iperf3 text output (không JSON).
    """
    result = {
        'protocol':       None,
        'throughput_mbps':None,
        'jitter_ms':      None,
        'lost_packets':   None,
        'total_packets':  None,
        'loss_pct':       None,
        'retransmits':    None,
        'valid':          False,
        'error':          None,
    }

    if not text:
        return result

    # Thử UDP pattern
    matches = UDP_LINE_RE.findall(text)
    if matches:
        result['protocol'] = 'udp'
        # Lấy dòng cuối cùng (sender/receiver summary)
        last = matches[-1]
        result['throughput_mbps'] = float(last[0])
        result['jitter_ms']       = float(last[1])
        result['lost_packets']    = int(last[2])
        result['total_packets']   = int(last[3])
        result['loss_pct']        = float(last[4])
        result['valid']           = True
        return result

    # Thử TCP pattern
    matches = TCP_LINE_RE.findall(text)
    if matches:
        result['protocol'] = 'tcp'
        result['throughput_mbps'] = float(matches[-1])
        result['valid'] = True
        # Tìm retransmits
        m = re.search(r'(\d+)\s+sender', text)
        if not m:
            m = re.search(r'(\d+)\s+retransmits', text)
        if m:
            result['retransmits'] = int(m.group(1))
        return result

    result['error'] = 'Không parse được (không match pattern UDP hay TCP)'
    return result


# ===========================================================================
# Hàm chính: parse 1 file
# ===========================================================================
def parse_iperf_file(filepath: str) -> dict:
    """Đọc file và parse (thử JSON trước, text sau)."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except FileNotFoundError:
        return {'valid': False, 'error': f'File not found: {filepath}'}

    if not text.strip():
        return {'valid': False, 'error': 'Empty file'}

    # Thử JSON
    result = parse_iperf_json(text)
    if not result['valid']:
        # Fallback text
        result = parse_iperf_text(text)

    result['source_file'] = os.path.basename(filepath)
    return result


def extract_metadata_from_filename(filename: str) -> dict:
    """
    Trích metadata từ tên file:
    <scenario>_udp_<src>_<dst_ip>_<load>_run<N>_<timestamp>.txt
    """
    meta = {
        'scenario':  '',
        'protocol':  '',
        'src_host':  '',
        'dst_ip':    '',
        'load_level':'',
        'run':       '',
    }
    name  = os.path.splitext(os.path.basename(filename))[0]
    parts = name.split('_')

    idx = 0
    try:
        meta['scenario']   = parts[idx]; idx += 1
        meta['protocol']   = parts[idx]; idx += 1  # 'udp' or 'tcp'
        meta['src_host']   = parts[idx]; idx += 1
        meta['dst_ip']     = parts[idx]; idx += 1
        meta['load_level'] = parts[idx]; idx += 1
        run_part = next((p for p in parts[idx:] if p.startswith('run')), '')
        meta['run']        = run_part.replace('run', '')
    except (IndexError, StopIteration):
        pass

    return meta


CSV_FIELDS = [
    'source_file', 'scenario', 'protocol', 'src_host', 'dst_ip',
    'load_level', 'run',
    'throughput_mbps', 'jitter_ms',
    'lost_packets', 'total_packets', 'loss_pct',
    'retransmits',
]


def files_to_csv(filepaths, csv_output=None):
    """Parse nhiều file và ghi CSV."""
    rows = []
    for fp in filepaths:
        result = parse_iperf_file(fp)
        meta   = extract_metadata_from_filename(fp)
        if result.get('valid'):
            row = {**meta}
            for f in CSV_FIELDS:
                if f not in row:
                    row[f] = result.get(f, '')
            rows.append(row)
            print(f'  [OK] {os.path.basename(fp)} ({result["protocol"]}): '
                  f'tput={result["throughput_mbps"]} Mbps '
                  f'jitter={result["jitter_ms"]} ms '
                  f'loss={result["loss_pct"]}%')
        else:
            print(f'  [SKIP] {os.path.basename(fp)}: {result.get("error", "unknown")}')

    if csv_output and rows:
        os.makedirs(os.path.dirname(csv_output) or '.', exist_ok=True)
        with open(csv_output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        print(f'\n  CSV đã lưu: {csv_output} ({len(rows)} records)')

    return rows


def main():
    parser = argparse.ArgumentParser(
        description='Parse iperf3 output – trích Throughput/Jitter/Loss')
    parser.add_argument('files', nargs='+',
                        help='Các file iperf3 output cần parse')
    parser.add_argument('--csv', default=None,
                        help='File CSV output path')
    args = parser.parse_args()

    filepaths = []
    for pattern in args.files:
        if '*' in pattern or '?' in pattern:
            filepaths.extend(str(p) for p in Path('.').glob(pattern))
        else:
            filepaths.append(pattern)

    if not filepaths:
        print('Không tìm thấy file nào.')
        return 1

    print(f'Parse {len(filepaths)} file(s)...\n')
    files_to_csv(filepaths, args.csv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
