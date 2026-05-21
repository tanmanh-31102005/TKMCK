#!/bin/bash
# =============================================================================
# FILE: scripts/run_leafspine_tests.sh
# MÔ TẢ: Chạy đo hiệu năng Chi nhánh 3 – Mạng Leaf-Spine
#
# Đặc điểm Leaf-Spine cần kiểm chứng:
#   - Intra-leaf: web1→web2 (cùng leaf1, 1 hop)
#   - Cross-leaf: web1→dns1 (leaf1→spine→leaf2, 2 hop)
#   - Cross-leaf: web1→db1  (leaf1→spine→leaf3, 2 hop)
#   - Cross-branch qua backbone MPLS
#
# Mục tiêu lý thuyết: tất cả cross-leaf đều 2 hop → delay ít hơn 3-tier
# Cách dùng:
#   sudo bash scripts/run_leafspine_tests.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOPO_DIR="$PROJECT_DIR/topology"
RAW_DIR="$PROJECT_DIR/results/raw"
CSV_DIR="$PROJECT_DIR/results/csv"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$RAW_DIR/leafspine_$TIMESTAMP"

echo "============================================================"
echo "  ĐO HIỆU NĂNG CHI NHÁNH 3 – MẠNG LEAF-SPINE"
echo "  Kiểm chứng: any-to-any path qua đúng 2 hop"
echo "  Timestamp: $TIMESTAMP"
echo "============================================================"

mkdir -p "$LOG_DIR" "$CSV_DIR"
sudo mn -c 2>/dev/null || true
sleep 1

echo "*** Khởi động đo tự động (scenario: leafspine)..."
cd "$TOPO_DIR"

sudo python3 -c "
import sys, os, time
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
    # Intra-leaf: cùng leaf switch
    ('web1', net['web2'],  '10.3.10.12', 'leafspine_web1→web2_intraleaf1'),
    ('dns1', net['dns2'],  '10.3.20.22', 'leafspine_dns1→dns2_intraleaf2'),
    # Cross-leaf: qua spine (2 hop cố định – bằng chứng Leaf-Spine)
    ('web1', net['dns1'],  '10.3.20.21', 'leafspine_web1→dns1_crossleaf_2hop'),
    ('web1', net['db1'],   '10.3.30.31', 'leafspine_web1→db1_crossleaf_2hop'),
    ('dns1', net['db2'],   '10.3.30.32', 'leafspine_dns1→db2_crossleaf_2hop'),
    ('db1',  net['web2'],  '10.3.10.12', 'leafspine_db1→web2_crossleaf_2hop'),
    # Cross-branch qua backbone MPLS
    ('web1', net['host1'], '10.1.0.101', 'leafspine_web1→host1_cross_flat'),
    ('web1', net['admin1'],'10.2.10.11', 'leafspine_web1→admin1_cross_3tier'),
]

print('*** Bắt đầu đo ping + iperf3...')
for src_name, dst_node, dst_ip, label in PAIRS:
    src_node = net[src_name]
    
    # Ping
    for run in range(1, 4):
        print(f'  ping {label} run{run}...')
        out = src_node.cmd(f'ping -c {PING_COUNT} -i 0.05 {dst_ip}')
        with open(f'{LOG_DIR}/{label}_ping_run{run}.txt', 'w') as f:
            f.write(out)
    
    # iperf3 UDP
    for bw, label_bw in LOADS:
        for run in range(1, 4):
            print(f'  iperf3 UDP {label} @{label_bw} run{run}...')
            dst_node.cmd('pkill -f \"iperf3 -s\" 2>/dev/null; sleep 0.2')
            dst_node.cmd('iperf3 -s -D --one-off 2>/dev/null')
            time.sleep(0.3)
            out = src_node.cmd(f'iperf3 -c {dst_ip} -u -b {bw} -t {IPERF_DUR} -J 2>/dev/null')
            with open(f'{LOG_DIR}/{label}_udp_{label_bw}_run{run}.txt', 'w') as f:
                f.write(out)
            dst_node.cmd('pkill -f \"iperf3 -s\" 2>/dev/null')
            time.sleep(0.2)

print('*** Xong!')
net.stop()
" 2>&1 | tee "$LOG_DIR/leafspine_test_run.log"

echo ""
echo "*** Parse kết quả..."
cd "$PROJECT_DIR"

python3 scripts/parse_ping.py  "$LOG_DIR"/*_ping_*.txt  --csv "$CSV_DIR/leafspine_ping_$TIMESTAMP.csv"  2>/dev/null || true
python3 scripts/parse_iperf.py "$LOG_DIR"/*_udp_*.txt   --csv "$CSV_DIR/leafspine_iperf_$TIMESTAMP.csv" 2>/dev/null || true

echo ""
echo "============================================================"
echo "  KẾT QUẢ ĐÃ LƯU:"
echo "    Log dir  : $LOG_DIR/"
echo "    Ping CSV : $CSV_DIR/leafspine_ping_$TIMESTAMP.csv"
echo "    Iperf CSV: $CSV_DIR/leafspine_iperf_$TIMESTAMP.csv"
echo "============================================================"
