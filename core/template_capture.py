"""
Item Image Capture Tool (Manual Capture & Screen Freeze Snipper):
Allows clean template capturing of items without yellow hover borders or red dots.
"""

import datetime
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
import cv2
import numpy as np
import pyautogui
import mss
import tkinter as tk
from PIL import Image, ImageTk

import config
from utils import logger
from vision import VisionEngine


def trim_yellow_border_if_present(screen_bgr: np.ndarray, mouse_x: int, mouse_y: int) -> np.ndarray:
    """
    Given a screen capture and logical mouse coordinates, checks if a yellow hover border box
    exists around the cursor. If present, trims the outer yellow border pixels and extracts
    the clean inner item content. Otherwise returns a centered 43x42 crop.
    """
    sh, sw = screen_bgr.shape[:2]
    
    # Define a search region around the mouse (80x80 pixels)
    rx1 = max(0, mouse_x - 40)
    ry1 = max(0, mouse_y - 40)
    rx2 = min(sw, mouse_x + 40)
    ry2 = min(sh, mouse_y + 40)
    
    patch = screen_bgr[ry1:ry2, rx1:rx2]
    if patch.size == 0:
        # Fallback centered crop
        cx1 = max(0, mouse_x - 21)
        cy1 = max(0, mouse_y - 21)
        return screen_bgr[cy1:min(sh, cy1+42), cx1:min(sw, cx1+43)].copy()
        
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    lower_yellow = np.array([15, 120, 120])
    upper_yellow = np.array([40, 255, 255])
    mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if 30 <= w <= 65 and 30 <= h <= 65:
            # Found yellow frame contour in patch
            abs_x = rx1 + x
            abs_y = ry1 + y
            # Trim 2px from all edges to remove outer yellow border lines completely
            inner_x1 = max(0, abs_x + 2)
            inner_y1 = max(0, abs_y + 2)
            inner_x2 = min(sw, abs_x + w - 2)
            inner_y2 = min(sh, abs_y + h - 2)
            
            crop = screen_bgr[inner_y1:inner_y2, inner_x1:inner_x2].copy()
            if crop.shape[0] > 10 and crop.shape[1] > 10:
                logger.info(f"[Capture] Detected yellow slot frame ({w}x{h}px). Trimmed outer border -> Inner item crop: {crop.shape[1]}x{crop.shape[0]}px.")
                return crop
                
    # If no yellow border contour found, return 43x42 crop centered on mouse
    cx1 = max(0, mouse_x - 21)
    cy1 = max(0, mouse_y - 21)
    cx2 = min(sw, cx1 + 43)
    cy2 = min(sh, cy1 + 42)
    return screen_bgr[cy1:cy2, cx1:cx2].copy()


class ScreenFreezeSniper:
    """
    ShareX / Snipping Tool style screen freezing overlay for dragging clean custom item crops.
    """
    def __init__(self):
        self.crop_image: Optional[np.ndarray] = None
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None

    def snipe(self) -> Optional[np.ndarray]:
        with mss.MSS() as sct:
            primary_mon = sct.monitors[1]
            sct_img = sct.grab(primary_mon)
            img_bgr = np.array(sct_img, dtype=np.uint8)[:, :, :3]

        screen_h, screen_w = img_bgr.shape[:2]
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

        root = tk.Tk()
        root.title("Screen Freeze Snipping Tool")
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.config(cursor="cross")

        pil_img = Image.fromarray(img_rgb)
        tk_img = ImageTk.PhotoImage(pil_img)

        canvas = tk.Canvas(root, cursor="cross", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        canvas.create_image(0, 0, image=tk_img, anchor="nw")

        # Instruction text on top
        hint_txt = "ĐANG ĐÓNG BẰNG MÀN HÌNH: Nhấp giữ & kéo chuột để chọn vùng cắt Item (hoặc nhấn ESC để hủy)"
        canvas.create_rectangle(10, 10, len(hint_txt)*9 + 20, 36, fill="black", outline="yellow")
        canvas.create_text(20, 23, text=hint_txt, fill="lime", font=("Consolas", 11, "bold"), anchor="w")

        def on_button_press(event):
            self.start_x = event.x
            self.start_y = event.y
            if self.rect_id:
                canvas.delete(self.rect_id)
            self.rect_id = canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2)

        def on_move_press(event):
            cur_x, cur_y = event.x, event.y
            canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

        def on_button_release(event):
            end_x, end_y = event.x, event.y
            x1, x2 = min(self.start_x, end_x), max(self.start_x, end_x)
            y1, y2 = min(self.start_y, end_y), max(self.start_y, end_y)

            w = x2 - x1
            h = y2 - y1

            if w > 5 and h > 5:
                # Extract physical crop from frozen screen BGR matrix
                self.crop_image = img_bgr[y1:y2, x1:x2].copy()
            root.destroy()

        def on_escape(event):
            self.crop_image = None
            root.destroy()

        canvas.bind("<ButtonPress-1>", on_button_press)
        canvas.bind("<B1-Motion>", on_move_press)
        canvas.bind("<ButtonRelease-1>", on_button_release)
        root.bind("<Escape>", on_escape)

        root.focus_force()
        root.mainloop()

        return self.crop_image


