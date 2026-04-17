# Measurement Toolkit – Hướng dẫn sử dụng

> **Đề tài**: Thiết kế và triển khai mạng Metro Ethernet sử dụng MPLS cho kết nối đa chi nhánh doanh nghiệp  
> **Sinh viên**: Huỳnh Văn Dũng – MSSV: 52300190

---

## Mục đích

Bộ công cụ đo tự động hiệu năng mạng theo đúng yêu cầu đề bài:

| Chỉ số | Công cụ | File |
|--------|---------|------|
| **Throughput** (Mbps) | iperf3 UDP/TCP | `run_measurements.py` |
| **Delay** (RTT, ms) | ping | `parse_ping.py` |
| **Packet Loss** (%) | ping + iperf3 UDP | `parse_ping.py`, `parse_iperf.py` |
| **Jitter** (ms) | iperf3 UDP (RFC 3550) | `parse_iperf.py` |

---

## Cấu trúc thư mục

```
CuoiKy/
├── topology/
│   ├── topo_backbone_mpls.py      # Backbone MPLS (CE/PE/P)
│   ├── topo_branch1_flat.py       # LAN Chi nhánh 1 – Flat
│   ├── topo_branch2_3tier.py      # LAN Chi nhánh 2 – 3-Tier
│   ├── topo_branch3_leafspine.py  # LAN Chi nhánh 3 – Leaf-Spine
│   ├── metro_full.py              # Topo tổng hợp (Orchestrator)
│   └── configure_mpls.py         # Cấu hình Linux Kernel MPLS
│
├── scripts/
│   ├── run_measurements.py        # Script đo tự động (Mininet Python API)
│   ├── run_flat_tests.sh          # Shell script: đo Chi nhánh 1
│   ├── run_3tier_tests.sh         # Shell script: đo Chi nhánh 2
│   ├── run_leafspine_tests.sh     # Shell script: đo Chi nhánh 3
│   ├── run_all_tests.sh           # Master script: đo tất cả + vẽ đồ thị
│   ├── parse_ping.py              # Parser kết quả ping
│   ├── parse_iperf.py             # Parser kết quả iperf3
│   ├── aggregate_results.py       # Tổng hợp nhiều CSV thành 1
│   └── plot_results.py            # Vẽ 8 biểu đồ so sánh
│
├── config/
│   └── tests.yaml                 # Cấu hình test cases
│
└── results/
    ├── raw/                       # Log thô ping/iperf3
    ├── csv/                       # Kết quả CSV
    └── charts/                    # Biểu đồ PNG
```

---

## Cài đặt

### Môi trường yêu cầu
- Ubuntu 20.04 / 22.04
- Python ≥ 3.8
- Mininet ≥ 2.3.0
- Open vSwitch
- iperf3

```bash
# Cài Mininet
sudo apt-get install -y mininet

# Cài iperf3
sudo apt-get install -y iperf3

# Cài Python libraries
pip3 install matplotlib numpy pyyaml

# Kiểm tra Mininet
mn --version

# Dọn dẹp Mininet (khi cần)
sudo mn -c
```

---

## Cách chạy

### Cách 1 – Nhanh nhất: Dữ liệu giả lập (không cần Mininet)

Dùng khi muốn xem demo biểu đồ ngay, hoặc chưa có Ubuntu/Mininet:

```bash
cd ~/Desktop/CuoiKy   # hoặc thư mục dự án

# Tạo dữ liệu giả lập + vẽ 8 biểu đồ
bash scripts/run_all_tests.sh --mock
```

Dữ liệu giả lập được thiết kế dựa trên đặc tính lý thuyết từ `kienthuc.txt`:
- **Flat**: delay thấp nhưng loss cao ở tải cao (broadcast storm)
- **3-Tier**: delay trung bình, VLAN giảm broadcast
- **Leaf-Spine**: throughput cao nhất, jitter thấp nhất (2 hop cố định)

---

### Cách 2 – Đo toàn hệ thống (khuyến nghị)

```bash
# Chạy toàn bộ: 3 scenario + aggregate + vẽ biểu đồ
sudo bash scripts/run_all_tests.sh
```

Script tự động:
1. Khởi Mininet với `metro_full.py`
2. Đo ping (100 gói) + iperf3 UDP 3 mức tải (10/50/100 Mbps) × 3 lần lặp
3. Parse kết quả → CSV
4. Aggregate → CSV tổng hợp
5. Vẽ 8 biểu đồ → `results/charts/`

---

### Cách 3 – Đo từng chi nhánh riêng

```bash
# Chi nhánh 1 – Flat
sudo bash scripts/run_flat_tests.sh

# Chi nhánh 2 – 3-Tier
sudo bash scripts/run_3tier_tests.sh

# Chi nhánh 3 – Leaf-Spine
sudo bash scripts/run_leafspine_tests.sh
```

---

### Cách 4 – Dùng Python script trực tiếp

