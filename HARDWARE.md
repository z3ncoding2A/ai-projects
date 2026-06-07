{
  "kernel": "7.0.9-zen1-1-zen",
  "cpu": "Intel(R) Core(TM) i5-14400F",
  "ram": "15Gi",
  "gpu": "NVIDIA Corporation GB206 [GeForce RTX 5060] (rev a1)"
}
System:
  Host: ai-arch Kernel: 7.0.9-zen1-1-zen arch: x86_64 bits: 64
  Console: pty pts/3 Distro: Arch Linux
Machine:
  Type: Desktop System: Micro product: G250 v: 1.0 serial: <superuser required>
  Mobo: ASRock model: B760M-C/D4 serial: <superuser required> Firmware: UEFI
    vendor: American Megatrends LLC. v: 8.01.MC01 date: 01/20/2026
CPU:
  Info: 6-core Intel Core i5-14400F [MT MCP] speed (MHz): avg: 1320
    min/max: 800/4700
Graphics:
  Device-1: NVIDIA GB206 [GeForce RTX 5060] driver: nvidia v: 595.71.05
  Display: unspecified server: X.org v: 1.21.1.22 with: Xwayland v: 24.1.11
    driver: X: loaded: nvidia gpu: nv_platform,nvidia,nvidia-nvswitch tty: 84x48
    resolution: 3840x2160
  API: OpenGL v: 4.6.0 compat-v: 4.6 vendor: mesa v: 26.1.1-arch1.2
    note: console (EGL sourced) renderer: NVIDIA GeForce RTX 5060/PCIe/SSE2, zink
    Vulkan 1.4(NVIDIA GeForce RTX 5060 (NVIDIA_PROPRIETARY)), llvmpipe (LLVM
    22.1.5 256 bits)
  Info: Tools: api: clinfo, eglinfo, glxinfo, vulkaninfo gpu: lact,
    nvidia-settings, nvidia-smi wl: nwg-displays x11: xdpyinfo,xprop
Network:
  Device-1: Intel Ethernet I219-V driver: e1000e
  Device-2: Intel Dual Band Wireless-AC 3168NGW [Stone Peak] driver: iwlwifi
Drives:
  Local Storage: total: 1.82 TiB used: 1.01 TiB (55.5%)
Info:
  Memory: total: 16 GiB available: 15.44 GiB used: 6.17 GiB (40.0%)
  Processes: 353 Uptime: 3h 49m Init: systemd Shell: sysinfo_jq.sh inxi: 3.3.40
NAME          SIZE TYPE MOUNTPOINTS
zram0        15.4G disk [SWAP]
nvme0n1     931.5G disk 
└─nvme0n1p1 931.5G part /mnt
nvme1n1     931.5G disk 
├─nvme1n1p1     1G part /boot
├─nvme1n1p2   150G part /
└─nvme1n1p3 780.5G part /home
