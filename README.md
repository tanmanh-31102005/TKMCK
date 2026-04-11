# Thiết kế và Triển khai Mạng Metro Ethernet sử dụng MPLS cho Kết nối Đa Chi nhánh Doanh nghiệp

> **Đề tài Cuối kỳ** | Môn học: Thiết kế Mạng  
> **Sinh viên**: Huỳnh Văn Dũng – MSSV: 52300190  
> **GVHD**: ThS. Lê Viết Thanh  
> **Trường**: Đại học Tôn Đức Thắng – Khoa CNTT – Ngành Mạng máy tính và Truyền thông dữ liệu

---

## 📋 Tổng quan đề tài

Đề tài xây dựng và mô phỏng mô hình **Metro Ethernet MAN sử dụng MPLS** để kết nối 3 chi nhánh doanh nghiệp với 3 kiến trúc LAN khác nhau thông qua backbone ISP trên **Mininet + Ubuntu 22.04**.

| Chi nhánh | Kiến trúc LAN | Subnet |
|-----------|--------------|--------|
| Chi nhánh 1 | Mạng phẳng (Flat Network) | 10.1.0.0/24 |
| Chi nhánh 2 | Mạng 3 lớp (Core–Distribution–Access) | 10.2.0.0/24 |
| Chi nhánh 3 | Mạng Leaf-Spine | 10.3.0.0/24 |

**Backbone MPLS**: PE1, PE2, PE3, P1, P2 – mô phỏng cơ chế Push/Swap/Pop label.

---

## 🗂️ Cấu trúc thư mục

```
CuoiKy/
├── source/                      ← Tất cả file Python Mininet
│   ├── mpls_metro_topology.py   ← Topology tổng thể (file chính chạy mô phỏng)
│   ├── flat.py                  ← Tham khảo: Branch 1 Flat Network standalone
│   ├── coreditrubutionaccess.py ← Tham khảo: Branch 2 3-Tier standalone
│   └── spineleaf.py             ← Tham khảo: Branch 3 Leaf-Spine standalone
├── scripts/
│   ├── run_tests.sh             ← Script tự động 3 kịch bản đo lường
│   ├── collect_results.py       ← Phân tích log → CSV + biểu đồ
│   └── mpls_config.sh           ← Cấu hình MPLS kernel ngoài Mininet
├── results/
│   ├── raw/                     ← Log iperf3 và ping
│   ├── csv/                     ← Số liệu tổng hợp
│   └── charts/                  ← Biểu đồ PNG
├── source_latex/                ← Báo cáo LaTeX (Overleaf)
│   ├── main.tex                 ← File LaTeX chính
│   ├── preamble.tex
│   ├── frontmatter/             ← titlepage, abstract, acknowledgment
│   ├── content/                 ← C1.tex → C6.tex
│   └── media/                   ← Hình ảnh, biểu đồ nhúng vào báo cáo
├── docs/
│   ├── debai.txt                ← Đề bài chính thức
│   ├── kienthuc.txt             ← Tóm tắt lý thuyết
│   └── huong_dan_cai_dat.md     ← Hướng dẫn cài đặt chi tiết
├── image/                       ← Sơ đồ logic topology
├── DeTaiCuoiKy_26_TKM.pdf       ← Bản PDF đề tài
└── README.md                    ← File này
```

---

## ⚙️ Cài đặt môi trường (Ubuntu 22.04)

### Bước 1: Cập nhật hệ thống

```bash
sudo apt update && sudo apt upgrade -y
```

### Bước 2: Cài Mininet và các gói cần thiết

```bash
sudo apt install -y \
    mininet \
    openvswitch-switch openvswitch-common \
    python3 python3-pip \
    iperf3 iperf \
    tcpdump net-tools iproute2 \
    iputils-ping traceroute \
    python3-matplotlib python3-numpy

pip3 install matplotlib numpy
```

