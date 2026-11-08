"""Copy what the GitHub repo holds into its local clone (run from the working folder).

The repo is a complete, self-contained copy of the project: clone it on any machine and the
current pipeline runs from it (README, "Set up on a new machine"). It holds, at the same relative
paths as the working folder so every script runs unchanged in both:

  wallpaper/                                 the live Wallpaper Engine project
  scripts/, tools/                           the pipeline, scene scripts, shader sources, helpers
  docs/                                      the handoff notes
  backups/2026-11-07_before_optimize/project the optimiser's source (pre-optimisation scene,
                                             full textures, masks); arm_follow_field.py writes here
  recovered_original/                        the art layers + original masks, lossless PNG
  Choronzon_mandala_black.png, mandala_canvas.png   mandala sources (scripts/add_mandalas.py)
  rig/**/*.png|json                          the motion maps as editable PNGs + reports
  mock/*.png|py                              approved still mocks (edge smoke) + the script that drew them
  README.md, .gitignore, .gitattributes      from repo/

Usage: python tools/export_repo.py [repo_dir]   (default E:/Dev/reptilian-ultrawide-wallpaper-engine)
Then commit and push from repo_dir. Not needed when you work in the clone itself.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from we_paths import PROJ  # noqa: E402

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("E:/Dev/reptilian-ultrawide-wallpaper-engine")
SKIP = (".pyc", ".dxs")         # .dxs: WE's compiled shader cache (shaders/blobsSM40), rebuilt per machine
TREES = {"wallpaper": (PROJ, None),
         "scripts": (HERE / "scripts", None),
         "tools": (HERE / "tools", None),
         "backups/2026-11-07_before_optimize/project": (HERE / "backups" / "2026-11-07_before_optimize" / "project", None),
         "recovered_original": (HERE / "recovered_original", None),
         "rig": (HERE / "rig", (".png", ".json")),
         "mock": (HERE / "mock", (".png", ".py"))}
DOCS = ["HANDOFF_animation.md", "HANDOFF_mandalas.md"]
ROOT_FILES = {"README.md": HERE / "repo" / "README.md",
              ".gitignore": HERE / "repo" / "gitignore",
              ".gitattributes": HERE / "repo" / "gitattributes",
              "Choronzon_mandala_black.png": HERE / "Choronzon_mandala_black.png",
              "mandala_canvas.png": HERE / "mandala_canvas.png"}


def sync(src_files, dst_root):
    """Make dst_root hold exactly src_files ({relative path: source}). Files are replaced in place
    and folders are only removed once empty: Windows often holds a handle on a folder (Explorer,
    indexer), which makes rmtree of a whole tree fail halfway."""
    for rel, src in src_files.items():
        (dst_root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst_root / rel)
    if dst_root.exists():
        for f in dst_root.rglob("*"):
            if f.is_file() and f.relative_to(dst_root).as_posix() not in src_files:
                f.unlink()
        for d in sorted((p for p in dst_root.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
            if not any(d.iterdir()):
                try:
                    d.rmdir()
                except OSError:
                    pass                     # held open; git ignores empty folders anyway


def tree_files(src, only=None):
    return {p.relative_to(src).as_posix(): p for p in src.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix.lower() not in SKIP
            and p.name != "scene.pkg"                # WE's publish package, rebuilt on publish
            and (only is None or p.suffix.lower() in only)}


def main():
    if REPO.resolve() == HERE.resolve():
        sys.exit("this is the clone itself: commit here directly, nothing to export")
    REPO.mkdir(parents=True, exist_ok=True)
    for name, (src, only) in TREES.items():
        sync(tree_files(src, only), REPO / name)
    sync({d: HERE / d for d in DOCS}, REPO / "docs")
    for dst, src in ROOT_FILES.items():
        shutil.copy2(src, REPO / dst)
    files = [p for p in REPO.rglob("*") if p.is_file() and ".git" not in p.relative_to(REPO).parts]
    print(f"exported {len(files)} files, {sum(p.stat().st_size for p in files) / 1e6:.1f} MB to {REPO}")


if __name__ == "__main__":
    main()
