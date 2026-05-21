#!/bin/bash
# =============================================================================
# FILE: scripts/run_flat_tests.sh
# MÔ TẢ: Chạy đo hiệu năng riêng cho Chi nhánh 1 – Mạng phẳng (Flat)
#
# Cách dùng:
#   chmod +x scripts/run_flat_tests.sh
#   sudo bash scripts/run_flat_tests.sh
# =============================================================================

set -e  # Dừng nếu có lỗi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOPO_DIR="$PROJECT_DIR/topology"
RAW_DIR="$PROJECT_DIR/results/raw"
CSV_DIR="$PROJECT_DIR/results/csv"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$RAW_DIR/flat_$TIMESTAMP"

echo "============================================================"
echo "  ĐO HIỆU NĂNG CHI NHÁNH 1 – MẠNG PHẲNG (FLAT NETWORK)"
echo "  Timestamp: $TIMESTAMP"
echo "============================================================"

# Tạo thư mục lưu kết quả
mkdir -p "$LOG_DIR" "$CSV_DIR"

# Dọn dẹp Mininet cũ (nếu còn)
echo "*** Dọn dẹp Mininet cũ..."
sudo mn -c 2>/dev/null || true
sleep 1

# ===========================================================================
# Chạy đo qua Python API (cách đáng tin cậy nhất với Mininet)
# ===========================================================================
echo "*** Khởi động đo tự động (scenario: flat)..."
cd "$TOPO_DIR"

sudo python3 -c "
import sys, os, time, json, re
sys.path.insert(0, '.')

from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel

setLogLevel('warning')
from metro_full import MetroFullTopo, configure_full_network

print('*** Khởi tạo topology...')
net = Mininet(topo=MetroFullTopo(), controller=None, link=TCLink)
net.start()
configure_full_network(net)
time.sleep(2)

LOG_DIR = '$LOG_DIR'
PING_COUNT = 100
IPERF_DUR  = 10
LOADS = [('10M','10Mbps'), ('50M','50Mbps'), ('100M','100Mbps')]

PAIRS = [
    ('host1', net['host2'], '10.1.0.102', 'host1→host2_intra'),
    ('host1', net['host3'], '10.1.0.103', 'host1→host3_intra'),
    ('host1', net['host4'], '10.1.0.104', 'host1→host4_intra'),
]

print('*** Bắt đầu đo ping + iperf3...')
for src_name, dst_node, dst_ip, label in PAIRS:
    src_node = net[src_name]
    
    # --- Ping test ---
    for run in range(1, 4):
        print(f'  ping {label} run{run}...')
        out = src_node.cmd(f'ping -c {PING_COUNT} -i 0.05 {dst_ip}')
        fname = f'{LOG_DIR}/flat_ping_{label}_run{run}.txt'
        with open(fname, 'w') as f:
            f.write(out)
    
    # --- iperf3 UDP test ---
    for bw, label_bw in LOADS:
        for run in range(1, 4):
            print(f'  iperf3 UDP {label} @{label_bw} run{run}...')
            dst_node.cmd('pkill -f \"iperf3 -s\" 2>/dev/null; sleep 0.2')
            dst_node.cmd('iperf3 -s -D --one-off 2>/dev/null')
            time.sleep(0.3)
            out = src_node.cmd(f'iperf3 -c {dst_ip} -u -b {bw} -t {IPERF_DUR} -J 2>/dev/null')
            fname = f'{LOG_DIR}/flat_udp_{src_name}_{dst_ip}_{label_bw}_run{run}.txt'
            with open(fname, 'w') as f:
                f.write(out)
            dst_node.cmd('pkill -f \"iperf3 -s\" 2>/dev/null')
            time.sleep(0.2)

print('*** Xong! Dọn dẹp...')
net.stop()
print(f'*** Log lưu tại: $LOG_DIR')
" 2>&1 | tee "$LOG_DIR/flat_test_run.log"

# ===========================================================================
# Parse kết quả
# ===========================================================================
echo ""
echo "*** Parse kết quả ping và iperf3..."
cd "$PROJECT_DIR"

python3 scripts/parse_ping.py "$LOG_DIR"/*_ping_*.txt \
    --csv "$CSV_DIR/flat_ping_$TIMESTAMP.csv" 2>/dev/null || true

python3 scripts/parse_iperf.py "$LOG_DIR"/*_udp_*.txt \
    --csv "$CSV_DIR/flat_iperf_$TIMESTAMP.csv" 2>/dev/null || true

echo ""
echo "============================================================"
echo "  KẾT QUẢ ĐÃ LƯU:"
echo "    Raw logs : $LOG_DIR/"
echo "    Ping CSV : $CSV_DIR/flat_ping_$TIMESTAMP.csv"
echo "    Iperf CSV: $CSV_DIR/flat_iperf_$TIMESTAMP.csv"
echo ""
echo "  Bước tiếp theo:"
echo "    python3 scripts/aggregate_results.py --dir $CSV_DIR"
echo "============================================================"
