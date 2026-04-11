# Hướng dẫn cài đặt và chạy mô phỏng trên Ubuntu 22.04

## PHẦN 1: CÀI ĐẶT MÔI TRƯỜNG

### 1.1 Cập nhật hệ thống

```bash
sudo apt update && sudo apt upgrade -y
sudo apt autoremove -y
```

### 1.2 Cài đặt Mininet

Cách ổn định nhất cho Ubuntu 22.04 là cài từ package:

```bash
sudo apt install -y mininet

# Kiểm tra version
mn --version
```

Nếu muốn cài từ source (phiên bản mới hơn):

```bash
git clone https://github.com/mininet/mininet
cd mininet
git tag   # xem các version
git checkout -b mininet-2.3.1 2.3.1
./util/install.sh -a
```

### 1.3 Cài Open vSwitch

```bash
sudo apt install -y openvswitch-switch openvswitch-common

# Khởi động OVS
sudo systemctl enable openvswitch-switch
sudo systemctl start openvswitch-switch

# Kiểm tra
sudo ovs-vsctl show
sudo ovs-appctl version
```

### 1.4 Cài các công cụ đo lường

```bash
sudo apt install -y \
    iperf3 iperf \
    tcpdump \
    net-tools \
    iproute2 \
    iputils-ping \
    traceroute \
    nmap \
    netcat-openbsd

# Kiểm tra iperf3
iperf3 --version
```

### 1.5 Cài Python và thư viện

```bash
# Python 3 (đã có sẵn trên Ubuntu 22.04)
python3 --version

# pip
sudo apt install -y python3-pip

# Thư viện cho vẽ biểu đồ
pip3 install matplotlib numpy scipy

# Hoặc dùng apt (ổn định hơn):
sudo apt install -y python3-matplotlib python3-numpy python3-scipy
```

### 1.6 Cài MPLS kernel module

```bash
# Load module (hiệu lực ngay lập tức)
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel

# Kiểm tra
lsmod | grep mpls

# Bật platform labels
sudo sysctl -w net.mpls.platform_labels=1000

# Để giữ sau reboot, thêm vào sysctl.conf:
echo 'net.mpls.platform_labels = 1000' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# Xác nhận
sysctl net.mpls.platform_labels
```

---

## PHẦN 2: XÁC NHẬN CÀI ĐẶT

### 2.1 Test Mininet cơ bản

```bash
# Test topology đơn giản
sudo mn --topo single,3 --test ping

# Kết quả mong đợi:
# *** Results: 0% dropped (6/6 received)

# Dọn dẹp
sudo mn -c
```

### 2.2 Test Open vSwitch

```bash
sudo mn --switch ovsk --topo linear,3 --test pingall
sudo mn -c
```

### 2.3 Test MPLS

```bash
# Kiểm tra module
lsmod | grep mpls
# Output mong đợi:
# mpls_iptunnel    16384  0
# mpls_router      16384  1 mpls_iptunnel

# Kiểm tra iproute2 hỗ trợ MPLS
ip -f mpls route help
# Không báo lỗi là thành công
```

---

## PHẦN 3: CHẠY TOPOLOGY MPLS METRO

### 3.1 Clone/Copy project

```bash
# Giả sử project đặt tại ~/CuoiKy
cd ~/CuoiKy
ls source/   # Phải có mpls_metro_topology.py, flat.py, coreditrubutionaccess.py, spineleaf.py
```

### 3.2 Chạy topology

```bash
# Dọn rác Mininet cũ
sudo mn -c

# Chạy topology chính (tổng thể)
cd ~/CuoiKy/source
sudo python3 mpls_metro_topology.py
```

### 3.3 Kiểm tra trong CLI

