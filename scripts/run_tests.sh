#!/bin/bash
# =============================================================================
# SCRIPT ĐO LƯỜNG HIỆU NĂNG – METRO ETHERNET MPLS
# =============================================================================
# Sinh viên: Huỳnh Văn Dũng – MSSV: 52300190
# Mục tiêu: Tự động hóa đo Throughput, Delay, Packet Loss, Jitter
#           cho 3 kịch bản tương ứng 3 kiến trúc LAN chi nhánh.
# =============================================================================
# Cách dùng: sudo bash run_tests.sh [scenario] [duration]
#   scenario: 1 (flat), 2 (3tier), 3 (leafspine), all (mặc định)
#   duration: thời gian iperf (giây, mặc định 10)
# =============================================================================

set -euo pipefail

# ─── Thư mục lưu kết quả ────────────────────────────────────────────────────
RESULTS_DIR="../results"
RAW_DIR="${RESULTS_DIR}/raw"
CSV_DIR="${RESULTS_DIR}/csv"
CHARTS_DIR="${RESULTS_DIR}/charts"

mkdir -p "${RAW_DIR}" "${CSV_DIR}" "${CHARTS_DIR}"

SCENARIO="${1:-all}"
DURATION="${2:-10}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─── Màu sắc terminal ────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log_info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}   $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()   { echo -e "${RED}[ERR]${NC}  $1"; }

echo ""
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   ĐO LƯỜNG HIỆU NĂNG – METRO ETHERNET MPLS BACKBONE${NC}"
echo -e "${BLUE}══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─── Hàm chạy ping và lưu log ──────────────────────────────────────────────
run_ping_test() {
    local SRC="$1"   # Tên node nguồn trong Mininet (vd: h1a)
    local DST="$2"   # Tên node đích trong Mininet (vd: h2a)
    local DST_IP="$3"
    local TAG="$4"   # Nhãn cho file log
    local COUNT="${5:-50}"

    log_info "Ping test: ${SRC} -> ${DST} (${DST_IP}), ${COUNT} gói"
    local LOGFILE="${RAW_DIR}/ping_${TAG}_${TIMESTAMP}.log"

    # Dùng mnexec hoặc ip netns exec để chạy lệnh trong namespace của Mininet node
    if ip netns list | grep -q "^${SRC}"; then
        ip netns exec "${SRC}" ping -c "${COUNT}" -i 0.2 -W 2 "${DST_IP}" \
            > "${LOGFILE}" 2>&1 || true
        log_ok "Saved: ${LOGFILE}"
    else
        log_warn "Namespace ${SRC} chưa có. Hãy chạy topology trước."
    fi
}

# ─── Hàm chạy iperf3 TCP (Throughput) ─────────────────────────────────────
run_iperf_tcp() {
    local SRC="$1"
    local DST="$2"
    local DST_IP="$3"
    local TAG="$4"

    log_info "iperf3 TCP: ${SRC} -> ${DST} (${DST_IP}), ${DURATION}s"
    local LOGFILE="${RAW_DIR}/iperf_tcp_${TAG}_${TIMESTAMP}.log"

    if ip netns list | grep -q "^${DST}"; then
        # Khởi server iperf3 trên dst
        ip netns exec "${DST}" iperf3 -s -D -p 5201 > /dev/null 2>&1 || true
        sleep 1
        # Chạy client iperf3 trên src
        ip netns exec "${SRC}" iperf3 -c "${DST_IP}" -p 5201 \
            -t "${DURATION}" -J > "${LOGFILE}" 2>&1 || true
        # Dừng server
        ip netns exec "${DST}" killall iperf3 2>/dev/null || true
        log_ok "Saved: ${LOGFILE}"
    else
        log_warn "Namespace ${DST} chưa có. Hãy chạy topology trước."
    fi
}

# ─── Hàm chạy iperf3 UDP (Jitter + Packet Loss) ─────────────────────────────
run_iperf_udp() {
    local SRC="$1"
    local DST="$2"
    local DST_IP="$3"
    local TAG="$4"
    local BANDWIDTH="${5:-10M}"

    log_info "iperf3 UDP: ${SRC} -> ${DST} (${DST_IP}), BW=${BANDWIDTH}, ${DURATION}s"
    local LOGFILE="${RAW_DIR}/iperf_udp_${TAG}_${TIMESTAMP}.log"

    if ip netns list | grep -q "^${DST}"; then
        ip netns exec "${DST}" iperf3 -s -D -p 5202 > /dev/null 2>&1 || true
        sleep 1
        ip netns exec "${SRC}" iperf3 -c "${DST_IP}" -p 5202 \
            -u -b "${BANDWIDTH}" -t "${DURATION}" -J > "${LOGFILE}" 2>&1 || true
        ip netns exec "${DST}" killall iperf3 2>/dev/null || true
        log_ok "Saved: ${LOGFILE}"
    else
        log_warn "Namespace ${DST} chưa có. Hãy chạy topology trước."
    fi
}

