"""Where the live Wallpaper Engine project is, on any machine.

PROJ, in order:
  1. the folder in the REPTILIAN_WE_PROJECT environment variable
  2. <Steam library>/steamapps/common/wallpaper_engine/projects/myprojects/reptilian_ultrawide_5120
     in any Steam library (Steam's install path from the registry + steamapps/libraryfolders.vdf)
  3. the repo's own wallpaper/ folder

On a fresh machine, link (2) to (3) once so Wallpaper Engine loads the repo copy and the scripts
write straight into it (see README, "Set up on a new machine").
"""
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PROJECT_NAME = "reptilian_ultrawide_5120"


def steam_libraries():
    roots = []
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    for name in ("SteamPath", "InstallPath"):
                        try:
                            roots.append(Path(winreg.QueryValueEx(k, name)[0]))
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:                       # not Windows
        roots.append(Path.home() / ".steam" / "steam")
    libs = []
    for r in roots:
        vdf = r / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
        libs.append(r)
    seen, out = set(), []
    for lib in libs:
        key = str(lib).lower()
        if key not in seen:
            seen.add(key)
            out.append(lib)
    return out


def find_project():
    env = os.environ.get("REPTILIAN_WE_PROJECT")
    if env:
        return Path(env)
    for lib in steam_libraries():
        p = lib / "steamapps" / "common" / "wallpaper_engine" / "projects" / "myprojects" / PROJECT_NAME
        if p.exists():
            return p
    return HERE / "wallpaper"


PROJ = find_project()


if __name__ == "__main__":
    print("Steam libraries:", *steam_libraries(), sep="\n  ")
    print("project:", PROJ)
