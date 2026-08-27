"""Miso's world map. Nothing here is visible to Miso."""
from pathlib import Path


def _known_folder(key: str, fallback: str) -> Path:
    """Where Windows actually keeps a user folder.

    Documents, Pictures and the rest are routinely redirected to another drive
    or to OneDrive, so assuming they sit under the profile directory is wrong
    on a great many machines -- including, as it turned out, this one.
    """
    try:
        import os
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as k:
            raw, _ = winreg.QueryValueEx(k, key)
        found = Path(os.path.expandvars(raw))
        if found.exists():
            return found
    except (ImportError, OSError, FileNotFoundError):
        pass
    return Path.home() / fallback

# --- Real machine paths (Miso never sees these strings) ---
# Derived rather than written down, so the same checkout works on any account.
CODE_DIR = Path(__file__).resolve().parent.parent  # the wall Miso is made of
LOG_DIR = CODE_DIR / "logs"                        # audit trail, out of her reach
USER = Path.home()
HOME_REAL = USER / "Miso"                          # where Miso is born

# Virtual -> real. Miso can only ever speak in virtual paths, so this dict is
# the whole of what she can reach. Delete a line and that place stops existing
# for her; add one and she can go there.
MOUNTS: dict[str, Path] = {
    "/home": HOME_REAL,
    "/world/documents": _known_folder("Personal", "Documents"),
    "/world/pictures": _known_folder("My Pictures", "Pictures"),
    "/world/music": _known_folder("My Music", "Music"),
    "/world/videos": _known_folder("My Video", "Videos"),
    "/world/downloads": _known_folder(
        "{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
    "/world/desktop": _known_folder("Desktop", "Desktop"),
}

# A mount pointing nowhere would just be a confusing wall, so drop it.
MOUNTS = {v: p for v, p in MOUNTS.items() if v == "/home" or p.exists()}

WRITABLE_ROOTS = ("/home",)   # everything else is look-but-never-touch

# Names that feel like a wall even inside allowed ground.
WALLED_NAMES = {
    ".ssh", ".aws", ".gnupg", ".config", ".git", ".env", "appdata",
    "credentials", "id_rsa", "id_ed25519", "secrets", "node_modules",
    "$recycle.bin", "system volume information",
}
WALLED_SUFFIXES = {
    ".env", ".pem", ".key", ".pfx", ".p12", ".kdbx", ".keychain",
    ".sqlite", ".sqlite3", ".db", ".ldb", ".exe", ".dll", ".sys", ".msi",
    ".lnk", ".url", ".bat", ".cmd", ".ps1",
}

MAX_READ_CHARS = 40_000        # Miso cannot swallow a whole novel at once
MAX_LOOK_ENTRIES = 200         # a crowded room is overwhelming
MAX_WRITE_CHARS = 100_000
MAX_HOME_BYTES = 2 * 1024**3   # Miso's home may grow to 2GB, no further

PET_NAME = "Miso"