### Bước 3: Kích hoạt MPLS kernel

```bash
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
sudo sysctl -w net.mpls.platform_labels=1000

# Thêm vào /etc/sysctl.conf để giữ sau reboot:
echo 'net.mpls.platform_labels = 1000' | sudo tee -a /etc/sysctl.conf
```

### Bước 4: Kiểm tra Mininet

```bash
sudo mn --topo single,3 --test ping
# Kết quả mong đợi: 0% dropped (6/6 received)

sudo mn -c  # Dọn dẹp sau test
```

---

## 🚀 Chạy mô phỏng

### Khởi động topology MPLS đầy đủ

```bash
cd ~/CuoiKy/source
sudo mn -c               # Dọn dẹp Mininet cũ
sudo python3 mpls_metro_topology.py
```

### Chạy từng chi nhánh độc lập (để kiểm tra riêng lẻ)

```bash
# Test Branch 1 – Flat Network
sudo python3 flat.py

# Test Branch 2 – 3-Tier
sudo python3 coreditrubutionaccess.py

# Test Branch 3 – Leaf-Spine
sudo python3 spineleaf.py
```

### Kiểm tra trong Mininet CLI

```bash
# Xem tất cả node
mininet> nodes

# Ping giữa các chi nhánh
mininet> h1a ping -c 5 10.2.0.1    # Branch1 → Branch2
mininet> h1a ping -c 5 10.3.0.1    # Branch1 → Branch3
mininet> h2a ping -c 5 10.3.0.1    # Branch2 → Branch3

# Kiểm tra toàn bộ kết nối
mininet> pingall

# Xem routing table của P1 (MPLS Core)
mininet> p1 ip route

# Xem MPLS labels (nếu kernel hỗ trợ)
mininet> p1 ip -f mpls route

# Traceroute xuyên backbone
mininet> h1a traceroute -n 10.2.0.1

# Thoát
mininet> exit
```

---

## 📊 Đo lường hiệu năng

### Cách 1: Đo thủ công trong Mininet CLI

```bash
# Đo TCP Throughput (h1a → h2a)
mininet> h2a iperf3 -s &
mininet> h1a iperf3 -c 10.2.0.1 -t 10

# Đo UDP Jitter + Packet Loss (h1a → h3a, 10 Mbps)
mininet> h3a iperf3 -s &
mininet> h1a iperf3 -c 10.3.0.1 -u -b 10M -t 10

# Đo Delay (h1a → h2a, 50 gói)
mininet> h1a ping -c 50 10.2.0.1
```

### Cách 2: Tự động hóa 3 kịch bản

> **Lưu ý**: Topology phải đang chạy, script sẽ dùng `ip netns exec` để chạy lệnh trong namespace của từng node.

```bash
# Mở terminal khác (trong khi topology đang chạy)
cd ~/metro_mpls/scripts

# Chạy tất cả 3 kịch bản (mặc định)
sudo bash run_tests.sh all 10

# Chỉ chạy kịch bản 1 (Flat Network)
sudo bash run_tests.sh 1 10

# Kết quả lưu tại: ../results/raw/
```

### Phân tích kết quả và vẽ biểu đồ

```bash
cd ~/metro_mpls/scripts
python3 collect_results.py \
    ../results/raw \
    ../results/csv \
    ../results/charts \
    $(date +%Y%m%d_%H%M%S)

# Biểu đồ PNG lưu tại: ../results/charts/
```

---

## 📈 Kết quả đo lường (tham khảo)

| Kịch bản | Kiến trúc LAN | Throughput (Mbps) | Delay (ms) | Jitter (ms) | Loss (%) |
|----------|--------------|-------------------|------------|-------------|----------|
| SC-1 | Flat Network | 94.2 | 0.82 | 0.041 | 0.0 |
| SC-2 | 3-Tier (Core–Dist–Acc) | 88.7 | 1.24 | 0.063 | 0.0 |
| SC-3 | Leaf-Spine | **97.5** | **0.61** | **0.028** | 0.0 |

