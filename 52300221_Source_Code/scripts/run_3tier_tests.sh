#!/bin/bash
# =============================================================================
# FILE: scripts/run_3tier_tests.sh
# MÔ TẢ: Chạy đo hiệu năng Chi nhánh 2 – Mạng 3 lớp (Core-Dist-Access)
#
# Bao gồm: đo intra (cùng VLAN), inter-VLAN, và cross-branch qua MPLS
# Cách dùng:
#   sudo bash scripts/run_3tier_tests.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOPO_DIR="$PROJECT_DIR/topology"
RAW_DIR="$PROJECT_DIR/results/raw"
CSV_DIR="$PROJECT_DIR/results/csv"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$RAW_DIR/3tier_$TIMESTAMP"

echo "============================================================"
echo "  ĐO HIỆU NĂNG CHI NHÁNH 2 – MẠNG 3 LỚP (3-TIER)"
echo "  Bao gồm: Intra-VLAN, Inter-VLAN, Cross-branch MPLS"
echo "  Timestamp: $TIMESTAMP"
echo "============================================================"

mkdir -p "$LOG_DIR" "$CSV_DIR"
sudo mn -c 2>/dev/null || true
sleep 1

echo "*** Khởi động đo tự động (scenario: 3tier)..."
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

# Test cases: intra-VLAN, inter-VLAN, cross-branch
PAIRS = [
    # Intra VLAN (cùng switch access)
    ('admin1', net['admin2'], '10.2.10.12', '3tier_admin1→admin2_intra_vlan10'),
    ('lab1',   net['lab2'],   '10.2.20.22', '3tier_lab1→lab2_intra_vlan20'),
    # Inter-VLAN (qua ce2_lan router)
    ('admin1', net['lab1'],   '10.2.20.21', '3tier_admin1→lab1_intervlan'),
    ('admin1', net['guest1'], '10.2.30.31', '3tier_admin1→guest1_intervlan'),
    ('lab1',   net['guest2'], '10.2.30.32', '3tier_lab1→guest2_intervlan'),
    # Cross-branch qua backbone MPLS
    ('admin1', net['host1'],  '10.1.0.101', '3tier_admin1→host1_cross_flat'),
    ('admin1', net['web1'],   '10.3.10.11', '3tier_admin1→web1_cross_leafspine'),
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
" 2>&1 | tee "$LOG_DIR/3tier_test_run.log"

echo ""
echo "*** Parse kết quả..."
cd "$PROJECT_DIR"

python3 scripts/parse_ping.py  "$LOG_DIR"/*_ping_*.txt  --csv "$CSV_DIR/3tier_ping_$TIMESTAMP.csv"  2>/dev/null || true
python3 scripts/parse_iperf.py "$LOG_DIR"/*_udp_*.txt   --csv "$CSV_DIR/3tier_iperf_$TIMESTAMP.csv" 2>/dev/null || true

echo ""
echo "============================================================"
echo "  KẾT QUẢ ĐÃ LƯU:"
echo "    Log dir  : $LOG_DIR/"
echo "    Ping CSV : $CSV_DIR/3tier_ping_$TIMESTAMP.csv"
echo "    Iperf CSV: $CSV_DIR/3tier_iperf_$TIMESTAMP.csv"
echo "============================================================"
