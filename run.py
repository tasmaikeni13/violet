from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_FILE = ROOT_DIR / "requirements.txt"
EMPIRICAL_SCRIPT = ROOT_DIR / "violet_core" / "test_theorems.py"
APP_SCRIPT = ROOT_DIR / "violet_studio" / "app.py"
DEPENDENCIES = {
    "numpy": "numpy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
}


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def missing_dependencies() -> list[str]:
    missing: list[str] = []
    for package_name, module_name in DEPENDENCIES.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)
    return missing


def install_dependencies() -> None:
    if not REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(f"requirements.txt was not found at {REQUIREMENTS_FILE}")

    print("Installing required Python packages...")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        cwd=ROOT_DIR,
    )


def ensure_dependencies() -> None:
    missing = missing_dependencies()
    if not missing:
        print("Dependencies already installed.")
        return

    print(f"Missing dependencies detected: {', '.join(missing)}")
    install_dependencies()
    still_missing = missing_dependencies()
    if still_missing:
        raise RuntimeError(f"Dependencies are still missing after install: {', '.join(still_missing)}")
    print("Dependencies installed successfully.")


def run_script(script_path: Path) -> int:
    return subprocess.call([sys.executable, str(script_path)], cwd=ROOT_DIR)


def launch_empirical_tests() -> None:
    clear_screen()
    exit_code = run_script(EMPIRICAL_SCRIPT)
    if exit_code != 0:
        raise SystemExit(exit_code)


def launch_violet_app() -> None:
    clear_screen()
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Tkinter is not available in this Python installation, so Violet Studio cannot start."
        ) from exc

    exit_code = run_script(APP_SCRIPT)
    if exit_code != 0:
        raise SystemExit(exit_code)


def prompt_choice() -> str:
    while True:
        print("VIOLET launcher")
        print("=" * 40)
        print("1. Empirical evidence tests")
        print("2. Open Violet app")
        print("3. Exit")
        choice = input("\nChoose an option [1-3]: ").strip()
        if choice in {"1", "2", "3"}:
            return choice
        clear_screen()
        print("Invalid choice. Please enter 1, 2, or 3.\n")


def main() -> None:
    try:
        ensure_dependencies()
    except Exception as exc:
        raise SystemExit(f"Dependency setup failed: {exc}") from exc

    clear_screen()
    choice = prompt_choice()

    if choice == "1":
        launch_empirical_tests()
    elif choice == "2":
        launch_violet_app()


if __name__ == "__main__":
    main()