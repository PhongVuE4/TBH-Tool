"""Qt worker that runs the automation cycle away from the presentation layer."""
import time
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
import config
from automation import AutomationEngine
from vision import VisionEngine
from utils import log_event, logger

class AutomationWorker(QThread):
    log_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(str)
    templates_count_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._running = False
        self._paused = False
        self.vision: Optional[VisionEngine] = None
        self.automation: Optional[AutomationEngine] = None

    def initialize_engines(self) -> int:
        try:
            self.vision = VisionEngine()
            self.automation = AutomationEngine()
            count = len(self.vision.template_cache)
            self.templates_count_signal.emit(count)
            return count
        except Exception as e:
            logger.exception(f"Engine initialization failure: {e}")
            return 0

    def reload_templates(self) -> int:
        if self.vision:
            self.vision.load_templates()
            count = len(self.vision.template_cache)
            self.templates_count_signal.emit(count)
            logger.info(f"Reloaded {count} template assets into memory cache.")
            return count
        return 0

    def start_automation(self):
        self._running = True
        self._paused = False
        if self.automation:
            self.automation.set_interrupted(False)
        if not self.isRunning():
            self.start()

    def pause_automation(self):
        self._paused = True
        if self.automation:
            self.automation.set_interrupted(True)
        self.status_signal.emit("PAUSED")
        logger.warning("[PAUSED] Automation engine paused.")

    def resume_automation(self):
        self._paused = False
        if self.automation:
            self.automation.set_interrupted(False)
        self.status_signal.emit("RUNNING")
        logger.info("[RESUMED] Automation engine resumed.")

    def stop_automation(self):
        self._running = False
        self._paused = False
        self.status_signal.emit("STOPPED")
        if self.automation:
            self.automation.set_interrupted(True)
        logger.warning("[STOPPED] Emergency Stop triggered!")

    def run(self):
        if not self.vision or not self.automation:
            self.initialize_engines()

        from app.automation_coordinator import (
            ensure_alchemy_tab_selected,
            ensure_ui_tabs_ready,
            process_match,
        )

        log_event("SYSTEM", "[+] PREPARING AUTOMATION: Please switch to your Game window in 3 seconds...")
        self.status_signal.emit("STARTING (3s)")

        for i in range(3, 0, -1):
            if not self._running:
                return
            log_event("SYSTEM", f"    Starting automation in: {i}s...")
            self.status_signal.emit(f"STARTING ({i}s)")
            time.sleep(1.0)

        if not self._running:
            return

        self.status_signal.emit("RUNNING")
        log_event("ACTION", "[✓] Automation Engine Active!")

        item_region = config.INVENTORY_REGION if config.INVENTORY_REGION is not None else config.GAME_REGION
        last_cube_tab_check = 0.0
        last_ui_tab_check = 0.0
        last_chest_check = 0.0
        inv_scroll_depth = 0
        needs_inventory_focus = True
        last_search_status_at = 0.0

        if self.automation:
            self.automation.prime_input_hooks()

        while self._running:
            if self._paused:
                time.sleep(0.2)
                continue

            loop_start = time.time()
            now = loop_start

            try:
                # Priority 0: Disconnection Check
                has_dc = any(cat == "disconnected" for _, (_, cat) in self.vision.template_cache.items())
                if has_dc:
                    full_img, _ = self.vision.capture_screen(None)
                    dc_matches = self.vision.find_all_matches(
                        full_img, categories={"disconnected"}, capture_offset=(0, 0), threshold=0.65, max_results=1, early_exit=True
                    )
                    if dc_matches:
                        logger.warning(
                            f"[PAUSED] Connection Lost detected ({dc_matches[0].template_name}). Waiting..."
                        )
                        time.sleep(0.5)
                        continue

                # Priority 1: Scan Inventory Items (Stash & Sell)
                inv_img, box_info = self.vision.capture_screen(item_region)
                inv_offset = (box_info["offset_x"], box_info["offset_y"])

                inv_matches = self.vision.find_all_matches(
                    inv_img, categories={"stash_item"}, capture_offset=inv_offset, early_exit=True, max_results=1
                )
                if not inv_matches:
                    inv_matches = self.vision.find_all_matches(
                        inv_img, categories={"sell_item"}, capture_offset=inv_offset, early_exit=True, max_results=1
                    )

                if not inv_matches and now - last_search_status_at >= 3.0:
                    log_event("INFO", "Searching for item...")
                    last_search_status_at = now

                acted = False
                for match in inv_matches:
                    if self._paused:
                        break
                    executed = process_match(match, self.automation)
                    if executed:
                        acted = True
                        last_search_status_at = 0.0
                        needs_inventory_focus = False
                        if match.category == "stash_item":
                            logger.info("Item stored in stash.")
                        else:
                            log_event(
                                "ACTION",
                                f"Placed item for sale [{self.automation.current_sales_slots}/{config.SALES_SLOTS_CAPACITY}]",
                            )
                        break

                # Priority 1.5: Scroll Inventory if empty view
                if not acted and config.INVENTORY_SCROLL_ENABLED and item_region is not None:
                    if self._paused:
                        continue
                    if inv_scroll_depth < config.INVENTORY_SCROLL_MAX_STEPS:
                        self.automation.scroll_inventory_region(
                            item_region, direction="down", ticks=config.INVENTORY_SCROLL_TICKS, quiet=True, ensure_focus=needs_inventory_focus
                        )
                        needs_inventory_focus = False
                        inv_scroll_depth += 1
                    elif inv_scroll_depth > 0:
                        self.automation.scroll_inventory_region(
                            item_region, direction="up", ticks=config.INVENTORY_SCROLL_TICKS * inv_scroll_depth, quiet=True, ensure_focus=needs_inventory_focus
                        )
                        needs_inventory_focus = False
                        inv_scroll_depth = 0

                # Priority 1.6: Batch Confirm Sell Button
                if self.automation.current_sales_slots >= config.SALES_SLOTS_CAPACITY:
                    if self._paused:
                        continue
                    full_img, _ = self.vision.capture_screen(None)
                    sell_btns = self.vision.find_all_matches(
                        full_img, categories={"sell_button"}, capture_offset=(0, 0), max_results=1, early_exit=True
                    )
                    if sell_btns:
                        if process_match(sell_btns[0], self.automation):
                            log_event("ACTION", "Clicked Batch Confirm Sell!")
                            needs_inventory_focus = True

                # Priority 2: Chest opening checks
                if now - last_chest_check >= 1.5:
                    if self._paused:
                        continue
                    last_chest_check = now
                    has_chests = any(cat in ("standard_chest", "boss_chest", "treasure_chest") for _, (_, cat) in self.vision.template_cache.items())
                    if has_chests:
                        full_img, _ = self.vision.capture_screen(None)
                        chests = self.vision.find_all_matches(
                            full_img, categories={"standard_chest", "boss_chest", "treasure_chest"}, capture_offset=(0, 0), max_results=1, early_exit=True
                        )
                        if chests:
                            c = chests[0]
                            if process_match(c, self.automation):
                                log_event("ACTION", "Opened reward chest.")
                                needs_inventory_focus = True

                # Priority 3: Infrequent UI Safeguards (HERO/Inventory/Stash/Cube)
                if now - last_ui_tab_check > config.UI_TAB_CHECK_INTERVAL:
                    if self._paused:
                        continue
                    ready = ensure_ui_tabs_ready(self.vision, self.automation)
                    last_ui_tab_check = time.time()
                    if not ready:
                        needs_inventory_focus = True

                # Priority 3.5: Infrequent Alchemy Mode Check
                if now - last_cube_tab_check > 10.0:
                    if self._paused:
                        continue
                    ensure_alchemy_tab_selected(self.vision, self.automation)
                    last_cube_tab_check = time.time()
                    needs_inventory_focus = True

            except Exception as e:
                logger.exception(f"Unhandled exception in AutomationWorker loop: {e}")

            elapsed = time.time() - loop_start
            sleep_time = max(0.01, config.SCAN_INTERVAL - elapsed)
            if self.automation:
                self.automation.wait(sleep_time)
            else:
                time.sleep(sleep_time)

        if self.automation:
            self.automation.sanitize_modifier_keys()


# --- REGION CHOICE DIALOG ---