```bash
# Đo scenario flat
sudo python3 scripts/run_measurements.py --scenario flat --verbose

# Đo scenario 3tier
sudo python3 scripts/run_measurements.py --scenario 3tier

# Đo tất cả
sudo python3 scripts/run_measurements.py --scenario all
```

---

### Cách 5 – Test topology riêng lẻ (không đo)

```bash
# Test backbone MPLS
sudo mn --custom topology/topo_backbone_mpls.py --topo backbone_mpls

# Test LAN phẳng (Chi nhánh 1)
sudo mn --custom topology/topo_branch1_flat.py --topo branch1_flat --test ping

# Test 3-tier (Chi nhánh 2)
sudo mn --custom topology/topo_branch2_3tier.py --topo branch2_3tier --test ping

# Test Leaf-Spine (Chi nhánh 3)
sudo mn --custom topology/topo_branch3_leafspine.py --topo branch3_leafspine --test ping

# Test toàn hệ thống
sudo python3 topology/metro_full.py
```

---

## Quy trình đo (Active Measurement)

### Throughput

Dùng **iperf3 TCP** (chính xác hơn):
```bash
# Trong Mininet CLI:
mininet> web1 iperf3 -s &
mininet> host1 iperf3 -c 10.3.10.11 -t 10
```

Dùng **iperf3 UDP** (đồng thời đo Jitter + Packet Loss):
```bash
mininet> web1 iperf3 -s -u &
mininet> host1 iperf3 -c 10.3.10.11 -u -b 100M -t 10 -J
```

### Delay + Packet Loss

```bash
# 100 gói, interval 0.05s (20 gói/s)
mininet> host1 ping -c 100 -i 0.05 10.3.10.11
```

### Jitter (RFC 3550)

**iperf3 UDP** tự tính jitter theo công thức RFC 3550:

```
J(i) = J(i-1) + (|D(i-1,i)| - J(i-1)) / 16
```

Trong đó `D(i-1,i)` là hiệu transit time giữa 2 gói liên tiếp.

Jitter cũng được xấp xỉ bằng **mdev** (mean absolute deviation) từ `ping`:
```
mdev = mean(|RTT_i - avg_RTT|)
```

> **Lưu ý**: `mdev` và jitter RFC 3550 có thể khác nhau vài %. Trong báo cáo, nên ghi rõ nguồn tính jitter.

---

## Đọc và hiểu output CSV

### Các cột quan trọng

| Cột | Đơn vị | Mô tả |
|-----|--------|-------|
| `scenario` | – | `flat` / `3tier` / `leafspine` |
| `test_type` | – | `intra` (nội bộ LAN) / `cross` (qua backbone) |
| `load_level` | – | `10Mbps` / `50Mbps` / `100Mbps` |
| `avg_delay_ms` | ms | RTT trung bình (ping) |
| `ping_loss_pct` | % | Packet loss từ ping |
| `throughput_mbps` | Mbps | Throughput UDP iperf3 |
| `jitter_ms` | ms | Jitter UDP (RFC 3550) |
| `udp_loss_pct` | % | Packet loss từ iperf3 UDP |
| `tcp_throughput_mbps` | Mbps | Throughput TCP iperf3 |

### Ví dụ kết quả mong đợi

| Scenario | Load | Throughput | Delay | Loss | Jitter |
|----------|------|-----------|-------|------|--------|
| Flat | 100M | ~88 Mbps | ~0.8 ms | ~0.2% | ~0.15 ms |
| 3-Tier | 100M | ~91 Mbps | ~2.1 ms | ~0.1% | ~0.22 ms |
| Leaf-Spine | 100M | ~98 Mbps | ~0.9 ms | ~0.0% | ~0.08 ms |
| (cross-branch) | 100M | ~85 Mbps | ~9 ms | ~0.3% | ~0.3 ms |

---

## Biểu đồ đã tạo

| File | Nội dung |
|------|---------|
| `throughput_comparison.png` | Grouped bar: throughput 3 kiến trúc × 3 mức tải |
| `delay_comparison.png` | Bar: delay intra vs cross-branch |
| `loss_comparison.png` | Line chart: packet loss khi tải tăng |
| `jitter_comparison.png` | Grouped bar: jitter theo mức tải |
| `delay_boxplot.png` | Boxplot RTT phân phối |
| `summary_heatmap.png` | Heatmap 4 metrics × 3 kiến trúc |
| `throughput_vs_load.png` | Throughput tuyến tính vs target bandwidth |
| `intra_vs_cross_delay.png` | Delay intra-branch vs cross-branch (MPLS overhead) |

### Dùng trong LaTeX báo cáo

```latex
\begin{figure}[h]
    \centering
    \includegraphics[width=0.9\linewidth]{../results/charts/throughput_comparison.png}
    \caption{So sánh Throughput (UDP) theo mức tải giữa 3 kiến trúc LAN}
    \label{fig:throughput}
\end{figure}
```

---

## MPLS Configuration (`configure_mpls.py`)

File `topology/configure_mpls.py` chịu trách nhiệm thiết lập mạng lõi Metro Ethernet sử dụng tính năng **MPLS tích hợp sẵn trong Linux Kernel** (thông qua bộ công cụ `iproute2`).

