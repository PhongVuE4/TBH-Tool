"""Automation match dispatch and UI-maintenance coordination."""
import time
import pyautogui
import config
from automation import AutomationEngine
from utils import logger
from vision import MatchResult, VisionEngine

def process_match(match: MatchResult, automation: AutomationEngine) -> bool:
    """Dispatches match result to appropriate automation action based on item/chest/UI category."""
    if match.category == "stash_item":
        return automation.execute_stash_item(match)
    elif match.category == "sell_item":
        return automation.execute_sell_item(match)
    elif match.category == "sell_button":
        return automation.execute_confirm_sell(match)
    elif match.category == "standard_chest":
        return automation.execute_open_standard_chest(match)
    elif match.category == "boss_chest":
        return automation.execute_open_boss_chest(match)
    elif match.category == "treasure_chest":
        return automation.execute_open_treasure_chest(match)
    elif match.category in ("alchemy_header", "alchemy_option", "cube_header"):
        return automation.execute_select_cube_mode(match)
    return False


def _alchemy_target_from_header(header: MatchResult) -> MatchResult:
    """
    Compute Alchemy row click position from a Cube mode header.
    Layout (from dropdown_cube.png): Alchemy is the 2nd list item under the header.
    """
    header_top = header.center_y - header.height // 2
    # Alchemy row center is ~2.52× header height below the header top edge
    alchemy_y = header_top + int(round(header.height * 2.52))
    alchemy_x = header.center_x
    return MatchResult(
        template_name="alchemy_option_relative",
        category="alchemy_option",
        confidence=1.0,
        center_x=alchemy_x,
        center_y=alchemy_y,
        width=header.width,
        height=max(28, int(round(header.height * 0.85))),
        region_x=0,
        region_y=0,
    )


def ensure_alchemy_tab_selected(vision: VisionEngine, automation: AutomationEngine) -> bool:
    """
    Checks the Cube panel dropdown/tab state using high-speed category filtering.
    Ensures 'Alchemy' mode is selected (required for selling items).
    If already on Alchemy, returns True. Otherwise opens the mode list and selects Alchemy.
    """
    if automation.is_interrupted() or not config.CHECK_SYNTHESIS_TAB:
        return True

    has_cube_templates = any(
        cat in ("alchemy_header", "alchemy_option", "cube_header", "cube_dropdown")
        for _, (_, cat) in vision.template_cache.items()
    )
    if not has_cube_templates:
        return True

    screen_img, _ = vision.capture_screen(None)
    cube_matches = vision.find_all_matches(
        screen_img,
        categories={"alchemy_header", "alchemy_option", "cube_header"},
        capture_offset=(0, 0),
        max_results=8,
    )

    alchemy_header_matches = [m for m in cube_matches if m.category == "alchemy_header"]
    if alchemy_header_matches:
        return True

    alchemy_option_matches = [m for m in cube_matches if m.category == "alchemy_option"]
    if alchemy_option_matches:
        logger.info("[Cube Window] 'Alchemy' option visible in dropdown. Selecting it now...")
        return automation.execute_select_cube_mode(alchemy_option_matches[0])

    cube_header_matches = [m for m in cube_matches if m.category == "cube_header"]
    if not cube_header_matches:
        return True

    header = cube_header_matches[0]
    logger.info("[Cube Window] Non-Alchemy mode active. Opening Cube mode dropdown...")
    if not automation.execute_select_cube_mode(header) or not automation.wait(0.65):
        return False

    # Move cursor aside so hover-highlight does not distort the Alchemy row
    try:
        if automation.is_interrupted():
            return False
        pyautogui.moveTo(max(0, header.center_x - 120), header.center_y, duration=0.08)
        if not automation.wait(0.12):
            return False
    except Exception:
        pass

    alch_options = []
    soft_threshold = max(0.70, config.CONFIDENCE_THRESHOLD - 0.12)
    for _ in range(3):
        if automation.is_interrupted():
            return False
        screen_img2, _ = vision.capture_screen(None)
        alch_options = vision.find_all_matches(
            screen_img2,
            categories={"alchemy_option"},
            capture_offset=(0, 0),
            threshold=soft_threshold,
            max_results=1,
        )
        if alch_options:
            break
        if not automation.wait(0.25):
            return False

    if alch_options:
        logger.info("[Cube Window] 'Alchemy' option detected after opening dropdown. Selecting...")
        return automation.execute_select_cube_mode(alch_options[0])

    # Fallback: click Alchemy by layout offset under the mode header (2nd list item)
    relative = _alchemy_target_from_header(header)
    logger.info(
        f"[Cube Window] Alchemy template miss — clicking relative position "
        f"({relative.center_x}, {relative.center_y}) under '{header.template_name}'."
    )
    return automation.execute_select_cube_mode(relative)