# ─── Hàm chạy toàn bộ kịch bản đo lường ─────────────────────────────────────
run_scenario() {
    local SC="$1"

    case "${SC}" in
        1)
            echo ""
            echo -e "${YELLOW}═══ KỊCH BẢN 1: MẠNG PHẲNG (FLAT NETWORK) ═══${NC}"
            echo "    Chi nhánh 1 (h1a,h1b,h1c) ↔ Chi nhánh 2 (h2a,h2b)"
            echo "    Chi nhánh 1 ↔ Chi nhánh 3 (h3a,h3b)"
            echo ""

            # Ping tests
            run_ping_test "h1a" "h2a" "10.2.0.1" "sc1_h1a_h2a" 50
            run_ping_test "h1a" "h3a" "10.3.0.1" "sc1_h1a_h3a" 50
            run_ping_test "h1b" "h2b" "10.2.0.2" "sc1_h1b_h2b" 50

            # iperf3 TCP (Throughput)
            run_iperf_tcp "h1a" "h2a" "10.2.0.1" "sc1_tcp_h1a_h2a"
            run_iperf_tcp "h1a" "h3a" "10.3.0.1" "sc1_tcp_h1a_h3a"

            # iperf3 UDP (Jitter + Loss)
            run_iperf_udp "h1a" "h2a" "10.2.0.1" "sc1_udp_h1a_h2a" "10M"
            run_iperf_udp "h1a" "h3a" "10.3.0.1" "sc1_udp_h1a_h3a" "10M"
            ;;

        2)
            echo ""
            echo -e "${YELLOW}═══ KỊCH BẢN 2: MẠNG 3 LỚP (CORE-DISTRIBUTION-ACCESS) ═══${NC}"
            echo ""

            run_ping_test "h2a" "h1a" "10.1.0.1" "sc2_h2a_h1a" 50
            run_ping_test "h2a" "h3a" "10.3.0.1" "sc2_h2a_h3a" 50
            run_ping_test "h2c" "h1c" "10.1.0.3" "sc2_h2c_h1c" 50

            run_iperf_tcp "h2a" "h1a" "10.1.0.1" "sc2_tcp_h2a_h1a"
            run_iperf_tcp "h2a" "h3a" "10.3.0.1" "sc2_tcp_h2a_h3a"

            run_iperf_udp "h2a" "h1a" "10.1.0.1" "sc2_udp_h2a_h1a" "10M"
            run_iperf_udp "h2a" "h3a" "10.3.0.1" "sc2_udp_h2a_h3a" "10M"
            ;;

        3)
            echo ""
            echo -e "${YELLOW}═══ KỊCH BẢN 3: MẠNG LEAF-SPINE ═══${NC}"
            echo ""

            run_ping_test "h3a" "h1a" "10.1.0.1" "sc3_h3a_h1a" 50
            run_ping_test "h3a" "h2a" "10.2.0.1" "sc3_h3a_h2a" 50
            run_ping_test "h3c" "h2c" "10.2.0.3" "sc3_h3c_h2c" 50

            run_iperf_tcp "h3a" "h1a" "10.1.0.1" "sc3_tcp_h3a_h1a"
            run_iperf_tcp "h3a" "h2a" "10.2.0.1" "sc3_tcp_h3a_h2a"

            run_iperf_udp "h3a" "h1a" "10.1.0.1" "sc3_udp_h3a_h1a" "10M"
            run_iperf_udp "h3a" "h2a" "10.2.0.1" "sc3_udp_h3a_h2a" "10M"
            ;;

        *)
            log_err "Kịch bản không hợp lệ: ${SC} (dùng 1, 2, 3 hoặc all)"
            ;;
    esac
}

# ─── Chạy kịch bản ──────────────────────────────────────────────────────────
if [[ "${SCENARIO}" == "all" ]]; then
    for SC in 1 2 3; do
        run_scenario "${SC}"
    done
else
    run_scenario "${SCENARIO}"
fi

# ─── Phân tích kết quả bằng Python ─────────────────────────────────────────
echo ""
log_info "Đang phân tích log và tạo CSV..."
if python3 collect_results.py "${RAW_DIR}" "${CSV_DIR}" "${CHARTS_DIR}" "${TIMESTAMP}"; then
    log_ok "Đã tạo CSV và biểu đồ!"
else
    log_warn "collect_results.py gặp lỗi hoặc chưa có dữ liệu."
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   HOÀN TẤT! Kết quả lưu tại: ${RESULTS_DIR}${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
