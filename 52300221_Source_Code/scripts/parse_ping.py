#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
FILE: scripts/parse_ping.py
MÔ TẢ: Parser cho kết quả ping – trích xuất Delay, Packet Loss, Jitter

INPUT : File text chứa output của lệnh ping
OUTPUT: Dict hoặc CSV row với các trường:
          min_ms, avg_ms, max_ms, mdev_ms (Jitter gần đúng), loss_pct

Về tính Jitter từ ping:
  Jitter = mdev (mean deviation of RTT) theo RFC 3550.
  Linux ping báo "mdev = X ms" – đây là xấp xỉ tốt của Jitter.

CÁCH DÙNG:
  python3 scripts/parse_ping.py results/raw/flat_ping_host1_10.1.0.102_run1.txt
  python3 scripts/parse_ping.py results/raw/*.txt  --csv results/csv/ping.csv
=============================================================================
"""

import re
import sys
import os
import csv
import argparse
from pathlib import Path


# ===========================================================================
# Regex patterns cho output ping Linux
# ===========================================================================

# Packet loss: "35 packets transmitted, 34 received, 2% packet loss, time 3429ms"
LOSS_RE = re.compile(
    r'(\d+) packets transmitted,\s+'
    r'(\d+) received,.*?'
    r'([\d.]+)% packet loss'
)

# RTT stats: "rtt min/avg/max/mdev = 0.145/0.287/0.512/0.089 ms"
RTT_RE = re.compile(
    r'rtt min/avg/max/mdev\s*=\s*'
    r'([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms'
)

# Mỗi dòng ping riêng lẻ để tính jitter chi tiết hơn
# "64 bytes from 10.1.0.102: icmp_seq=1 ttl=64 time=0.287 ms"
PING_LINE_RE = re.compile(r'time=([\d.]+)\s*ms')


def parse_ping_output(text: str) -> dict:
    """
    Parse output text của lệnh ping.
    
    Trả về dict:
      tx_pkts      : số gói đã gửi
      rx_pkts      : số gói nhận được
      loss_pct     : % mất gói
      min_ms       : RTT min (ms)
      avg_ms       : RTT avg (ms)
      max_ms       : RTT max (ms)
      mdev_ms      : RTT mdev (ms) – dùng làm Jitter
      jitter_ms    : Jitter = mdev (ms) theo RFC 3550 approximation
      rtt_samples  : list RTT từng gói (ms) – dùng để vẽ đồ thị
      valid        : True nếu parse thành công
    """
    result = {
        'tx_pkts':    None,
        'rx_pkts':    None,
        'loss_pct':   None,
        'min_ms':     None,
        'avg_ms':     None,
        'max_ms':     None,
        'mdev_ms':    None,
        'jitter_ms':  None,
        'rtt_samples': [],
        'valid':      False,
    }

    if not text or not text.strip():
        return result

    # Trích packet statistics
    m_loss = LOSS_RE.search(text)
    if m_loss:
        result['tx_pkts']  = int(m_loss.group(1))
        result['rx_pkts']  = int(m_loss.group(2))
        result['loss_pct'] = float(m_loss.group(3))

    # Trích RTT summary
    m_rtt = RTT_RE.search(text)
    if m_rtt:
        result['min_ms']  = float(m_rtt.group(1))
        result['avg_ms']  = float(m_rtt.group(2))
        result['max_ms']  = float(m_rtt.group(3))
        result['mdev_ms'] = float(m_rtt.group(4))
        # Jitter ≈ mdev (mean deviation ≈ half of standard deviation)
        result['jitter_ms'] = result['mdev_ms']
        result['valid'] = True

    # Trích từng sample RTT cho histogram/đồ thị
    result['rtt_samples'] = [
        float(m.group(1)) for m in PING_LINE_RE.finditer(text)
    ]

    # Fallback tính jitter từ samples nếu không có mdev
    if result['rtt_samples'] and result['jitter_ms'] is None:
        samples = result['rtt_samples']
        if len(samples) > 1:
            avg = sum(samples) / len(samples)
            diffs = [abs(samples[i] - samples[i-1]) for i in range(1, len(samples))]
            result['jitter_ms'] = round(sum(diffs) / len(diffs), 4)
            result['avg_ms']    = round(avg, 4)
            result['min_ms']    = round(min(samples), 4)
            result['max_ms']    = round(max(samples), 4)
            result['valid']     = True

    return result


def parse_ping_file(filepath: str) -> dict:
    """Đọc file và parse."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        result = parse_ping_output(text)
        result['source_file'] = os.path.basename(filepath)
        return result
    except FileNotFoundError:
        return {'valid': False, 'error': f'File not found: {filepath}'}


def extract_metadata_from_filename(filename: str) -> dict:
    """
    Trích metadata từ tên file theo convention:
    <scenario>_ping_<src>_<dst_ip>_run<N>_<timestamp>.txt
    """
    meta = {
        'scenario': '',
        'src_host': '',
        'dst_ip':   '',
        'run':      '',
        'timestamp':'',
    }
    name = os.path.splitext(os.path.basename(filename))[0]
    parts = name.split('_')

    try:
        meta['scenario']  = parts[0] if len(parts) > 0 else ''
        meta['src_host']  = parts[2] if len(parts) > 2 else ''
        meta['dst_ip']    = parts[3] if len(parts) > 3 else ''
        # run part: "run1" → "1"
        run_part = next((p for p in parts if p.startswith('run')), '')
        meta['run']       = run_part.replace('run', '')
    except (IndexError, StopIteration):
        pass

    return meta


CSV_FIELDS = [
    'source_file', 'scenario', 'src_host', 'dst_ip', 'run',
    'tx_pkts', 'rx_pkts', 'loss_pct',
    'min_ms', 'avg_ms', 'max_ms', 'mdev_ms', 'jitter_ms',
    'sample_count',
]


def files_to_csv(filepaths, csv_output=None):
    """Parse nhiều file và ghi CSV."""
    rows = []
    for fp in filepaths:
        result = parse_ping_file(fp)
        meta   = extract_metadata_from_filename(fp)
        if result.get('valid'):
            row = {**meta, **result}
            row['sample_count'] = len(result.get('rtt_samples', []))
            rows.append(row)
            print(f'  [OK] {os.path.basename(fp)}: '
                  f'loss={result["loss_pct"]}% '
                  f'avg={result["avg_ms"]}ms '
                  f'jitter={result["jitter_ms"]}ms')
        else:
            print(f'  [SKIP] {os.path.basename(fp)}: không parse được')

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
        description='Parse kết quả ping – trích Delay/Loss/Jitter')
    parser.add_argument('files', nargs='+',
                        help='Các file ping output cần parse (glob OK)')
    parser.add_argument('--csv', default=None,
                        help='Đường dẫn file CSV output')
    parser.add_argument('--show-samples', action='store_true',
                        help='In danh sách RTT mẫu')
    args = parser.parse_args()

    # Mở rộng glob nếu cần
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
    rows = files_to_csv(filepaths, args.csv)

    if args.show_samples:
        for fp in filepaths:
            result = parse_ping_file(fp)
            if result.get('rtt_samples'):
                print(f'\n  RTT samples [{os.path.basename(fp)}]:')
                print('  ' + ', '.join(f'{v:.3f}' for v in result['rtt_samples'][:20]))
                if len(result['rtt_samples']) > 20:
                    print(f'  ... và {len(result["rtt_samples"])-20} giá trị nữa')

    return 0


if __name__ == '__main__':
    sys.exit(main())