def ensure_ui_tabs_ready(vision: VisionEngine, automation: AutomationEngine) -> bool:
    """
    Safeguard: HERO open/closed, Inventory (not Formation), STASH + CUBE panels.
    """
    if automation.is_interrupted() or not config.CHECK_UI_TABS:
        return True

    ui_cats = {
        "hero_tab_open", "hero_tab_closed", "inventory_tab", "formation_tab",
        "stash_tab_icon", "cube_tab_icon",
    }
    if not any(cat in ui_cats for _, (_, cat) in vision.template_cache.items()):
        return True

    full_img, _ = vision.capture_screen(None)
    soft_hero = max(0.75, config.CONFIDENCE_THRESHOLD - 0.08)
    strict = config.CONFIDENCE_THRESHOLD

    def _best(matches, cat: str):
        found = [m for m in matches if m.category == cat]
        return found[0] if found else None

    def _conf(m):
        return m.confidence if m is not None else -1.0

    def _find_icons(img, threshold: float):
        return vision.find_all_matches(
            img,
            categories={"stash_tab_icon", "cube_tab_icon", "inventory_tab", "formation_tab"},
            capture_offset=(0, 0),
            threshold=threshold,
            max_results=8,
        )

    def _open_stash_and_cube(stash_m, cube_m) -> bool:
        """Click STASH then CUBE icons. Returns True if any click was attempted."""
        acted = False
        if stash_m is not None:
            if automation.is_interrupted():
                return acted
            logger.info("[UI Safeguard] Opening STASH panel...")
            acted = automation.execute_ui_click(stash_m, "OPEN STASH TAB")
            if not automation.wait(0.45):
                return acted
        else:
            logger.info("[UI Safeguard] STASH icon not found — cannot open STASH panel.")
        if cube_m is not None:
            if automation.is_interrupted():
                return acted
            logger.info("[UI Safeguard] Opening CUBE panel...")
            acted = automation.execute_ui_click(cube_m, "OPEN CUBE TAB") or acted
            if not automation.wait(0.45):
                return acted
        else:
            logger.info("[UI Safeguard] CUBE icon not found — cannot open CUBE panel.")
        return acted

    def _cube_panel_open(img) -> bool:
        """Fast check: Alchemy header only (avoids scanning every mode_header on full HD)."""
        hits = vision.find_all_matches(
            img,
            categories={"alchemy_header"},
            capture_offset=(0, 0),
            threshold=strict,
            max_results=1,
            early_exit=True,
        )
        if hits:
            return True
        hits = vision.find_all_matches(
            img,
            categories={"cube_header"},
            capture_offset=(0, 0),
            threshold=strict,
            max_results=1,
            early_exit=True,
        )
        return bool(hits)

    # --- HERO HUD (full screen) ---
    hero_matches = vision.find_all_matches(
        full_img,
        categories={"hero_tab_open", "hero_tab_closed"},
        capture_offset=(0, 0),
        threshold=soft_hero,
        max_results=4,
    )
    hero_open = _best(hero_matches, "hero_tab_open")
    hero_closed = _best(hero_matches, "hero_tab_closed")
    if hero_open is not None and hero_closed is not None:
        if _conf(hero_closed) > _conf(hero_open) + 0.03:
            hero_open = None
        else:
            hero_closed = None

    if hero_closed is not None and hero_open is None:
        logger.info("[UI Safeguard] HERO tab CLOSED — opening...")
        if not automation.execute_ui_click(hero_closed, "OPEN HERO TAB") or not automation.wait(1.0):
            return False

        stash2 = cube2 = inv2 = form2 = None
        for attempt in range(4):
            if automation.is_interrupted():
                return False
            screen2, _ = vision.capture_screen(None)
            icons = _find_icons(screen2, soft_hero)
            stash2 = _best(icons, "stash_tab_icon")
            cube2 = _best(icons, "cube_tab_icon")
            inv2 = _best(icons, "inventory_tab")
            form2 = _best(icons, "formation_tab")
            if stash2 is not None or cube2 is not None:
                break
            if not automation.wait(0.35):
                return False

        if inv2 is None and form2 is not None:
            if automation.is_interrupted():
                return False
            synthetic = MatchResult(
                template_name="inventory_tab_relative",
                category="inventory_tab",
                confidence=form2.confidence,
                center_x=form2.center_x - max(50, form2.width),
                center_y=form2.center_y,
                width=form2.width,
                height=form2.height,
                region_x=0,
                region_y=0,
            )
            logger.info("[UI Safeguard] Inventory not active after HERO open — switching...")
            if not automation.execute_ui_click(synthetic, "SWITCH TO INVENTORY") or not automation.wait(0.35):
                return False

        _open_stash_and_cube(stash2, cube2)
        return False

    panel_matches = _find_icons(full_img, strict)
    if _best(panel_matches, "stash_tab_icon") is None or _best(panel_matches, "cube_tab_icon") is None:
        soft_icons = _find_icons(full_img, soft_hero)
        panel_matches = list(panel_matches) + [
            m for m in soft_icons
            if m.category in ("stash_tab_icon", "cube_tab_icon")
            and _best(panel_matches, m.category) is None
        ]

    inventory = _best(panel_matches, "inventory_tab")
    formation = _best(panel_matches, "formation_tab")
    stash_icon = _best(panel_matches, "stash_tab_icon")
    cube_icon = _best(panel_matches, "cube_tab_icon")

    if formation is None:
        formation = _best(_find_icons(full_img, soft_hero), "formation_tab")

    hero_ui_visible = hero_open is not None or stash_icon is not None or cube_icon is not None

    if inventory is not None:
        pass
    elif hero_ui_visible or hero_open is not None:
        click_target = None
        if formation is not None:
            click_target = MatchResult(
                template_name="inventory_tab_relative",
                category="inventory_tab",
                confidence=formation.confidence,
                center_x=formation.center_x - max(50, formation.width),
                center_y=formation.center_y,
                width=formation.width,
                height=formation.height,
                region_x=0,
                region_y=0,
            )
        else:
            soft_inv = _best(_find_icons(full_img, soft_hero), "inventory_tab")
            if soft_inv is not None:
                click_target = soft_inv
        if click_target is not None:
            logger.info("[UI Safeguard] Inventory not selected — switching from Formation...")
            if not automation.execute_ui_click(click_target, "SWITCH TO INVENTORY") or not automation.wait(0.4):
                return False
            return False

    if hero_open is not None or hero_ui_visible:
        if not _cube_panel_open(full_img):
            if stash_icon is None or cube_icon is None:
                for _ in range(3):
                    if automation.is_interrupted():
                        return False
                    img3, _ = vision.capture_screen(None)
                    icons3 = _find_icons(img3, soft_hero)
                    if stash_icon is None:
                        stash_icon = _best(icons3, "stash_tab_icon")
                    if cube_icon is None:
                        cube_icon = _best(icons3, "cube_tab_icon")
                    if stash_icon is not None and cube_icon is not None:
                        break
                    if not automation.wait(0.3):
                        return False
            if stash_icon is not None or cube_icon is not None:
                _open_stash_and_cube(stash_icon, cube_icon)
                return False

    return True

