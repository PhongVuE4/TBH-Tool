"""Command-line entry points for TBH-Tool."""
import argparse
import sys
import time
import pyautogui
import config
from app.automation_coordinator import ensure_alchemy_tab_selected, ensure_ui_tabs_ready, process_match
from automation import AutomationEngine
from capture import run_item_capture_tool
from get_region import interactive_region_picker
from utils import logger
from vision import VisionEngine

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TBH-Tool Desktop Automation v2.0 (PVandAI)")
    parser.add_argument("--mode", choices=["gui", "live", "cli", "menu"], default="gui", help="Execution mode (default: gui)")
    return parser.parse_args()


def run_live_loop(
    vision: VisionEngine,
    automation: AutomationEngine,
    scan_interval: float = config.SCAN_INTERVAL,
) -> None:
    """Runs continuous live loop with category-filtered ultra-fast template matching."""
    logger.info("\n>>> BẮT ĐẦU CHẾ ĐỘ CHẠY TỰ ĐỘNG (TBH-TOOL - PVandAI) <<<")
    logger.info(f"Tần suất quét: {scan_interval}s | Dung tích ô bán: {config.SALES_SLOTS_CAPACITY} ô")
    
    item_region = config.INVENTORY_REGION if config.INVENTORY_REGION is not None else config.GAME_REGION
    if config.INVENTORY_REGION is not None:
        logger.info(f"Vùng quét Balo (INVENTORY_REGION): {config.INVENTORY_REGION}")
    else:
        logger.info(f"Vùng quét Game (GAME_REGION): {config.GAME_REGION}")

    logger.info("Tính năng: Cất rương | Bán | Mở Rương | Tab Alchemy | Cuộn Balo | Kiểm tra UI HERO/STASH/CUBE")
    logger.info("Nhấn Ctrl + C hoặc di chuyển chuột lên góc trên-trái (0,0) để DỪNG.\n")

    logger.info("[+] ĐANG CHUẨN BỊ THAO TÁC: Vui lòng chuyển sang cửa sổ Game trong 3 giây...")
    for i in range(3, 0, -1):
        logger.info(f"    Bắt đầu sau: {i}s...")
        time.sleep(1)
    automation.prime_input_hooks()
    logger.info("[✓] Đã sẵn sàng tự động hóa!\n")

    last_cube_tab_check = 0.0
    last_ui_tab_check = 0.0
    last_chest_check = 0.0
    last_disconnect_log = 0.0
    is_disconnected = False
    dc_clean_counter = 0
    inv_scroll_depth = 0
    needs_inventory_focus = True

    try:
        while True:
            loop_start = time.time()
            now = loop_start

            # === PRIORITY 0: Disconnection / Reconnecting Guard ===
            has_dc_templates = any(
                cat == "disconnected" for _, (_, cat) in vision.template_cache.items()
            )
            if has_dc_templates:
                full_img, _ = vision.capture_screen(None)
                dc_matches = vision.find_all_matches(
                    full_img,
                    categories={"disconnected"},
                    capture_offset=(0, 0),
                    threshold=0.65,
                    max_results=1,
                    early_exit=True,
                )
                if dc_matches:
                    dc_clean_counter = 0
                    if not is_disconnected:
                        is_disconnected = True
                        logger.warning(
                            f"\n[PAUSED] MẤT KẾT NỐI / ĐANG RECONNECT! (Phát hiện: {dc_matches[0].template_name})"
                            "\nTự động tạm dừng tất cả thao tác chuột & bàn phím. Đang chờ kết nối khôi phục..."
                        )
                        last_disconnect_log = now
                    elif now - last_disconnect_log > 8.0:
                        logger.info("[PAUSED] Trạng thái: Bảng thông báo mất kết nối vẫn đang hiển thị. Đang chờ game tự động kết nối lại...")
                        last_disconnect_log = now

                    time.sleep(0.5)
                    continue
                elif is_disconnected:
                    dc_clean_counter += 1
                    if dc_clean_counter < 5:
                        logger.debug(f"[Xác nhận kết nối] Đang chờ bảng cảnh báo đóng hoàn toàn ({dc_clean_counter}/5)...")
                        time.sleep(0.5)
                        continue
                    else:
                        is_disconnected = False
                        dc_clean_counter = 0
                        logger.info(
                            "\n[RESUMED] [✓] Đã khôi phục kết nối mạng và bảng cảnh báo mất kết nối đã tự đóng hoàn toàn!"
                            "\nTiếp tục tự động hóa bình thường.\n"
                        )
                        needs_inventory_focus = True

            # === PRIORITY 1: Inventory items (sell / stash) ===
            inv_img, box_info = vision.capture_screen(item_region)
            inv_offset = (box_info["offset_x"], box_info["offset_y"])

            inv_matches = vision.find_all_matches(
                inv_img,
                categories={"stash_item"},
                capture_offset=inv_offset,
                early_exit=True,
                max_results=1,
            )
            if not inv_matches:
                inv_matches = vision.find_all_matches(
                    inv_img,
                    categories={"sell_item"},
                    capture_offset=inv_offset,
                    early_exit=True,
                    max_results=1,
                )

            acted_on_inventory = False
            for match in inv_matches:
                executed = process_match(match, automation)
                if executed:
                    acted_on_inventory = True
                    needs_inventory_focus = False
                    break

            # Scroll bag when empty view
            if (
                not acted_on_inventory
                and config.INVENTORY_SCROLL_ENABLED
                and item_region is not None
            ):
                focus = needs_inventory_focus
                if inv_scroll_depth < config.INVENTORY_SCROLL_MAX_STEPS:
                    automation.scroll_inventory_region(
                        item_region,
                        direction="down",
                        ticks=config.INVENTORY_SCROLL_TICKS,
                        quiet=True,
                        ensure_focus=focus,
                    )
                    needs_inventory_focus = False
                    inv_scroll_depth += 1
                elif inv_scroll_depth > 0:
                    automation.scroll_inventory_region(
                        item_region,
                        direction="up",
                        ticks=config.INVENTORY_SCROLL_TICKS * inv_scroll_depth,
                        quiet=True,
                        ensure_focus=focus,
                    )
                    needs_inventory_focus = False
                    inv_scroll_depth = 0

            # Sell button when capacity full
            if automation.current_sales_slots >= config.SALES_SLOTS_CAPACITY:
                full_screen_img, _ = vision.capture_screen(None)
                sell_btns = vision.find_all_matches(
                    full_screen_img,
                    categories={"sell_button"},
                    capture_offset=(0, 0),
                    max_results=1,
                    early_exit=True,
                )
                if sell_btns:
                    process_match(sell_btns[0], automation)
                    needs_inventory_focus = True

            # === PRIORITY 2: Reward chests ===
            if now - last_chest_check >= 1.5:
                last_chest_check = now
                has_chest_templates = any(
                    cat in ("standard_chest", "boss_chest", "treasure_chest")
                    for _, (_, cat) in vision.template_cache.items()
                )
                if has_chest_templates:
                    full_screen_img, _ = vision.capture_screen(None)
                    chest_matches = vision.find_all_matches(
                        full_screen_img,
                        categories={"standard_chest", "boss_chest", "treasure_chest"},
                        capture_offset=(0, 0),
                        max_results=1,
                        early_exit=True,
                    )
                    if chest_matches:
                        executed = process_match(chest_matches[0], automation)
                        if executed:
                            needs_inventory_focus = True
                            time.sleep(0.35)

            # === PRIORITY 3: Infrequent UI / Alchemy maintenance ===
            if now - last_ui_tab_check > config.UI_TAB_CHECK_INTERVAL:
                ready = ensure_ui_tabs_ready(vision, automation)
                last_ui_tab_check = time.time()
                if not ready:
                    needs_inventory_focus = True

            if now - last_cube_tab_check > 10.0:
                ensure_alchemy_tab_selected(vision, automation)
                last_cube_tab_check = time.time()
                needs_inventory_focus = True

            elapsed = time.time() - loop_start
            sleep_time = max(0.0, scan_interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("\n[!] Đã dừng tự động hóa (Người dùng nhấn Ctrl+C).")
    except pyautogui.FailSafeException:
        logger.critical("\n[!] CẢNH BÁO: Đã kích hoạt khẩn cấp FailSafe! Đã dừng tự động hóa.")
    except Exception as e:
        logger.exception(f"Lỗi ngoài dự kiến trong vòng lặp chính: {e}")
    finally:
        automation.sanitize_modifier_keys()
        vision.close()
        logger.info("Vision session closed. Exiting.")


def display_menu() -> None:
    """Displays interactive Vietnamese terminal selection menu."""
    vision = VisionEngine()
    automation = AutomationEngine()

    while True:
        print("\n" + "=" * 65)
        print("         TBH-Tool v2.0 (PVandAI)")
        print("=" * 65)
        print("  [1] Chạy Tự Động (Run)")
        print("  [2] Nạp Lại Mẫu Ảnh Item (Reload Template Assets)")
        print("  [3] Xác Định Tọa Độ Vùng Màn Hình (Inventory & Game Region)")
        print("  [4] Chụp Ảnh Item Mẫu Tự Động (Item Template Capture Tool - ~43x42)")
        print("  [0] Thoát Chương Trình (Exit - hoặc nhấn 'q')")
        print("=" * 65)
        
        choice = input("Nhập lựa chọn của bạn [0-4] (hoặc 'q' để thoát): ").strip().lower()

        if choice in ["1", "live", "auto"]:
            run_live_loop(vision, automation)
            input("\nNhấn Enter để quay lại Menu chính...")
        elif choice in ["2", "reload", "refresh"]:
            print("\n[+] Đang nạp lại danh sách mẫu ảnh item từ thư mục templates/...")
            count = vision.load_templates()
            print(f" [✓] Nạp lại thành công {count} ảnh mẫu vào bộ nhớ cache!")
            time.sleep(1.2)
        elif choice in ["3", "region"]:
            interactive_region_picker()
            input("\nNhấn Enter để quay lại Menu chính...")
        elif choice in ["4", "capture", "crop"]:
            run_item_capture_tool(vision)
            input("\nNhấn Enter để quay lại Menu chính...")
        elif choice in ["0", "q", "b", "back", "exit"]:
            print("\nCảm ơn bạn đã sử dụng TBH-Tool v2.0 (PVandAI)! Tạm biệt.")
            sys.exit(0)
        else:
            print("\n[!] Lựa chọn không hợp lệ. Vui lòng thử lại!")
            time.sleep(1)


def main() -> None:
    args = parse_arguments()
    if args.mode == "gui":
        from gui import run_gui_app
        run_gui_app()
    elif args.mode == "live":
        vision = VisionEngine()
        automation = AutomationEngine()
        run_live_loop(vision, automation)
    else:
        try:
            display_menu()
        except KeyboardInterrupt:
            print("\n\nĐã thoát chương trình bằng Ctrl+C.")
            sys.exit(0)


if __name__ == "__main__":
    main()
