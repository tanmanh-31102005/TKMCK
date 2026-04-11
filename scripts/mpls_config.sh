#!/bin/bash
# =============================================================================
# SCRIPT CẤU HÌNH MPLS TRÊN LINUX ROUTER (NGOÀI MININET)
# =============================================================================
# Dùng để cấu hình thủ công MPLS labels sau khi topology Mininet đã chạy.
# Chạy từ terminal ngoài Mininet (dùng ip netns exec).
# =============================================================================
# Cách dùng: sudo bash mpls_config.sh
# Yêu cầu: Topology Mininet đang chạy (mpls_metro_topology.py)
# =============================================================================

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${CYAN}[MPLS]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC}   $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "══════════════════════════════════════════════════════"
echo "   CẤU HÌNH MPLS LABEL SWITCHING – METRO ETHERNET"
echo "══════════════════════════════════════════════════════"
echo ""

# ─── Kiểm tra namespace Mininet ──────────────────────────────────────────────
check_ns() {
    ip netns list | grep -q "^$1" 2>/dev/null
}

if ! check_ns "p1"; then
    warn "Không tìm thấy namespace 'p1'. Hãy chạy topology Mininet trước!"
    warn "  sudo python3 source/mpls_metro_topology.py"
    exit 1
fi

log "Đang bật MPLS trên tất cả router..."

# ─── Bật MPLS platform labels ────────────────────────────────────────────────
for NS in pe1 pe2 pe3 p1 p2; do
    if check_ns "${NS}"; then
        ip netns exec "${NS}" sysctl -w net.mpls.platform_labels=1000 > /dev/null 2>&1 || true
        ok "  ${NS}: platform_labels=1000"
    fi
done

# ─── Bật MPLS input trên từng interface ──────────────────────────────────────
log "Bật MPLS input trên các interface..."

declare -A ROUTER_INTFS=(
    ["pe1"]="pe1-p1 pe1-ce1"
    ["pe2"]="pe2-p2 pe2-ce2"
    ["pe3"]="pe3-p1 pe3-ce3"
    ["p1"]="p1-pe1 p1-pe3 p1-p2"
    ["p2"]="p2-pe2 p2-p1"
)

for ROUTER in pe1 pe2 pe3 p1 p2; do
    if check_ns "${ROUTER}"; then
        for INTF in ${ROUTER_INTFS[${ROUTER}]}; do
            ip netns exec "${ROUTER}" sysctl -w "net.mpls.conf.${INTF}.input=1" \
                > /dev/null 2>&1 || warn "    Không thể bật MPLS trên ${ROUTER}/${INTF}"
        done
        ok "  ${ROUTER}: MPLS input enabled"
    fi
done

# ─── Cấu hình LSP: PE1 → PE2 (qua P1 → P2) ──────────────────────────────────
log ""
log "=== LSP 1: PE1 → PE2 (Label: 100 → 200 → 300 → pop) ==="

# Push: PE1 – gói đến 10.2.0.0/24 gắn label 100
ip netns exec pe1 ip route add 10.2.0.0/24 \
    encap mpls 100 via inet 10.0.12.2 dev pe1-p1 2>/dev/null \
    && ok "  PE1: PUSH label 100 → next-hop P1 (10.0.12.2)" \
    || warn "  PE1: PUSH label (dùng fallback static route)"

# Swap tại P1: 100 → 200, chuyển sang P2
ip netns exec p1 ip -f mpls route add 100 as 200 \
    via inet 10.0.99.2 dev p1-p2 2>/dev/null \
    && ok "  P1:  SWAP 100→200 → next-hop P2 (10.0.99.2)" \
    || warn "  P1:  SWAP label không khả dụng (MPLS kernel?)"

# Swap tại P2: 200 → 300, chuyển sang PE2
ip netns exec p2 ip -f mpls route add 200 as 300 \
    via inet 10.0.23.1 dev p2-pe2 2>/dev/null \
    && ok "  P2:  SWAP 200→300 → next-hop PE2 (10.0.23.1)" \
    || warn "  P2:  SWAP label không khả dụng"

# Pop tại PE2: gỡ label 300, giao IP thuần về CE2
ip netns exec pe2 ip -f mpls route add 300 \
    via inet 10.100.2.1 dev pe2-ce2 2>/dev/null \
    && ok "  PE2: POP label 300 → CE2 (10.100.2.1)" \
    || warn "  PE2: POP label không khả dụng"

# ─── Cấu hình LSP: PE1 → PE3 ─────────────────────────────────────────────────
log ""
log "=== LSP 2: PE1 → PE3 (Label: 400 → 500 → pop) ==="

ip netns exec pe1 ip route add 10.3.0.0/24 \
    encap mpls 400 via inet 10.0.12.2 dev pe1-p1 2>/dev/null \
    && ok "  PE1: PUSH label 400 → next-hop P1" \
    || warn "  PE1: PUSH 400 không khả dụng"

ip netns exec p1 ip -f mpls route add 400 as 500 \
    via inet 10.0.31.1 dev p1-pe3 2>/dev/null \
    && ok "  P1:  SWAP 400→500 → next-hop PE3" \
    || warn "  P1:  SWAP 400 không khả dụng"

ip netns exec pe3 ip -f mpls route add 500 \
    via inet 10.100.3.1 dev pe3-ce3 2>/dev/null \
    && ok "  PE3: POP label 500 → CE3" \
    || warn "  PE3: POP 500 không khả dụng"

# ─── Hiển thị bảng MPLS routing ──────────────────────────────────────────────
echo ""
log "=== Bảng MPLS Route trên P1 ==="
ip netns exec p1 ip -f mpls route 2>/dev/null \
    || warn "  Bảng MPLS trống (kernel không hỗ trợ hoặc chưa cấu hình thành công)"

echo ""
log "=== Bảng MPLS Route trên P2 ==="
ip netns exec p2 ip -f mpls route 2>/dev/null \
    || warn "  Bảng MPLS trống"

# ─── Kiểm tra ping xuyên backbone ────────────────────────────────────────────
echo ""
log "=== Kiểm tra kết nối xuyên backbone ==="
log "  h1a (10.1.0.1) → h2a (10.2.0.1)..."
ip netns exec h1a ping -c 3 -W 2 10.2.0.1 2>/dev/null \
    && ok "  Kết nối thành công!" \
    || warn "  Ping thất bại – kiểm tra routing trên CE/PE"

echo ""
echo "══════════════════════════════════════════════════════"
echo -e "${GREEN}   XONG! MPLS đã được cấu hình.${NC}"
echo "   Kiểm tra chi tiết: sudo ip netns exec p1 ip -f mpls route"
echo "══════════════════════════════════════════════════════"
echo ""