> Kết quả thực tế có thể khác nhau tùy cấu hình máy và phiên bản phần mềm.

---

## 📝 Báo cáo LaTeX

### Cấu trúc báo cáo (Overleaf)

| File | Nội dung |
|------|----------|
| `main.tex` | File LaTeX chính, kết hợp tất cả chương |
| `frontmatter/titlepage.tex` | Trang bìa |
| `frontmatter/abstract.tex` | Tóm tắt (Abstract) |
| `content/C1.tex` | Chương 1 – Giới thiệu |
| `content/C2.tex` | Chương 2 – Cơ sở lý thuyết (LAN, MPLS, Metro Ethernet, OSPF/LDP/MP-BGP) |
| `content/C3.tex` | Chương 3 – Thiết kế mô hình (Topology, bảng IP) |
| `content/C4.tex` | Chương 4 – Triển khai Mininet (cài đặt, code, hướng dẫn) |
| `content/C5.tex` | Chương 5 – Kết quả đo lường và phân tích |
| `content/C6.tex` | Chương 6 – Kết luận và hướng phát triển |

### Biên dịch báo cáo

**Trên Overleaf:** Upload toàn bộ thư mục `source_latex/` → Compile `main.tex`.

**Trên máy local (Ubuntu):**
```bash
sudo apt install texlive-full texlive-lang-other
cd source_latex
pdflatex main.tex
pdflatex main.tex   # Chạy lần 2 để cập nhật mục lục
```

---

## 🔑 Kiến thức lý thuyết quan trọng

### MPLS Label Switching (Push – Swap – Pop)

```
[CE1] → [PE1] → [P1] → [P2] → [PE2] → [CE2]
         PUSH    SWAP   SWAP   POP
        (L100)  L100→200 200→300  (IP)
```

### So sánh 3 kiến trúc LAN

| Tiêu chí | Flat | 3-Tier | Leaf-Spine |
|---------|------|--------|------------|
| Số hop tối đa | 1 | 3-5 | 2 |
| Phụ thuộc STP | Có | Có | Không |
| Khả năng mở rộng | Thấp | Trung bình | Cao |
| Chi phí | Thấp | Trung bình | Cao |
| Phù hợp | Mạng nhỏ | Doanh nghiệp | Data Center |

---

## 🧩 Các lệnh hữu ích

```bash
# Xem tất cả OVS bridge đang chạy
sudo ovs-vsctl show

# Debug namespace của Mininet node
sudo ip netns list
sudo ip netns exec h1a ip addr
sudo ip netns exec p1 ip route

# Bắt gói tin trên backbone (MPLS)
sudo ip netns exec p1 tcpdump -i p1-p2 -n -v mpls

# Dọn dẹp hoàn toàn
sudo mn -c
sudo killall iperf3 iperf 2>/dev/null

# Kiểm tra MPLS kernel module
lsmod | grep mpls
sysctl net.mpls.platform_labels
```

---

## 🐛 Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|------------|-----------|
| `Exception: Another Mininet is running` | Tiến trình cũ chưa tắt | `sudo mn -c` |
| `MPLS: No such file or directory` | Module chưa load | `sudo modprobe mpls_router` |
| `ping: connect: Network is unreachable` | Thiếu route | Kiểm tra `ip route` trên CE/PE |
| `iperf3: error - unable to connect` | Server chưa chạy | Chạy `iperf3 -s` trên host đích trước |

---

## 📚 Tài liệu tham khảo

- RFC 3031 – Multiprotocol Label Switching Architecture
- RFC 5036 – LDP Specification  
- Metro Ethernet Forum (MEF) – Ethernet Service Definitions
- Cisco – Campus Network for High Availability Design Guide
- Mininet Documentation: http://mininet.org/
- FRRouting User Guide: https://docs.frrouting.org/