def run_item_capture_tool(vision_engine: VisionEngine) -> None:
    """
    Manual Item Image Capture Tool with Hover+Enter and Screen Freeze Snipper.
    """
    target_dir = config.SELL_ITEMS_DIR
    target_name = "sell_items"

    while True:
        print("\n" + "=" * 65)
        print("  📸 CÔNG CỤ CHỤP ẢNH ITEM MẪU - TBH-TOOL (Tác giả: PVandAI)")
        print("=" * 65)
        print(f"  Thư mục lưu hiện tại: templates/{target_name}/")
        print("  Dung tích ảnh chuẩn: ~43px (Rộng) x 42px (Cao) (Tự loại bỏ viền khung vàng)")
        print("=" * 65)
        print("  [1] Chụp Tức Thì (Di chuột vào ô Item trong game -> Nhấn Enter)")
        print("  [2] Đóng Băng Màn Hình & Cắt Ảnh (Screen Freeze Snipping Tool - ShareX Style)")
        print("  [s] Đổi thư mục lưu (sell_items <-> stash_items)")
        print("  [0] Quay lại Menu chính (hoặc nhấn 'q')")
        print("=" * 65)

        choice = input("Nhập lựa chọn của bạn [0-2, s] (hoặc 'q' để quay lại): ").strip().lower()

        if choice in ["0", "q", "b", "back"]:
            break
        elif choice == "s":
            if target_name == "sell_items":
                target_dir = config.STASH_ITEMS_DIR
                target_name = "stash_items"
            else:
                target_dir = config.SELL_ITEMS_DIR
                target_name = "sell_items"
            print(f"\n[✓] Đã chuyển thư mục đích sang: templates/{target_name}/")
            time.sleep(0.8)
            continue

        elif choice == "1":
            print("\n" + "-" * 65)
            print("🎯 CHẾ ĐỘ CHỤP TỨC THÌ (HOVER + ENTER):")
            print("  1. Di chuột lên ô Item cần chụp trong game.")
            print("  2. Nhấn Enter tại đây (công cụ sẽ tự chụp & cắt bỏ viền khung vàng).")
            print("  3. Nhập tên file mong muốn (hoặc nhấn Enter để dùng tên tự động).")
            print("  (Gõ 's' để đổi thư mục lưu | '0' hoặc 'q' rồi nhấn Enter để quay lại Menu chính)")
            print("-" * 65)

            while True:
                user_cmd = input(f"\n👉 [Lưu tại: templates/{target_name}/] Hãy di chuột vào ô Item trong game và nhấn ENTER (nhấn 's' để đổi thư mục, 'c'/'esc'/'0'/'q' để quay lại): ").strip()
                if user_cmd.lower() in ["0", "q", "b", "back", "exit", "esc", "c", "cancel", "\x1b"]:
                    break
                elif user_cmd.lower() == "s":
                    if target_name == "sell_items":
                        target_dir = config.STASH_ITEMS_DIR
                        target_name = "stash_items"
                    else:
                        target_dir = config.SELL_ITEMS_DIR
                        target_name = "sell_items"
                    print(f" [✓] Đã chuyển thư mục lưu sang: templates/{target_name}/")
                    continue

                # Get current mouse coordinates on display
                mx, my = pyautogui.position()
                logger.info(f" [+] Đang chụp tại vị trí con trỏ chuột: ({mx}, {my})...")

                # Capture entire monitor 1 screen BGR
                with mss.MSS() as sct:
                    primary_mon = sct.monitors[1]
                    sct_img = sct.grab(primary_mon)
                    full_screen = np.array(sct_img, dtype=np.uint8)[:, :, :3]

                # Convert logical mouse coordinates to physical display coordinates if DPI scaled
                phys_mx = int(mx * vision_engine.scale_x)
                phys_my = int(my * vision_engine.scale_y)

                # Extract clean item graphic (automatically trimming yellow border if present)
                crop_img = trim_yellow_border_if_present(full_screen, phys_mx, phys_my)

                if crop_img is None or crop_img.shape[0] == 0 or crop_img.shape[1] == 0:
                    print(" [!] Lỗi: Không thể cắt ảnh tại vị trí chuột.")
                    continue

                ch, cw = crop_img.shape[:2]
                print(f" [✓] Đã chụp xong ảnh Item kích thước: {cw}px (Rộng) x {ch}px (Cao).")

                # Prompt for custom filename or auto timestamp with ESC / 'c' cancel option
                default_filename = f"item_{target_name[:4]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                name_input = input(f"   Nhập tên file (gõ 'c' / 'esc' để HỦY) [Mặc định: {default_filename}]: ").strip()

                if name_input.lower() in ["c", "cancel", "esc", "\x1b", "huy", "0", "q"]:
                    print(" [!] Đã HỦY lưu mẫu ảnh vật phẩm này.")
                    continue

                if not name_input:
                    filename = default_filename
                else:
                    filename = name_input if name_input.endswith(".png") else f"{name_input}.png"

                save_path = target_dir / filename
                cv2.imwrite(str(save_path), crop_img)

                logger.info(f" [✓] Đã lưu mẫu ảnh thành công: templates/{target_name}/{filename}")
                vision_engine.load_templates()
                print(" [✓] Đã cập nhật bộ nhớ mẫu ảnh (Vision Cache)!")

        elif choice == "2":
            print("\n" + "-" * 65)
            print("❄️ CHẾ ĐỘ ĐÓNG BẰNG MÀN HÌNH & CẮT ẢNH (SHAREX STYLE):")
            print("  - Màn hình sẽ được đóng bằng ngay lập tức.")
            print("  - Nhấp giữ & kéo chuột để khoanh vùng Item cần cắt.")
            print("  - Nhấn Esc để hủy bỏ.")
            print("-" * 65)

            input("Nhấn ENTER để bắt đầu đóng bằng màn hình... ")
            time.sleep(0.3)

            sniper = ScreenFreezeSniper()
            crop_img = sniper.snipe()

            if crop_img is not None and crop_img.shape[0] > 0 and crop_img.shape[1] > 0:
                ch, cw = crop_img.shape[:2]
                print(f"\n [✓] Đã cắt vùng ảnh kích thước: {cw}px (Rộng) x {ch}px (Cao).")

                # Prompt for custom filename or auto timestamp with ESC / 'c' cancel option
                default_filename = f"item_{target_name[:4]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                name_input = input(f"   Nhập tên file mẫu (gõ 'c' / 'esc' để HỦY) [Mặc định: {default_filename}]: ").strip()

                if name_input.lower() in ["c", "cancel", "esc", "\x1b", "huy", "0", "q"]:
                    print(" [!] Đã HỦY lưu mẫu ảnh vật phẩm này.")
                    time.sleep(0.8)
                    continue

                if not name_input:
                    filename = default_filename
                else:
                    filename = name_input if name_input.endswith(".png") else f"{name_input}.png"

                save_path = target_dir / filename
                cv2.imwrite(str(save_path), crop_img)

                logger.info(f" [✓] Đã lưu mẫu ảnh thành công: templates/{target_name}/{filename}")
                vision_engine.load_templates()
                print(" [✓] Đã cập nhật bộ nhớ mẫu ảnh (Vision Cache)!")
            else:
                print(" [!] Đã hủy bỏ thao tác cắt ảnh.")
                time.sleep(0.8)