### 1. Cách kích hoạt trong mã nguồn

Script này được thiết kế theo dạng module, có thể cắm vào bất kỳ topology Mininet nào có các node PE và P. Nhờ được gọi vào cuối `metro_full.py`, MPLS sẽ tự động thiết lập sau khi các interface ảo được khởi tạo.

```python
# Trong file metro_full.py (hoặc khi chạy qua Python API)
from configure_mpls import configure_mpls, verify_mpls

# Bật MPLS push/swap/pop trên toàn mạng
configure_mpls(net)    

# In bảng route MPLS LFIB để xác minh
verify_mpls(net)       
```

### 2. Nguyên lý hoạt động (4 bước tự động)

Khi hàm `configure_mpls(net)` chạy, nó thực hiện 4 bước sau trên các container Mininet (vốn là các network namespace của Linux):

1. **Load Module & Enable Platform (Tất cả P/PE)**: 
   - Tự động nạp Kernel module: `modprobe mpls_router`, `mpls_iptunnel`.
   - Bật hỗ trợ nhãn: `sysctl -w net.mpls.platform_labels=100000`.
   - Cho phép nhận gói tin MPLS trên từng interface: `sysctl -w net.mpls.conf.<iface>.input=1`.

2. **Cấu hình SWAP / Transit (Trên P Routers)**:
   - Các router Core (P1-P4) không đọc IP Header, chỉ đọc nhãn MPLS.
   - Script dùng lệnh `ip -f mpls route add <in_label> as <out_label> via inet <next_hop>` để tạo bảng LFIB.
   - Ví dụ tại P1: Nhận nhãn `200` từ PE1, đổi thành nhãn `201`, đẩy sang P3.

3. **Cấu hình PUSH / Ingress LER (Tại PE Routers)**:
   - PE nhận gói IP thuần tuý từ mạng khách hàng (CE).
   - PE kiểm tra IP đích (ví dụ `10.2.0.0/16` - LAN 2) và ép (encap/push) nhãn `200` vào gói tin, tống vào MPLS domain.
   - Lệnh tương ứng: `ip route add 10.2.0.0/16 encap mpls 200 via <next_hop_P>`.

4. **Cấu hình POP / Egress LER (Tại PE Routers đích)**:
   - Khi gói MPLS đến PE đích (hoặc P cuối cùng Pop nhãn bằng explicit-null `label 0`), nhãn bị gỡ bỏ.
   - PE đích sẽ định tuyến lại bằng IP Header thông thường để gửi về CE tương ứng.

### 3. Kiểm tra bằng tay trong Mininet CLI

Để chứng minh MPLS đang hoạt động thật thay vì chỉ định tuyến IP thông thường, bạn có thể kiểm tra bảng LFIB (Route MPLS) trên các con Router:

```bash
# Kiểm tra bảng SWAP trên router lỗi P1
mininet> p1 ip -f mpls route show
# Output mong đợi: 200 as 201 via inet 10.20.13.2 dev p1-eth2 ...

# Kiểm tra PUSH rule (Encap) trên PE1
mininet> pe1 ip route show
# Output mong đợi sẽ thấy dòng có chứa chữ "encap mpls xyz"
```

> **Lưu ý báo cáo**: Hãy chụp màn hình lệnh `ip -f mpls route show` trên router `p1` hoặc `p2` để chứng minh trong đề tài rằng gói tin thực sự được chuyển mạch bằng **nhãn (label)** ở core mạng thay vì IP.

---

## Phân tích kết quả (gợi ý cho báo cáo)

### Tại sao Leaf-Spine cho Throughput cao nhất?
- Mọi đường đi qua đúng **2 hop** (leaf→spine→leaf)
- **Không có STP** → không có blocked port, tận dụng full bandwidth
- **Equal-cost multipath** (ECMP) qua nhiều spine → load balancing tự nhiên

### Tại sao Flat cho Throughput thấp nhất ở 100Mbps?
- **Broadcast storm**: tất cả host cùng broadcast domain → ARP flood
- Không phân VLAN → broadcast càng nhiều khi nhiều host
- Switch access duy nhất trở thành bottleneck

### Tại sao Cross-branch delay cao hơn Intra-branch?
- MPLS overhead: mỗi PE phải **Push/Pop nhãn** (xử lý thêm)
- Thêm **hop count**: CE→PE→P→P→PE→CE (5-6 hop)
- Intra-branch chỉ 1-3 hop (trong LAN)

### Jitter thấp nhất ở Leaf-Spine?
- Path length **cố định** (always exactly 2 hop)
- Không có STP reconvergence → không spike đột ngột
- Equal-cost paths → không có "hot link" bị nghẽn

---

## Troubleshooting

```bash
# Mininet bị treo → dọn dẹp
sudo mn -c

# Kernel MPLS không load
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
lsmod | grep mpls

# iperf3 bị conflict port
sudo pkill -f iperf3

# OVS switch không bật
sudo service openvswitch-switch start
sudo ovs-vsctl show
```
