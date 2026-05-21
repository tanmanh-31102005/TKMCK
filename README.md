# Thiết Kế & Triển Khai Mạng Metro Ethernet sử dụng MPLS

## Mô tả
Dự án cuối kỳ môn Thiết kế Mạng nhằm mục tiêu xây dựng và mô phỏng mô hình mạng Metro Ethernet MAN sử dụng công nghệ MPLS (Multiprotocol Label Switching) để kết nối 3 chi nhánh doanh nghiệp thông qua hạ tầng mạng của nhà cung cấp dịch vụ (ISP). Dự án tập trung nghiên cứu, đo lường và đánh giá hiệu năng (Throughput, Delay, Packet Loss, Jitter) khi các chi nhánh sử dụng các kiến trúc mạng nội bộ khác nhau bao gồm: Flat Network (Mạng phẳng), 3-Tier (Core - Distribution - Access) và Leaf-Spine (Mạng 2 lớp).

## Kiến trúc / Topology
Dự án triển khai mô hình mạng Metro Ethernet kết nối 3 chi nhánh qua mạng xương sống MPLS (P và PE routers).

![Sơ đồ mạng](LOGIC.jpg)

### Chi tiết các phân đoạn mạng:
* **ISP Backbone**: Gồm 3 router biên PE (PE1, PE2, PE3) và 4 router lõi P (P1, P2, P3, P4) chạy định tuyến OSPF và phân phối nhãn MPLS LDP.
* **Chi nhánh 1 (Flat LAN)**: Mạng phẳng với các host nằm chung Layer 2.
* **Chi nhánh 2 (3-Tier LAN)**: Mạng 3 lớp Core-Distribution-Access chia làm 3 VLAN riêng biệt (VLAN 10 Admin, VLAN 20 Lab, VLAN 30 Guest).
* **Chi nhánh 3 (Leaf-Spine LAN)**: Mạng Clos 2 lớp hiện đại tối ưu hóa băng thông bằng ECMP.

## Công nghệ sử dụng
- Python 3.x
- Mininet 2.x
- VMware Workstation
- Open vSwitch (OVS)
- Linux Kernel MPLS modules
- iperf3 & ping
- Matplotlib & NumPy

## Cách chạy / cài đặt

### Bước 1: Cài đặt các gói phụ thuộc trên Ubuntu
Chạy các lệnh dưới đây để cài đặt môi trường giả lập:
```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch iperf3 python3-pip
sudo service openvswitch-switch start
pip3 install matplotlib numpy pyyaml
```

### Bước 2: Kích hoạt MPLS trong Linux Kernel
```bash
sudo modprobe mpls_router
sudo modprobe mpls_iptunnel
```

### Bước 3: Chạy mô phỏng và đo lường

* **Cách 1: Chạy tự động toàn bộ kịch bản kiểm thử (Khuyến nghị)**
  Script này sẽ tự động khởi tạo Mininet, chạy kịch bản gửi tải mạng qua các chi nhánh, thu thập dữ liệu và xuất biểu đồ so sánh:
  ```bash
  sudo bash 52300221_Source_Code/scripts/run_all_tests.sh
  ```
  *(Các biểu đồ kết quả sẽ được lưu tại thư mục `52300221_Source_Code/results/charts/`)*

* **Cách 2: Chạy chế độ giả lập nhanh (Mock mode)**
  Chạy kiểm tra logic vẽ biểu đồ mà không cần chạy mạng Mininet thực tế:
  ```bash
  bash 52300221_Source_Code/scripts/run_all_tests.sh --mock
  ```

* **Cách 3: Chạy độc lập từng chi nhánh**
  ```bash
  sudo bash 52300221_Source_Code/scripts/run_flat_tests.sh      # Chi nhánh 1
  sudo bash 52300221_Source_Code/scripts/run_3tier_tests.sh     # Chi nhánh 2
  sudo bash 52300221_Source_Code/scripts/run_leafspine_tests.sh # Chi nhánh 3
  ```

* **Cách 4: Chạy Mininet CLI để cấu hình & test thủ công**
  ```bash
  sudo python3 52300221_Source_Code/topology/metro_full.py
  ```
  Khi vào giao diện dòng lệnh `mininet>`, có thể chạy:
  ```bash
  mininet> pingall                  # Ping kiểm tra kết nối toàn mạng
  mininet> host1 ping -c 3 web1     # Ping liên chi nhánh qua MPLS
  mininet> p1 ip -f mpls route show # Xem bảng chuyển mạch nhãn MPLS trên router P1
  ```
