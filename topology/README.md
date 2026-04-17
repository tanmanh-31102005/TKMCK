# Metro Ethernet MPLS – Topology Scripts

> **Đề tài**: Thiết kế và triển khai mạng Metro Ethernet sử dụng MPLS cho kết nối đa chi nhánh doanh nghiệp  
> **Sinh viên**: Huỳnh Văn Dũng – MSSV: 52300190  
> **GVHD**: Lê Viết Thanh

---

## Cấu trúc file

```
topology/
├── topo_backbone_mpls.py      # Backbone MPLS: CE/PE/P routers
├── topo_branch1_flat.py       # Chi nhánh 1: Mạng phẳng (Flat)
├── topo_branch2_3tier.py      # Chi nhánh 2: Mạng 3 lớp (Core-Dist-Access)
├── topo_branch3_leafspine.py  # Chi nhánh 3: Mạng Leaf-Spine
└── metro_full.py              # Orchestrator: Tích hợp tất cả
```

---

## Sơ đồ tổng quan

```
[CE1]──PE1──P1──P2──PE3──[CE3]
         │   └──P3──┘
         └──P3──P4──PE2──[CE2]
              (full-mesh P1,P2,P3,P4)

Chi nhánh 1 (Flat):
  host1/2/3/4 ── s_acc1 ── ce1_lan ══ CE1

Chi nhánh 2 (3-Tier):
  admin/lab/guest ── acc ── dist ── core ── ce2_lan ══ CE2

Chi nhánh 3 (Leaf-Spine):
  web/dns/db ── leaf1/2/3 ── spine1/2 ── ce3_lan ══ CE3
```

---

## Địa chỉ IP

| Link              | Bên A              | Bên B              |
|-------------------|--------------------|--------------------|
| CE1 – PE1         | CE1: 10.0.1.1/30   | PE1: 10.0.1.2/30   |
| CE2 – PE2         | CE2: 10.0.2.1/30   | PE2: 10.0.2.2/30   |
| CE3 – PE3         | CE3: 10.0.3.1/30   | PE3: 10.0.3.2/30   |
| PE1 – P1          | PE1: 10.10.11.1/30 | P1: 10.10.11.2/30  |
| PE1 – P3          | PE1: 10.10.13.1/30 | P3: 10.10.13.2/30  |
| PE2 – P3          | PE2: 10.10.23.1/30 | P3: 10.10.23.2/30  |
| PE2 – P4          | PE2: 10.10.24.1/30 | P4: 10.10.24.2/30  |
| PE3 – P2          | PE3: 10.10.32.1/30 | P2: 10.10.32.2/30  |
| PE3 – P4          | PE3: 10.10.34.1/30 | P4: 10.10.34.2/30  |
| P1 – P2           | P1: 10.20.12.1/30  | P2: 10.20.12.2/30  |
| P1 – P3           | P1: 10.20.13.1/30  | P3: 10.20.13.2/30  |
| P1 – P4           | P1: 10.20.14.1/30  | P4: 10.20.14.2/30  |
| P2 – P3           | P2: 10.20.23.1/30  | P3: 10.20.23.2/30  |
| P2 – P4           | P2: 10.20.24.1/30  | P4: 10.20.24.2/30  |
| P3 – P4           | P3: 10.20.34.1/30  | P4: 10.20.34.2/30  |
| **chi nhánh 1**   | ce1_lan: 10.1.0.1  | hosts: 10.1.0.0/24 |
| **chi nhánh 2**   | ce2_lan gateway    | VLAN10: 10.2.10.0/24 / VLAN20: 10.2.20.0/24 / VLAN30: 10.2.30.0/24 |
| **chi nhánh 3**   | ce3_lan gateway    | Web: 10.3.10.0/24 / DNS: 10.3.20.0/24 / DB: 10.3.30.0/24 |

---

## Cách chạy từng file

### 1. Backbone MPLS (test CE-CE ping)

```bash
# Cách 1: Chạy script trực tiếp
sudo python3 topo_backbone_mpls.py

# Cách 2: Dùng --custom flag Mininet
sudo mn --custom topo_backbone_mpls.py --topo backbone_mpls

# Test ping giữa CE:
# Trong CLI Mininet:
# mininet> ce1 ping -c 3 10.0.2.1    ← CE1 → CE2
# mininet> ce1 ping -c 3 10.0.3.1    ← CE1 → CE3
```

