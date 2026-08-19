"""TBH-Tool application bootstrap and backwards-compatible public API."""
from app.automation_coordinator import ensure_alchemy_tab_selected, ensure_ui_tabs_ready, process_match
from app.cli import display_menu, main, parse_arguments, run_live_loop

__all__ = [
    "display_menu", "ensure_alchemy_tab_selected", "ensure_ui_tabs_ready",
    "main", "parse_arguments", "process_match", "run_live_loop",
]

if __name__ == "__main__":
    main()
