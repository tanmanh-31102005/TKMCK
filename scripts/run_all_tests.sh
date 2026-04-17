#!/bin/bash
# =============================================================================
# FILE: scripts/run_all_tests.sh
# MÔ TẢ: Chạy TOÀN BỘ bộ đo – 3 kiến trúc + tạo CSV tổng hợp + vẽ biểu đồ
#
# QUY TRÌNH TỰ ĐỘNG:
#   1. Chạy đo tự động cho cả 3 scenario (flat, 3tier, leafspine)
#         → dùng run_measurements.py (chỉ cần 1 lần start Mininet)
#   2. Aggregate kết quả → CSV tổng
#   3. Vẽ 8 biểu đồ so sânh → results/charts/
#
# Cách dùng:
#   chmod +x scripts/run_all_tests.sh
#   sudo bash scripts/run_all_tests.sh
#
#   Để chỉ dùng dữ liệu mock (khi chưa có Mininet):
#   bash scripts/run_all_tests.sh --mock
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TOPO_DIR="$PROJECT_DIR/topology"
CSV_DIR="$PROJECT_DIR/results/csv"
CHART_DIR="$PROJECT_DIR/results/charts"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

MOCK_MODE=false
if [[ "$1" == "--mock" ]]; then
    MOCK_MODE=true
fi

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   METRO ETHERNET MPLS – MEASUREMENT TOOLKIT              ║"
echo "║   Đề tài: Thiết kế mạng Metro Ethernet sử dụng MPLS     ║"
echo "║   Sinh viên: Nguyễn Tấn Mạnh – MSSV: 52300221             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Timestamp : $TIMESTAMP"
echo "  Mock mode : $MOCK_MODE"
echo ""

mkdir -p "$CSV_DIR" "$CHART_DIR"

# ===========================================================================
if [ "$MOCK_MODE" = true ]; then
    # ==========================
    # Chế độ MOCK: không cần Mininet
    # ==========================
    echo "╔═══════════════════════════════════════════╗"
    echo "║  CHẾ ĐỘ MOCK – Tạo dữ liệu giả lập       ║"
    echo "╚═══════════════════════════════════════════╝"
    
    cd "$PROJECT_DIR"
    AGG_CSV="$CSV_DIR/aggregated_mock_$TIMESTAMP.csv"
    
    python3 scripts/aggregate_results.py \
        --generate-mock \
        --output "$AGG_CSV"
    
    echo ""
    echo "*** Vẽ 8 biểu đồ từ dữ liệu giả lập..."
    python3 scripts/plot_results.py --csv "$AGG_CSV"

else
    # ==========================
    # Chế độ THỰC: chạy Mininet
    # ==========================
    echo "╔═══════════════════════════════════════════╗"
    echo "║  CHẾ ĐỘ THỰC – Chạy Mininet               ║"
    echo "╚═══════════════════════════════════════════╝"
    
    # Kiểm tra quyền root
    if [ "$EUID" -ne 0 ]; then
        echo "LỖI: Cần chạy với sudo!"
        echo "  sudo bash scripts/run_all_tests.sh"
        exit 1
    fi
    
    # Kiểm tra Mininet
    if ! command -v mn &>/dev/null; then
        echo "LỖI: Mininet chưa cài đặt!"
        echo "  sudo apt-get install mininet"
        exit 1
    fi
    
    # Kiểm tra iperf3
    if ! command -v iperf3 &>/dev/null; then
        echo "CẢNH BÁO: iperf3 chưa cài đặt. Cài bằng:"
        echo "  sudo apt-get install iperf3"
        exit 1
    fi
    
    echo ""
    echo "[BƯỚC 1/3] Dọn dẹp Mininet..."
    sudo mn -c 2>/dev/null || true
    sleep 2
    
    echo ""
    echo "[BƯỚC 2/3] Chạy đo 3 scenario (flat + 3tier + leafspine)..."
    cd "$PROJECT_DIR"
    
    MEAS_CSV="$CSV_DIR/results_$TIMESTAMP.csv"
    
    sudo python3 scripts/run_measurements.py \
        --scenario all \
        --verbose 2>&1 | tee "$CSV_DIR/measurements_$TIMESTAMP.log"
    
    # Tìm CSV mới nhất vừa tạo
    MEAS_CSV=$(ls -t "$CSV_DIR"/results_*.csv 2>/dev/null | head -1)
    
    if [ -z "$MEAS_CSV" ]; then
        echo "LỖI: Không tìm thấy CSV kết quả! Chuyển sang mock mode..."
        MOCK_MODE=true
    fi
    
    if [ "$MOCK_MODE" = false ]; then
        echo ""
        echo "[BƯỚC 3/3] Aggregate + Plot..."
        
        AGG_CSV="$CSV_DIR/aggregated_$TIMESTAMP.csv"
        python3 scripts/aggregate_results.py --csv "$MEAS_CSV" --output "$AGG_CSV"
        python3 scripts/plot_results.py --csv "$AGG_CSV"
    fi
    
    # Fallback mock nếu cần
    if [ "$MOCK_MODE" = true ]; then
        echo "*** Tạo biểu đồ từ dữ liệu giả lập thay thế..."
        python3 scripts/aggregate_results.py --generate-mock \
            --output "$CSV_DIR/aggregated_mock_$TIMESTAMP.csv"
        python3 scripts/plot_results.py \
            --csv "$CSV_DIR/aggregated_mock_$TIMESTAMP.csv"
    fi
fi

# ===========================================================================
# Tóm tắt kết quả
# ===========================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    HOÀN TẤT!                             ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Kết quả được lưu tại:                                   ║"
echo "║    CSV  : $CSV_DIR/"
echo "║    Chart: $CHART_DIR/"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  Danh sách biểu đồ đã tạo:                               ║"
for f in "$CHART_DIR"/*.png; do
    [ -f "$f" ] && echo "║    → $(basename "$f")"
done
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "  Đưa biểu đồ vào LaTeX báo cáo:"
echo "    \\includegraphics[width=\\linewidth]{../results/charts/throughput_comparison.png}"
echo ""
