"""Copy what the public GitHub repo holds into its local clone, replacing the managed folders.

  wallpaper/   the live Wallpaper Engine project (what WE loads)
  scripts/     pipeline scripts + shader sources        tools/   helpers (rigs, .tex I/O, previews)
  docs/        the handoff notes                         README.md, .gitignore, .gitattributes

Usage: python tools/export_repo.py [repo_dir]   (default E:/Dev/reptilian-ultrawide-wallpaper-engine)
Then commit and push from repo_dir.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ  # noqa: E402

REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("E:/Dev/reptilian-ultrawide-wallpaper-engine")
TREES = {"wallpaper": PROJ, "scripts": HERE / "scripts", "tools": HERE / "tools"}
DOCS = ["HANDOFF_animation.md", "HANDOFF_mandalas.md"]
ROOT_FILES = {"README.md": HERE / "repo" / "README.md",
              ".gitignore": HERE / "repo" / "gitignore",
              ".gitattributes": HERE / "repo" / "gitattributes"}


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


def tree_files(src):
    return {p.relative_to(src).as_posix(): p for p in src.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".dxs")}
    # .dxs: WE's compiled shader cache (shaders/blobsSM40), rebuilt on every machine


def main():
    REPO.mkdir(parents=True, exist_ok=True)
    for name, src in TREES.items():
        sync(tree_files(src), REPO / name)
    sync({d: HERE / d for d in DOCS}, REPO / "docs")
    for dst, src in ROOT_FILES.items():
        shutil.copy2(src, REPO / dst)
    n = sum(1 for p in REPO.rglob("*") if p.is_file() and ".git" not in p.relative_to(REPO).parts)
    mb = sum(p.stat().st_size for p in REPO.rglob("*") if p.is_file() and ".git" not in p.relative_to(REPO).parts) / 1e6
    print(f"exported {n} files, {mb:.1f} MB to {REPO}")


if __name__ == "__main__":
    main()
