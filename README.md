# 🌐 Thiết Kế & Triển Khai Mạng Metro Ethernet sử dụng MPLS

<div align="center">

![Network Topology](LOGIC.jpg)

**Mô phỏng mạng Metro Ethernet MAN với MPLS Backbone kết nối 3 chi nhánh doanh nghiệp có kiến trúc LAN khác nhau**

---

[![Platform](https://img.shields.io/badge/Platform-Mininet-blue?style=for-the-badge)](http://mininet.org/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-yellow?style=for-the-badge&logo=python)](https://www.python.org/)
[![OS](https://img.shields.io/badge/OS-Ubuntu%2020.04%2F22.04-orange?style=for-the-badge&logo=ubuntu)](https://ubuntu.com/)
[![Protocol](https://img.shields.io/badge/Protocol-MPLS%20%7C%20OSPF%20%7C%20LDP-green?style=for-the-badge)]()
[![License](https://img.shields.io/badge/License-Academic-purple?style=for-the-badge)]()

</div>

---

## 📋 Thông tin dự án

| Thông tin | Chi tiết |
|-----------|----------|
| **Trường** | Đại học Tôn Đức Thắng |
| **Khoa** | Công nghệ Thông tin |
| **Ngành** | Mạng Máy tính và Truyền thông Dữ liệu |
| **Môn học** | Thiết kế Mạng (Cuối kỳ) |
| **Sinh viên** | Nguyễn Tấn Mạnh – MSSV: 52300221 |
| **GVHD** | Lê Viết Thanh |

---

## 🎯 Mục tiêu dự án

Dự án này xây dựng và mô phỏng hoàn chỉnh một hệ thống **mạng Metro Ethernet MAN (Metropolitan Area Network)** sử dụng **MPLS (Multiprotocol Label Switching)** để kết nối đa chi nhánh doanh nghiệp, với 3 mục tiêu chính:

1. **Mô phỏng thực tế** – Triển khai mô hình mạng đầy đủ trên nền tảng **Mininet** bao gồm backbone MPLS (ISP) và 3 chi nhánh với kiến trúc LAN khác nhau.
2. **Đánh giá hiệu năng** – Đo lường và phân tích các chỉ số: **Throughput, Delay, Packet Loss, Jitter** theo từng kịch bản.
3. **So sánh kiến trúc LAN** – Đối chiếu hiệu suất giữa 3 mô hình nội bộ: Mạng phẳng, 3 lớp (Core-Dist-Access), và Leaf-Spine.

---

## 🏗️ Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                    ISP BACKBONE (MPLS Core)                     │
│                                                                  │
│         PE1 ──── P1 ──── P2 ──── PE3                           │
│          │        │       │        │                             │
│          │        └── P3 ─┘        │                             │
│          └──── P3 ──── P4 ──── PE2                              │
│                  (full-mesh P1,P2,P3,P4)                        │
└────────────┬──────────────────┬─────────────────┬───────────────┘
             │                  │                  │
         CE1 │              CE2 │              CE3 │
             ▼                  ▼                  ▼
    ┌─────────────┐   ┌─────────────────┐  ┌──────────────────┐
    │ CHI NHÁNH 1 │   │   CHI NHÁNH 2   │  │   CHI NHÁNH 3    │
    │  Mạng phẳng │   │   Mạng 3 lớp    │  │   Leaf-Spine     │
    │  (Flat LAN) │   │ Core-Dist-Access│  │  (2-Tier Clos)   │
    │             │   │                 │  │                  │
    │ host1~host4 │   │admin/lab/guest  │  │ web/dns/db nodes │
    └─────────────┘   └─────────────────┘  └──────────────────┘
```

### Các thành phần hệ thống

| Thành phần | Vai trò | Số lượng |
|-----------|---------|----------|
| **P Router** (Provider) | Chuyển mạch nhãn MPLS trong core | 4 (P1–P4) |
| **PE Router** (Provider Edge) | Ingress/Egress LER – Push/Pop nhãn | 3 (PE1–PE3) |
| **CE Router** (Customer Edge) | Cầu nối khách hàng ↔ ISP | 3 (CE1–CE3) |
| **Switches** | Chuyển mạch nội bộ chi nhánh | ~12 |
| **Hosts** | Thiết bị đầu cuối | ~14 |

---

## 📂 Cấu trúc thư mục

```
CuoiKy/
├── 📄 README.md                       # File này
├── 🖼️  LOGIC.jpg                      # Sơ đồ logic tổng quan
├── 📄 debai.txt                       # Đề bài gốc
├── 📄 kienthuc.txt                    # Tài liệu lý thuyết
│
├── 📁 52300221_Source_Code/           # Toàn bộ mã nguồn
│   │
│   ├── 📁 topology/                   # Script Mininet topology
│   │   ├── metro_full.py              # ★ Orchestrator – Chạy toàn hệ thống
│   │   ├── topo_backbone_mpls.py      # Backbone ISP (PE/P/CE)
│   │   ├── topo_branch1_flat.py       # Chi nhánh 1: Mạng phẳng
│   │   ├── topo_branch2_3tier.py      # Chi nhánh 2: Mạng 3 lớp
│   │   ├── topo_branch3_leafspine.py  # Chi nhánh 3: Leaf-Spine
│   │   ├── configure_mpls.py          # Cấu hình MPLS Linux Kernel
│   │   └── configure_mpls_ldp.py      # Cấu hình LDP (Label Distribution)
│   │
│   ├── 📁 scripts/                    # Công cụ đo & phân tích
│   │   ├── run_all_tests.sh           # ★ Master script: chạy tất cả
│   │   ├── run_flat_tests.sh          # Đo Chi nhánh 1 (Flat)
│   │   ├── run_3tier_tests.sh         # Đo Chi nhánh 2 (3-Tier)
│   │   ├── run_leafspine_tests.sh     # Đo Chi nhánh 3 (Leaf-Spine)
│   │   ├── run_measurements.py        # Python API đo tự động
│   │   ├── parse_ping.py              # Parser kết quả ping → CSV
│   │   ├── parse_iperf.py             # Parser kết quả iperf3 → CSV
│   │   ├── aggregate_results.py       # Tổng hợp nhiều CSV
│   │   ├── plot_results.py            # Vẽ 8 biểu đồ so sánh
│   │   └── README_toolkit.md          # Hướng dẫn chi tiết toolkit
│   │
│   ├── 📁 config/
│   │   └── tests.yaml                 # Cấu hình test cases
│   │
│   └── 📁 results/
│       ├── raw/                       # Log thô ping/iperf3
│       ├── csv/                       # Kết quả CSV đã parse
│       └── charts/                    # Biểu đồ PNG (8 biểu đồ)
│
├── 📄 52300221.pdf                    # Báo cáo đề tài
├── 📄 52300221_slide.pdf              # Slide thuyết trình
└── 📄 DeTaiCuoiKy_26_TKM.pdf         # Đề tài gốc từ giảng viên
```

---

## 🔧 Yêu cầu môi trường

### Hệ điều hành
- **Ubuntu 20.04 LTS** hoặc **Ubuntu 22.04 LTS** *(khuyến nghị)*
- Có thể dùng VM (VirtualBox/VMware) hoặc WSL2 trên Windows

### Phần mềm cần cài

```bash
# 1. Cài Mininet (>= 2.3.0)
sudo apt-get update
sudo apt-get install -y mininet

# 2. Cài Open vSwitch
sudo apt-get install -y openvswitch-switch
sudo service openvswitch-switch start

# 3. Cài iperf3
sudo apt-get install -y iperf3

# 4. Cài Python libraries
pip3 install matplotlib numpy pyyaml

# 5. Bật MPLS modules trong Linux Kernel
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel

# Kiểm tra phiên bản
mn --version
python3 --version
iperf3 --version
```

### Bảng kiểm tra môi trường

| Phần mềm | Phiên bản tối thiểu | Kiểm tra |
|----------|---------------------|----------|
| Mininet | >= 2.3.0 | `mn --version` |
| Python | >= 3.8 | `python3 --version` |
| Open vSwitch | >= 2.13 | `ovs-vsctl --version` |
| iperf3 | >= 3.7 | `iperf3 --version` |
| matplotlib | >= 3.3 | `pip3 show matplotlib` |

---

## 🚀 Hướng dẫn chạy

### ⚡ Cách 1: Chạy toàn hệ thống (Khuyến nghị)

```bash
# Clone repo
git clone https://github.com/tanmanh-31102005/TKMCK.git
cd TKMCK/52300221_Source_Code

# Chạy toàn bộ hệ thống + đo + vẽ biểu đồ
sudo bash scripts/run_all_tests.sh
```

Script tự động thực hiện:
1. 🔵 Khởi động Mininet với topology đầy đủ (`metro_full.py`)
2. 📊 Đo ping (100 gói) + iperf3 UDP ở 3 mức tải (10/50/100 Mbps) × 3 lần lặp
3. 📄 Parse kết quả → CSV
4. 📈 Tổng hợp & vẽ 8 biểu đồ so sánh → `results/charts/`

---

### 🎭 Cách 2: Demo nhanh (không cần Mininet)

Dành cho Windows / macOS hoặc khi chưa cài Mininet – dùng dữ liệu giả lập:

```bash
bash scripts/run_all_tests.sh --mock
```

> Dữ liệu mock được thiết kế theo đặc tính lý thuyết: Flat có loss cao ở tải cao, Leaf-Spine có throughput cao nhất.

---

### 🔬 Cách 3: Chạy từng chi nhánh độc lập

```bash
# Chi nhánh 1 – Flat Network
sudo bash scripts/run_flat_tests.sh

# Chi nhánh 2 – 3-Tier Network
sudo bash scripts/run_3tier_tests.sh

# Chi nhánh 3 – Leaf-Spine Network
sudo bash scripts/run_leafspine_tests.sh
```

---

### 🐍 Cách 4: Dùng Python API

```bash
# Đo một scenario cụ thể
sudo python3 scripts/run_measurements.py --scenario flat --verbose
sudo python3 scripts/run_measurements.py --scenario 3tier
sudo python3 scripts/run_measurements.py --scenario leafspine

# Đo tất cả
sudo python3 scripts/run_measurements.py --scenario all
```

---

### 🖥️ Cách 5: Tương tác trực tiếp trong Mininet CLI

#### Chạy toàn hệ thống:
```bash
sudo python3 52300221_Source_Code/topology/metro_full.py
```

#### Chạy từng topology riêng lẻ:
```bash
# Backbone MPLS
sudo mn --custom topology/topo_backbone_mpls.py --topo backbone_mpls

# Chi nhánh 1 – Flat (test ping tự động)
sudo mn --custom topology/topo_branch1_flat.py --topo branch1_flat --test ping

# Chi nhánh 2 – 3-Tier
sudo mn --custom topology/topo_branch2_3tier.py --topo branch2_3tier --test ping

# Chi nhánh 3 – Leaf-Spine
sudo mn --custom topology/topo_branch3_leafspine.py --topo branch3_leafspine --test ping
```

#### Lệnh kiểm tra trong Mininet CLI:
```bash
# ═══ Test kết nối cross-branch (qua MPLS backbone) ═══
mininet> host1 ping -c 3 10.3.10.11    # Branch1 → Branch3 (qua backbone)
mininet> admin1 ping -c 3 10.3.20.21   # Branch2 → Branch3
mininet> web1 ping -c 3 10.2.10.11     # Branch3 → Branch2
mininet> pingall                        # Tất cả host ping nhau

# ═══ Đo Throughput (iperf3 TCP) ═══
mininet> web1 iperf3 -s &
mininet> host1 iperf3 -c 10.3.10.11 -t 10

# ═══ Đo Delay (ping 100 gói) ═══
mininet> host1 ping -c 100 10.3.10.11

# ═══ Đo Packet Loss (flood ping) ═══
mininet> host1 ping -c 1000 -f 10.3.20.21

# ═══ Đo Jitter (iperf3 UDP) ═══
mininet> web1 iperf3 -s -u &
mininet> host1 iperf3 -c 10.3.10.11 -u -b 10M -t 10
```

---

## 🌐 Địa chỉ IP hệ thống

### Backbone MPLS (ISP)

| Link | Router A | Router B |
|------|----------|----------|
| CE1 – PE1 | CE1: `10.0.1.1/30` | PE1: `10.0.1.2/30` |
| CE2 – PE2 | CE2: `10.0.2.1/30` | PE2: `10.0.2.2/30` |
| CE3 – PE3 | CE3: `10.0.3.1/30` | PE3: `10.0.3.2/30` |
| PE1 – P1 | PE1: `10.10.11.1/30` | P1: `10.10.11.2/30` |
| PE1 – P3 | PE1: `10.10.13.1/30` | P3: `10.10.13.2/30` |
| PE2 – P3 | PE2: `10.10.23.1/30` | P3: `10.10.23.2/30` |
| PE2 – P4 | PE2: `10.10.24.1/30` | P4: `10.10.24.2/30` |
| PE3 – P2 | PE3: `10.10.32.1/30` | P2: `10.10.32.2/30` |
| PE3 – P4 | PE3: `10.10.34.1/30` | P4: `10.10.34.2/30` |
| P1 – P2 | P1: `10.20.12.1/30` | P2: `10.20.12.2/30` |
| P1 – P3 | P1: `10.20.13.1/30` | P3: `10.20.13.2/30` |
| P1 – P4 | P1: `10.20.14.1/30` | P4: `10.20.14.2/30` |
| P2 – P3 | P2: `10.20.23.1/30` | P3: `10.20.23.2/30` |
| P2 – P4 | P2: `10.20.24.1/30` | P4: `10.20.24.2/30` |
| P3 – P4 | P3: `10.20.34.1/30` | P4: `10.20.34.2/30` |

### Mạng chi nhánh

| Chi nhánh | Subnet | Hosts |
|-----------|--------|-------|
| Chi nhánh 1 (Flat) | `10.1.0.0/24` | host1~host4: `10.1.0.101~104` |
| Chi nhánh 2 – VLAN 10 (Admin) | `10.2.10.0/24` | admin1: `10.2.10.11`, admin2: `10.2.10.12` |
| Chi nhánh 2 – VLAN 20 (Lab) | `10.2.20.0/24` | lab1: `10.2.20.21`, lab2: `10.2.20.22` |
| Chi nhánh 2 – VLAN 30 (Guest) | `10.2.30.0/24` | guest1: `10.2.30.31`, guest2: `10.2.30.32` |
| Chi nhánh 3 – Web (leaf1) | `10.3.10.0/24` | web1: `10.3.10.11`, web2: `10.3.10.12` |
| Chi nhánh 3 – DNS (leaf2) | `10.3.20.0/24` | dns1: `10.3.20.21`, dns2: `10.3.20.22` |
| Chi nhánh 3 – DB (leaf3) | `10.3.30.0/24` | db1: `10.3.30.31`, db2: `10.3.30.32` |

---

## ⚙️ Nguyên lý hoạt động MPLS

### Quy trình chuyển mạch nhãn (Label Switching)

```
                    MPLS Domain (ISP Backbone)
                ┌────────────────────────────────┐
                │                                │
CE1 ─── PE1 ──→│── P1 ──→ P3 ──→ P4 ──→ ──│──→ PE2 ─── CE2
  [IP Packet]  │  [PUSH]  [SWAP]  [SWAP]    │  [POP]  [IP Packet]
               │  Label:  Label:  Label:    │
               │   100     200     201      │
               └────────────────────────────┘
```

| Bước | Router | Hành động | Mô tả |
|------|--------|-----------|-------|
| **PUSH** | PE Ingress | Dán nhãn vào gói IP | CE → PE: gói IP thuần → gói MPLS có nhãn |
| **SWAP** | P (Core) | Đổi nhãn cũ → nhãn mới | Chuyển tiếp bằng nhãn, không đọc IP Header |
| **POP** | PE Egress | Gỡ nhãn, trả về IP | Gửi gói IP nguyên bản về CE đích |

### Cấu hình MPLS trong Mininet

```python
from configure_mpls import configure_mpls, verify_mpls

# Bật MPLS trên toàn mạng
configure_mpls(net)

# Kiểm tra bảng LFIB (Label Forwarding Information Base)
verify_mpls(net)
```

### Kiểm tra MPLS đang hoạt động

```bash
# Xem bảng SWAP tại router P1
mininet> p1 ip -f mpls route show
# Kết quả mong đợi: 200 as 201 via inet 10.20.13.2 dev p1-eth2 ...

# Xem PUSH rule (Encap) tại PE1
mininet> pe1 ip route show
# Kết quả có dòng chứa: encap mpls <label>

# Xác nhận Kernel MPLS modules đã load
lsmod | grep mpls
```

### Các giao thức điều khiển

| Giao thức | Tầng | Vai trò |
|-----------|------|---------|
| **OSPF** | Underlay (IGP) | Định tuyến nội vùng ISP – giúp PE/P "thấy nhau" |
| **LDP** | Label Distribution | Phân phối nhãn MPLS cho các đường đi OSPF đã tìm |
| **MP-BGP** | Overlay | Trao đổi thông tin định tuyến VPN giữa các PE |

---

## 📊 Các chỉ số hiệu năng & phương pháp đo

| Chỉ số | Đơn vị | Công cụ | Mô tả |
|--------|--------|---------|-------|
| **Throughput** | Mbps | iperf3 TCP/UDP | Lưu lượng dữ liệu thực tế truyền qua mạng/giây |
| **Delay (RTT)** | ms | ping | Thời gian gói tin đi từ nguồn → đích → nguồn |
| **Packet Loss** | % | ping + iperf3 UDP | Tỉ lệ gói bị mất trên tổng gói gửi |
| **Jitter** | ms | iperf3 UDP (RFC 3550) | Biến động độ trễ giữa các gói tin liên tiếp |

### Kịch bản đo (Test Cases)

```
Mức tải:    10 Mbps │ 50 Mbps │ 100 Mbps
Lần lặp:    3 lần mỗi kịch bản
Ping:       100 gói / lần đo

Scenario 1: Intra-branch Flat      (host1 → host2, host1 → host3)
Scenario 2: Intra-branch 3-Tier    (admin1 → lab1, admin1 → guest1)
Scenario 3: Intra-branch Leaf-Spine (web1 → dns1, web1 → db1)
Scenario 4: Cross-branch via MPLS  (Flat↔3Tier↔LeafSpine)
```

### Kết quả mong đợi (Benchmark)

| Kiến trúc | Tải 100Mbps | Throughput | Delay | Loss | Jitter |
|-----------|-------------|------------|-------|------|--------|
| Flat | Intra | ~88 Mbps | ~0.8 ms | ~0.2% | ~0.15 ms |
| 3-Tier | Intra | ~91 Mbps | ~2.1 ms | ~0.1% | ~0.22 ms |
| Leaf-Spine | Intra | ~98 Mbps | ~0.9 ms | ~0.0% | ~0.08 ms |
| (Cross-branch) | MPLS | ~85 Mbps | ~9 ms | ~0.3% | ~0.3 ms |

---

## 📈 Biểu đồ kết quả

Sau khi chạy, 8 biểu đồ được tạo tự động trong `results/charts/`:

| File biểu đồ | Nội dung |
|-------------|----------|
| `throughput_comparison.png` | Grouped bar: Throughput 3 kiến trúc × 3 mức tải |
| `delay_comparison.png` | Bar chart: Delay intra vs cross-branch |
| `loss_comparison.png` | Line chart: Packet loss khi tải tăng dần |
| `jitter_comparison.png` | Grouped bar: Jitter theo mức tải |
| `delay_boxplot.png` | Boxplot phân phối RTT |
| `summary_heatmap.png` | Heatmap 4 metrics × 3 kiến trúc |
| `throughput_vs_load.png` | Throughput tuyến tính vs target bandwidth |
| `intra_vs_cross_delay.png` | Delay nội bộ vs xuyên backbone (MPLS overhead) |

---

## 🔍 Phân tích & Kết luận

### Tại sao Leaf-Spine cho Throughput cao nhất?
- **2 hop cố định** (leaf → spine → leaf) – không có đường đi dài hơn
- **Không có STP** → không có blocked port, tận dụng full bandwidth
- **ECMP** (Equal-Cost Multi-Path) qua nhiều spine → load balancing tự nhiên

### Tại sao Flat cho Loss cao nhất ở 100 Mbps?
- **Broadcast storm**: tất cả host cùng broadcast domain → ARP flood
- Không phân VLAN → broadcast càng nhiều khi tải tăng
- Switch access duy nhất trở thành bottleneck

### Tại sao Cross-branch delay cao hơn Intra-branch?
- **MPLS overhead**: PE phải Push/Pop nhãn (xử lý thêm ~2–4 ms)
- **Hop count**: CE → PE → P → P → PE → CE (5–6 hop) vs 1–3 hop trong LAN
- **Serialization delay**: thêm header MPLS vào mỗi gói

### So sánh tổng quan 3 kiến trúc

| Tiêu chí | Flat | 3-Tier | Leaf-Spine |
|----------|:----:|:------:|:----------:|
| Throughput | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Delay thấp | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Packet Loss | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Jitter thấp | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Độ phức tạp | Thấp | Trung bình | Cao |
| Khả năng mở rộng | Kém | Tốt | Xuất sắc |

---

## 🛠️ Troubleshooting

```bash
# ❌ Mininet bị treo hoặc lỗi khi khởi động lại
sudo mn -c

# ❌ MPLS Kernel modules không load
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
lsmod | grep mpls

# ❌ iperf3 bị conflict port
sudo pkill -f iperf3

# ❌ Open vSwitch không khởi động
sudo service openvswitch-switch start
sudo ovs-vsctl show

# ❌ Permission denied khi chạy script
chmod +x scripts/*.sh
sudo bash scripts/run_all_tests.sh

# ❌ Python module not found
pip3 install matplotlib numpy pyyaml

# ✅ Dọn dẹp hoàn toàn sau khi test
sudo mn -c && sudo pkill -f iperf3 && sudo pkill -f python3
```

---

## 📖 Tài liệu tham khảo

- Mininet Documentation: [http://mininet.org/](http://mininet.org/)
- Linux Kernel MPLS: [iproute2 MPLS guide](https://www.kernel.org/doc/Documentation/networking/mpls-sysctl.txt)
- OSPF RFC 2328: [https://tools.ietf.org/html/rfc2328](https://tools.ietf.org/html/rfc2328)
- LDP RFC 5036: [https://tools.ietf.org/html/rfc5036](https://tools.ietf.org/html/rfc5036)
- Jitter RFC 3550: [https://tools.ietf.org/html/rfc3550](https://tools.ietf.org/html/rfc3550)
- Metro Ethernet Forum (MEF): [https://www.mef.net/](https://www.mef.net/)

---

<div align="center">

**Trường Đại học Tôn Đức Thắng | Khoa CNTT | 2025**

*Nguyễn Tấn Mạnh – MSSV: 52300221*

</div>
