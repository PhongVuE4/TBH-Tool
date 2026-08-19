"""
Interactive Helper: Accurately find and AUTOMATICALLY SAVE your INVENTORY_REGION and GAME_REGION coordinates to config.json.
"""

import time
from pathlib import Path
import pyautogui

import config


def save_region_to_config(region_name: str, left: int, top: int, width: int, height: int) -> bool:
    """Updates config.json file and in-memory configuration with specified region dictionary."""
    try:
        config.update_region(region_name, left, top, width, height)
        return True
    except Exception as e:
        print(f"[!] Lỗi khi lưu cấu hình: {e}")
        return False


def capture_region(region_name: str = "INVENTORY_REGION") -> dict:
    title = "VÙNG BALO / INVENTORY" if region_name == "INVENTORY_REGION" else "VÙNG GAME / KHUNG CỬA SỔ"
    print("\n" + "=" * 65)
    print(f" XÁC ĐỊNH TỌA ĐỘ {title} ({region_name})")
    print("=" * 65)
    print("1. Mở cửa sổ game của bạn để hiển thị rõ trên màn hình.")
    print(f"2. Di chuyển chuột đến GÓC TRÊN-BÊN TRÁI (Top-Left) của {title}.")
    print("   Đang chờ 5 giây...")
    for i in range(5, 0, -1):
        print(f"   {i}...", end="\r")
        time.sleep(1)

    top_left_x, top_left_y = pyautogui.position()
    print(f"\n[+] Đã ghi nhận Góc Trên-Trái: ({top_left_x}, {top_left_y})")

    print(f"\n3. Bây giờ di chuyển chuột đến GÓC DƯỚI-BÊN PHẢI (Bottom-Right) của {title}.")
    print("   Đang chờ 5 giây...")
    for i in range(5, 0, -1):
        print(f"   {i}...", end="\r")
        time.sleep(1)

    bottom_right_x, bottom_right_y = pyautogui.position()
    print(f"\n[+] Đã ghi nhận Góc Dưới-Phải: ({bottom_right_x}, {bottom_right_y})")

    width = max(1, bottom_right_x - top_left_x)
    height = max(1, bottom_right_y - top_left_y)

    region_dict = {
        "left": top_left_x,
        "top": top_left_y,
        "width": width,
        "height": height,
    }

    print("\n" + "=" * 65)
    print(f" 📋 TỌA ĐỘ {region_name} MỚI CỦA BẠN:")
    print("=" * 65)
    print(f'{region_name} = {{\n    "left": {top_left_x},\n    "top": {top_left_y},\n    "width": {width},\n    "height": {height}\n}}')
    print("=" * 65)

    if save_region_to_config(region_name, top_left_x, top_left_y, width, height):
        print(f" [✓] ĐÃ TỰ ĐỘNG LƯU {region_name} VÀO FILE CẤU HÌNH config.json!")
        print(f"     (Đường dẫn: {config.CONFIG_JSON_PATH})")
    else:
        print(" [!] Không thể tự động lưu. Vui lòng chỉnh sửa thủ công file config.json.")

    print("=" * 65 + "\n")
    return region_dict


def interactive_region_picker():
    print("\n" + "=" * 65)
    print("  📐 CÔNG CỤ ĐO TỌA ĐỘ VÙNG MÀN HÌNH - TBH-TOOL (PVandAI)")
    print("=" * 65)
    print("  [1] Đo Vùng Balo / Inventory (INVENTORY_REGION - Khuyên dùng để không click nhầm đồ trong rương)")
    print("  [2] Đo Vùng Cửa Sổ Game / Nút Bán (GAME_REGION)")
    print("  [0] Quay lại Menu chính (hoặc nhấn 'q')")
    print("=" * 65)
    choice = input("Nhập lựa chọn của bạn [0-2] (hoặc 'q' để quay lại): ").strip().lower()
    if choice in ["0", "q"]:
        return
    elif choice == "1":
        capture_region("INVENTORY_REGION")
    elif choice == "2":
        capture_region("GAME_REGION")


if __name__ == "__main__":
    interactive_region_picker()
