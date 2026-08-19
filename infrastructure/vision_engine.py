"""
Vision Engine: Optimized template matching, DPI scaling compensation, and category-filtered OpenCV searches.
"""

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Dict, List, Optional, Set, Tuple
import cv2
import mss
import numpy as np
import pyautogui

import config
from utils import logger


@dataclass
class MatchResult:
    template_name: str
    category: str       # stash/sell/chest/alchemy/cube/ui tab categories
    confidence: float
    center_x: int       # Logical screen coordinate X (for pyautogui)
    center_y: int       # Logical screen coordinate Y (for pyautogui)
    width: int
    height: int
    region_x: int       # Region-relative coordinate X
    region_y: int       # Region-relative coordinate Y


class VisionEngine:
    """Handles template caching, screen capture, DPI scaling, and computer vision matching."""

    def __init__(self, templates_dir: Path = config.TEMPLATES_DIR):
        self.templates_dir = templates_dir
        self.template_cache: Dict[str, Tuple[np.ndarray, str]] = {}  # name -> (img, category)
        self.sct = mss.MSS()

        # Calculate DPI Scale Factors (Windows Display Scaling compensation)
        screen_logical_w, screen_logical_h = pyautogui.size()
        primary_mon = self.sct.monitors[1]
        self.scale_x = primary_mon["width"] / float(screen_logical_w)
        self.scale_y = primary_mon["height"] / float(screen_logical_h)

        if abs(self.scale_x - 1.0) > 0.01 or abs(self.scale_y - 1.0) > 0.01:
            logger.info(f"Detected Windows DPI Display Scaling: {self.scale_x:.2f}x horizontal, {self.scale_y:.2f}x vertical.")
        else:
            logger.info("Windows Display Scaling: 1.00x (Standard 100% DPI).")

        self.load_templates()

    def load_templates(self) -> None:
        """Loads all PNG template assets with folder-first category hierarchy."""
        self.template_cache.clear()
        if not self.templates_dir.exists():
            logger.warning(f"Template directory '{self.templates_dir}' does not exist.")
            return

        png_files = list(self.templates_dir.rglob("*.png"))
        if not png_files:
            logger.warning(f"No .png template files found in '{self.templates_dir}'.")
            return

        logger.info("Loading template assets...")
        dropdown_sources: List[Tuple[str, np.ndarray]] = []

        for filepath in png_files:
            try:
                img = cv2.imread(str(filepath), cv2.IMREAD_COLOR)
                if img is None:
                    logger.error(f"Failed to read image file: {filepath}")
                    continue

                rel_path = filepath.relative_to(self.templates_dir)
                folder_parts = [p.lower() for p in rel_path.parts[:-1]]
                file_name = filepath.name.lower()

                # Folder & Name Category Resolution
                if "disconnected" in file_name or "reconnecting" in file_name or "connection_lost" in file_name:
                    category = "disconnected"
                elif "boss_chest" in file_name or any("boss" in p for p in folder_parts):
                    category = "boss_chest"
                elif "treasure_chest" in file_name or "treasure" in file_name:
                    category = "treasure_chest"
                elif "standard_chest" in file_name or "normal_chest" in file_name or any("chest" in p for p in folder_parts if "stash" not in p):
                    category = "standard_chest"
                elif "alchemy_header" in file_name or "alch_header" in file_name:
                    category = "alchemy_header"
                elif "alchemy_option" in file_name or "alch_option" in file_name or "alchemy_item" in file_name:
                    category = "alchemy_option"
                elif "hero_tab_open" in file_name:
                    category = "hero_tab_open"
                elif "hero_tab_closed" in file_name:
                    category = "hero_tab_closed"
                elif "inventory_tab" in file_name:
                    category = "inventory_tab"
                elif "formation_tab" in file_name:
                    category = "formation_tab"
                elif "stash_tab" in file_name or "stash_icon" in file_name:
                    category = "stash_tab_icon"
                elif "cube_tab" in file_name or (file_name.startswith("cube_") and "icon" in file_name):
                    category = "cube_tab_icon"
                elif "mode_arrow" in file_name or "cube_mode_arrow" in file_name:
                    category = "cube_header"
                elif "mode_header" in file_name:
                    # Collapsed Cube mode headers — Alchemy means already correct; others need switching
                    if "alchemy" in file_name:
                        category = "alchemy_header"
                    else:
                        category = "cube_header"
                elif "synthesis_header" in file_name or "syn_header" in file_name:
                    # Legacy name: treat as non-Alchemy header that should be switched away from
                    category = "cube_header"
                elif "synthesis_option" in file_name or "syn_option" in file_name or "synthesis_item" in file_name:
                    category = "alchemy_option"  # legacy files redirected; prefer alchemy_option.png
                elif "dropdown" in file_name or "cube_dropdown" in file_name:
                    # Full open-dropdown screenshot — used as crop source, not matched directly
                    category = "cube_dropdown"
                elif "cube_header" in file_name or "crafting_header" in file_name or any("cube" in p for p in folder_parts):
                    category = "cube_header"
                elif any(k in p for p in folder_parts for k in ["sell_items", "sells", "sell", "sales"]):
                    category = "sell_item"
                elif any(k in p for p in folder_parts for k in ["stash_items", "stash", "storage"]):
                    category = "stash_item"
                elif "sell_button" in file_name or "btn_sell" in file_name or "button_sell" in file_name:
                    category = "sell_button"
                elif any(k in file_name for k in ["sell", "sale"]):
                    category = "sell_item"
                elif any(k in file_name for k in ["stash", "storage"]):
                    category = "stash_item"
                else:
                    category = "sell_item"
                    logger.warning(f"Template '{filepath.name}' folder path uncategorized. Defaulting to 'sell_item'.")

                # Keep full dropdown out of the match cache (too large / slow); crop useful regions instead
                if category == "cube_dropdown":
                    dropdown_sources.append((filepath.stem, img))
                    continue

                self.template_cache[filepath.name] = (img, category)
            except Exception as e:
                logger.exception(f"Exception loading template {filepath}: {e}")

        # Derive compact Alchemy / header templates from dropdown screenshots when missing
        self._extract_cube_crops_from_dropdowns(dropdown_sources)

        logger.info(f"Successfully cached {len(self.template_cache)} templates in memory.")

    def _extract_cube_crops_from_dropdowns(self, dropdown_sources: List[Tuple[str, np.ndarray]]) -> None:
        """
        From a full Cube mode-dropdown screenshot, auto-crop:
          - header bar  -> cube_header (click to open when that mode is active)
          - Alchemy row -> alchemy_option (click to select Alchemy for selling)
        Skips alchemy crop if the user already provided an explicit alchemy_option template.
        Header crops are always added as extra cube_header templates (covers Crafting, etc.).
        """
        if not dropdown_sources:
            return

        existing_categories = {cat for _, cat in self.template_cache.values()}
        need_alchemy = "alchemy_option" not in existing_categories

        for stem, img in dropdown_sources:
            h, w = img.shape[:2]
            # Layout ratios from dropdown_cube.png (302x193): header [0,34), Alchemy [69,102)
            y_header_end = max(1, int(round(h * 34 / 302)))
            y_alchemy_start = min(h - 1, int(round(h * 69 / 302)))
            y_alchemy_end = min(h, int(round(h * 102 / 302)))
            # Exclude trailing open/close arrow so header matches both expanded & collapsed states
            x_header_end = max(1, int(round(w * 0.82)))

            header_key = f"{stem}__header.png"
            if header_key not in self.template_cache:
                header_crop = img[0:y_header_end, 0:x_header_end].copy()
                if header_crop.size > 0:
                    self.template_cache[header_key] = (header_crop, "cube_header")

            if need_alchemy and y_alchemy_end > y_alchemy_start:
                alchemy_crop = img[y_alchemy_start:y_alchemy_end, :].copy()
                if alchemy_crop.size > 0:
                    self.template_cache[f"{stem}__alchemy_option.png"] = (alchemy_crop, "alchemy_option")
                    need_alchemy = False

    def capture_screen(self, region: Optional[Dict[str, int]] = None) -> Tuple[np.ndarray, Dict[str, int]]:
        """
        Captures screen region using high-performance MSS with silent retry & boundary clamping.
        """
        primary_mon = self.sct.monitors[1]
        mon_w = primary_mon["width"]
        mon_h = primary_mon["height"]
        mon_left = primary_mon["left"]
        mon_top = primary_mon["top"]

        if region is None:
            capture_box = {
                "top": mon_top,
                "left": mon_left,
                "width": mon_w,
                "height": mon_h,
            }
            offset_logical_x = 0
            offset_logical_y = 0
        else:
            phys_left = max(0, min(mon_w - 10, int(region["left"] * self.scale_x)))
            phys_top = max(0, min(mon_h - 10, int(region["top"] * self.scale_y)))
            phys_width = max(10, min(mon_w - phys_left, int(region["width"] * self.scale_x)))
            phys_height = max(10, min(mon_h - phys_top, int(region["height"] * self.scale_y)))

            capture_box = {
                "top": mon_top + phys_top,
                "left": mon_left + phys_left,
                "width": phys_width,
                "height": phys_height,
            }
            offset_logical_x = region["left"]
            offset_logical_y = region["top"]

        try:
            sct_img = self.sct.grab(capture_box)
        except Exception:
            time.sleep(0.02)
            try:
                self.sct = mss.MSS()
                sct_img = self.sct.grab(capture_box)
            except Exception as e2:
                logger.error(f"Screen capture retry failed: {e2}")
                raise

        img_bgr = np.array(sct_img, dtype=np.uint8)[:, :, :3]
        
        box_info = {
            "offset_x": offset_logical_x,
            "offset_y": offset_logical_y,
            "width": capture_box["width"],
            "height": capture_box["height"],
        }
        return img_bgr, box_info

    def find_all_occurrences(
        self,
        screen_img: np.ndarray,
        template_name: str,
        capture_offset: Tuple[int, int] = (0, 0),
        threshold: float = config.CONFIDENCE_THRESHOLD,
        max_results: Optional[int] = None,
    ) -> List[MatchResult]:
        """
        Finds multiple non-overlapping occurrences of a template in screen_img.
        Converts physical pixel offsets back to logical PyAutoGUI coordinates.
        When max_results == 1, uses minMaxLoc (much faster than full NMS scan).
        """
        if template_name not in self.template_cache:
            return []

        template, category = self.template_cache[template_name]
        th, tw = template.shape[:2]
        sh, sw = screen_img.shape[:2]

        if sh < th or sw < tw:
            return []

        match_matrix = cv2.matchTemplate(screen_img, template, cv2.TM_CCOEFF_NORMED)

        def _to_match(x: int, y: int, score: float) -> MatchResult:
            phys_center_x = x + tw // 2
            phys_center_y = y + th // 2
            return MatchResult(
                template_name=template_name,
                category=category,
                confidence=float(score),
                center_x=int(phys_center_x / self.scale_x) + capture_offset[0],
                center_y=int(phys_center_y / self.scale_y) + capture_offset[1],
                width=tw,
                height=th,
                region_x=x,
                region_y=y,
            )

        # Fast path: only need the single best peak
        if max_results == 1:
            _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(match_matrix)
            if max_val >= threshold:
                return [_to_match(max_loc[0], max_loc[1], max_val)]
            return []

        locs = np.where(match_matrix >= threshold)
        matches: List[MatchResult] = []
        visited_mask = np.zeros((sh, sw), dtype=bool)

        coords = list(zip(locs[0], locs[1]))  # (row y, col x) in physical pixels
        coords.sort(key=lambda pt: match_matrix[pt[0], pt[1]], reverse=True)

        for y, x in coords:
            if visited_mask[y, x]:
                continue

            matches.append(_to_match(x, y, match_matrix[y, x]))

            if max_results is not None and len(matches) >= max_results:
                break

            visited_mask[max(0, y - th // 2):min(sh, y + th // 2), max(0, x - tw // 2):min(sw, x + tw // 2)] = True

        return matches

    def find_all_matches(
        self,
        screen_img: np.ndarray,
        categories: Optional[Set[str]] = None,
        capture_offset: Tuple[int, int] = (0, 0),
        threshold: float = config.CONFIDENCE_THRESHOLD,
        max_results: Optional[int] = None,
        early_exit: bool = False,
    ) -> List[MatchResult]:
        """
        Scans screen image against cached templates filtered by categories.
        Passing specific categories (e.g. {'stash_item', 'sell_item'}) makes matching 50x FASTER!
        early_exit: stop after the first template that yields a match (fast inventory path).
        max_results: cap total returned matches; uses fast minMaxLoc when == 1 per template.
        """
        results: List[MatchResult] = []
        per_template_max = 1 if (max_results == 1 or early_exit) else None

        for name, (_, category) in self.template_cache.items():
            if categories is not None and category not in categories:
                continue

            occurrences = self.find_all_occurrences(
                screen_img, name, capture_offset, threshold, max_results=per_template_max
            )
            if not occurrences:
                continue

            results.extend(occurrences)

            if early_exit:
                break
            if max_results is not None and len(results) >= max_results:
                # Keep the best so far, then stop scanning more templates
                results.sort(key=lambda m: m.confidence, reverse=True)
                return results[:max_results]

        results.sort(key=lambda m: m.confidence, reverse=True)
        if max_results is not None:
            return results[:max_results]
        return results

    def close(self) -> None:
        """Closes MSS capture instance."""
        self.sct.close()
