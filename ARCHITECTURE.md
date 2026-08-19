# TBH-Tool Architecture

## Dependency direction

```text
main.py / gui.py (compatibility facades)
        │
        ├── app/                application lifecycle, CLI, worker, coordinator
        ├── ui/                 PyQt views, dialogs, overlays, visual helpers
        ├── core/               reusable automation, capture, region services
        ├── infrastructure/     vision, Windows hotkeys, logging adapters
        └── config.py           stable configuration boundary and persistence API
```

The presentation layer invokes application services. Application services use
the core and infrastructure layers. The core layer has no PyQt dependency;
PyQt-specific threading remains in `app.automation_worker`.

## Module ownership

| Area | Implementation | Stable legacy import |
| --- | --- | --- |
| GUI bootstrap | `ui.application` | `gui.run_gui_app` |
| Main window | `ui.main_window` | `gui.TBHToolMainWindow` |
| Dialogs | `ui.dialogs` | `gui.*Dialog` |
| Overlays | `ui.overlays` | `gui.*Overlay` |
| Automation worker | `app.automation_worker` | `gui.AutomationWorker` |
| Automation orchestration | `app.automation_coordinator` | `main.process_match`, `main.ensure_*` |
| CLI lifecycle | `app.cli` | `main.*` |
| Input engine | `core.automation_engine` | `automation.*` |
| Capture and regions | `core.template_capture`, `core.regions` | `capture.*`, `get_region.*` |
| Vision | `infrastructure.vision_engine` | `vision.*` |
| Windows hotkeys | `infrastructure.hotkey_manager` | `hotkeys.*` |
| Logging | `infrastructure.logging_utils` | `utils.*` |

## Compatibility policy

Existing entry points, configuration keys, template paths, hotkey behavior,
logging calls, and the PyInstaller-facing root modules remain unchanged. New
code should import from the owning module above; root modules exist to avoid
breaking existing integrations while the application evolves.
