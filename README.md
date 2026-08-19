# TBH-Tool v2.0 (PVandAI)

Windows Desktop Automation Utility with PyQt6 UI, **OpenCV** template matching, **MSS** high-speed screen capture, and **PyAutoGUI** input execution.

---

## 🌟 Key Features

- **Author**: **PVandAI**
- **Compact Native Windows Desktop GUI**: Built matching the StitchAI dark technical design language.
- **Item Categorization & Automation**:
  - Stash items (`templates/stash_items/`): Executes **`Ctrl + Right-Click`**.
  - Sell items (`templates/sell_items/`): Executes **`Alt + Right-Click`**.
  - Confirm Sell (`templates/sell_button.png`): Clicks **Sell** only when sales capacity is reached.
- **Quick Template Capture Tool**: Hover+Enter capture or freeze-screen snipper tool (`F3`).
- **Screen Region Measuring**: Measure `INVENTORY_REGION` and `GAME_REGION` interactively (`F2`).
- **Hotkeys (Focused Scope)**:
  - `F1`: Start / Pause
  - `F2`: Measure Region
  - `F3`: Capture Item
  - `F4`: Reload Templates
  - `ESC`: Emergency Stop

---

## 🚀 Launching the App

Run `main.py` directly:
```bash
python main.py
```
Or run via batch file: `Run_TBH_Tool.bat`

---

## ⚙️ Configuration (`config.json`)

- `STASH_MODIFIER`: Modifier key for stashing (Default: `"ctrl"`).
- `SELL_MODIFIER`: Modifier key for selling (Default: `"alt"`).
- `SALES_SLOTS_CAPACITY`: Number of slots to fill before confirming sale (Default: `9`).
- `CONFIDENCE_THRESHOLD`: Vision template matching confidence threshold (Default: `0.85`).
- `FAILSAFE`: Emergency safety stop when mouse moves to corner `(0,0)`.