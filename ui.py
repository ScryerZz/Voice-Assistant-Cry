from src.core.console import configure_console_encoding
from src.ui.config_app import main as ui_main

configure_console_encoding()


if __name__ == "__main__":
    import sys

    if "--assistant" in sys.argv:
        from main import main as assistant_main

        assistant_main()
    elif "--diagnose" in sys.argv:
        from diagnose import main as diagnose_main

        raise SystemExit(diagnose_main())
    else:
        ui_main()