```bash
# Sau khi thấy "mininet> "

# Xem tất cả node
mininet> nodes

# Kết quả mong đợi: h1a h1b h1c h2a h2b h2c h2d h3a h3b h3c h3d
#                   ce1 ce2 ce3 pe1 pe2 pe3 p1 p2
#                   b1sw b2acc1 b2acc2 b2dist b2core b3sp1 b3sp2 b3lf1 b3lf2

# Ping chi nhánh 1 → chi nhánh 2
mininet> h1a ping -c 10 10.2.0.1

# Ping chi nhánh 1 → chi nhánh 3
mininet> h1a ping -c 10 10.3.0.1

# Kiểm tra toàn bộ
mininet> pingall
```

### 3.4 Xem bảng định tuyến MPLS

```bash
# Bảng route của P1 (Core router)
mininet> p1 ip route

# Bảng MPLS (nếu đã cấu hình)
mininet> p1 ip -f mpls route

# Route của PE1
mininet> pe1 ip route

# Route của CE1
mininet> ce1 ip route
```

### 3.5 Bắt gói MPLS bằng tcpdump

```bash
# Trong một xterm mở từ Mininet
mininet> xterm p1

# Trong cửa sổ p1:
tcpdump -i p1-p2 -n -v mpls
# Gửi traffic từ h1a → h2a để thấy MPLS label

# Hoặc từ terminal host (ngoài Mininet):
sudo ip netns exec p1 tcpdump -i p1-p2 -n mpls
```

### 3.6 Cấu hình MPLS sau khi topology chạy

```bash
# Mở terminal mới (giữ Mininet CLI ở terminal ra)
cd ~/CuoiKy/scripts
sudo bash mpls_config.sh
```

---

## PHẦN 4: ĐO LƯỜNG HIỆU NĂNG

### 4.1 Đo thủ công

```bash
# Terminal 1: Topology đang chạy
# Terminal 2: Dùng ip netns exec

# Đo TCP Throughput (h1a → h2a)
sudo ip netns exec h2a iperf3 -s -D
sudo ip netns exec h1a iperf3 -c 10.2.0.1 -t 10 -J > ../results/raw/tcp_sc1.json

# Đo UDP Jitter (h1a → h3a)
sudo ip netns exec h3a iperf3 -s -D
sudo ip netns exec h1a iperf3 -c 10.3.0.1 -u -b 10M -t 10 -J > ../results/raw/udp_sc1.json

# Đo Ping Delay
sudo ip netns exec h1a ping -c 50 10.2.0.1 > ../results/raw/ping_sc1_h1a_h2a.log

# Dừng server
sudo ip netns exec h2a killall iperf3
sudo ip netns exec h3a killall iperf3
```

### 4.2 Chạy tự động (3 kịch bản)

```bash
cd ~/CuoiKy/scripts
sudo bash run_tests.sh all 10
```

### 4.3 Phân tích và vẽ biểu đồ

```bash
python3 collect_results.py \
    ../results/raw \
    ../results/csv \
    ../results/charts \
    $(date +%Y%m%d)
```

---

## PHẦN 5: XỬ LÝ LỖI THƯỜNG GẶP

### Lỗi: "cannot reopen network namespace"

```bash
sudo mn -c
sudo systemctl restart openvswitch-switch
```

### Lỗi: "RTNETLINK answers: File exists"

```bash
# IP đã được gán trước đó, dọn sạch:
sudo mn -c
```

### Lỗi: "modprobe: FATAL: Module mpls_router not found"

```bash
# Kernel không hỗ trợ MPLS – kiểm tra version:
uname -r   # Cần >= 4.1

# Cài thêm kernel headers (nếu cần build module):
sudo apt install -y linux-headers-$(uname -r)
```

### Lỗi: "iperf3: error - the server is busy"

```bash
# Kill iperf3 server cũ:
sudo ip netns exec h2a killall iperf3 2>/dev/null
# Đợi vài giây rồi thử lại
```

### Mininet bị treo

```bash
# Kill tất cả Mininet process
sudo mn -c
sudo killall python3 2>/dev/null
sudo killall ovs-vswitchd 2>/dev/null
sudo systemctl restart openvswitch-switch
```