### 2. Chi nhánh 1 – Mạng phẳng (Flat)

```bash
# Chạy độc lập test LAN phẳng
sudo mn --custom topo_branch1_flat.py --topo branch1_flat --test ping

# Hoặc:
sudo python3 topo_branch1_flat.py

# Trong CLI Mininet:
# mininet> pingall
# mininet> host1 ping host4
# mininet> h1 iperf h2      ← đo throughput
```

### 3. Chi nhánh 2 – Mạng 3 lớp (Core-Distribution-Access)

```bash
# Chạy độc lập test 3-tier
sudo mn --custom topo_branch2_3tier.py --topo branch2_3tier --test ping

# Hoặc:
sudo python3 topo_branch2_3tier.py

# Trong CLI Mininet:
# mininet> pingall
# mininet> admin1 ping lab1     ← Inter-VLAN qua ce2_lan
# mininet> admin1 ping guest2   ← Inter-VLAN cross-group
# mininet> iperf admin1 lab2    ← đo throughput inter-VLAN
```

### 4. Chi nhánh 3 – Mạng Leaf-Spine

```bash
# Chạy độc lập test Leaf-Spine
sudo mn --custom topo_branch3_leafspine.py --topo branch3_leafspine --test ping

# Hoặc:
sudo python3 topo_branch3_leafspine.py

# Trong CLI Mininet:
# mininet> pingall
# mininet> web1 ping dns1    ← leaf1 → spine → leaf2 (2 hops)
# mininet> web1 ping db2     ← leaf1 → spine → leaf3
# mininet> iperf web1 db1    ← đo throughput cross-leaf
```

### 5. Toàn hệ thống (Metro Full – Orchestrator)

```bash
# Chạy toàn hệ thống tích hợp
sudo python3 metro_full.py

# Hoặc:
sudo mn --custom metro_full.py --topo metro_full

# Trong CLI Mininet (cross-branch test):
# mininet> host1 ping 10.3.10.11    ← branch1 → branch3 (qua backbone)
# mininet> admin1 ping 10.3.20.21   ← branch2 → branch3
# mininet> web1 ping 10.2.10.11     ← branch3 → branch2
# mininet> pingall                  ← toàn bộ hệ thống
```

---

## Đo hiệu năng (Performance Metrics)

### Throughput (dùng iperf)
```bash
# Trong Mininet CLI:
# Chạy iperf server tại đích:
mininet> web1 iperf -s &
# Đo từ nguồn:
mininet> host1 iperf -c 10.3.10.11 -t 10

# Hoặc dùng lệnh tích hợp:
mininet> iperf host1 web1
```

### Delay / Latency (dùng ping)
```bash
# 100 gói, đo RTT trung bình:
mininet> host1 ping -c 100 10.3.10.11
```

### Packet Loss (dùng ping với tải cao)
```bash
mininet> host1 ping -c 1000 -f 10.3.20.21   # flood ping
```

### Jitter (dùng iperf UDP)
```bash
mininet> web1 iperf -s -u &
mininet> host1 iperf -c 10.3.10.11 -u -b 10M -t 10
# Xem Jitter trong kết quả iperf UDP
```

---

## Yêu cầu môi trường

- Ubuntu 20.04 / 22.04
- Mininet >= 2.3.0
- Python >= 3.8
- Open vSwitch (OVS)

```bash
# Cài đặt Mininet (nếu chưa có):
sudo apt-get install mininet

# Kiểm tra phiên bản:
mn --version

# Dọn dẹp sau khi chạy:
sudo mn -c
```

---

## Ghi chú kiến trúc

| File                        | Chạy độc lập | Tích hợp với metro_full |
|-----------------------------|:------------:|:------------------------:|
| `topo_backbone_mpls.py`     | ✓            | ✓ (import)               |
| `topo_branch1_flat.py`      | ✓            | ✓ (import)               |
| `topo_branch2_3tier.py`     | ✓            | ✓ (import)               |
| `topo_branch3_leafspine.py` | ✓            | ✓ (import)               |
| `metro_full.py`             | ✓ (tổng hợp)| –                        |

**Thiết kế tách lớp**: Backbone không biết về chi tiết LAN. Mỗi chi nhánh
có thể test độc lập. `metro_full.py` đóng vai trò "glue layer" kết nối tất cả.
