"""Paths for standalone CLAW builds.

Machine paths come from the ignored build.local.json at the checkout root. Relative
paths are resolved against that file. No journal infrastructure is imported when
the configuration is present. The old project layout is supported as a fallback;
Morphbench can also be found in its sibling independent checkout.
"""
from __future__ import annotations

from pathlib import Path
import json
from types import SimpleNamespace

#: Метки корня. Первая — прежняя раскладка, когда `tools\\` лежал прямо в корне проекта.
#: Вторая — нынешняя: всё версионируемое уехало в рабочую копию `wt-claude-projects\\`,
#: и модуль путей лежит в её общей части. Проверяются обе, потому что модуль обязан
#: собираться и там, где раскладка ещё прежняя.
MARKER = Path("tools") / "paths.py"
WORKTREE = Path("wt-claude-projects")
MARKER_WT = WORKTREE / "admin" / "tools" / "paths.py"


def local_config(start: Path | str | None = None) -> dict:
    """Machine paths for the independent checkout; never load journal internals."""
    here = Path(start or __file__).resolve()
    for candidate in (here, *here.parents):
        config = candidate / "build.local.json"
        if config.is_file():
            data = json.loads(config.read_text(encoding="utf-8-sig"))
            for key in ("mods", "pynifly", "blender", "sevenZip", "morphbench"):
                if data.get(key):
                    path = Path(data[key])
                    data[key] = str(path if path.is_absolute() else (config.parent / path).resolve())
            return data
        if (candidate / ".git").exists():
            break
    return {}


def project_paths(start: Path | str | None = None):
    """Explicit local configuration, with the historical layout as a fallback."""
    cfg = local_config(start)
    if cfg:
        missing = [key for key in ("mods", "pynifly", "blender", "sevenZip") if not cfg.get(key)]
        if missing:
            raise SystemExit("build.local.json: missing " + ", ".join(missing))
        return SimpleNamespace(mods=Path(cfg["mods"]), pynifly=Path(cfg["pynifly"]),
                               blender=Path(cfg["blender"]), seven_zip=Path(cfg["sevenZip"]))
    import sys
    try:
        folder = project_tools(start)
    except SystemExit as exc:
        raise SystemExit("Create build.local.json in the CLAW checkout; see docs/rebuild.md") from exc
    sys.path.insert(0, str(folder))
    from paths import P
    return P


def project_root(start: Path | str | None = None) -> Path:
    """Ближайшая папка вверх по дереву, в которой лежит модуль путей проекта."""
    here = Path(start or __file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / MARKER).is_file() or (candidate / MARKER_WT).is_file():
            return candidate
    raise SystemExit("не найден корень проекта: вверх от %s нет ни %s, ни %s"
                     % (here, MARKER, MARKER_WT))


def project_tools(start: Path | str | None = None) -> Path:
    """Папка, которую кладут в sys.path, чтобы сделать `from paths import P`.

    В нынешней раскладке таких папок две: общая `admin\\tools` и предметная
    `<журнал проекта>\\tools`. Нужна предметная: она прокладкой подтягивает общую
    и добавляет пути сборки — `P.mods`, `P.downloads`, `P.seven_zip`, — которых
    в общей нет.
    """
    root = project_root(start)
    if (root / MARKER).is_file():
        return root / "tools"
    journals = sorted(found.parent for found in (root / WORKTREE).glob("*/tools/paths.py")
                      if found.parent.parent.name != "admin")
    if journals:
        return journals[0]
    return root / WORKTREE / "admin" / "tools"


def morphbench(start: Path | str | None = None) -> Path:
    """`mb.py` верстака: соседняя рабочая копия ветки `morphbench`.

    Ищется от корня проекта, а не от модуля: рабочие копии лежат рядом в `dev\\`,
    и их взаимное расположение задано раскладкой проекта, а не глубиной модуля.
    """
    cfg = local_config(start)
    if cfg.get("morphbench"):
        path = Path(cfg["morphbench"])
        if not path.is_file():
            raise SystemExit("build.local.json: Morphbench does not exist: %s" % path)
        return path
    here = Path(start or __file__).resolve()
    for candidate in (here, *here.parents):
        path = candidate / "morphbench" / "morphbench" / "mb.py"
        if path.is_file():
            return path
    dev = project_root(start) / "dev"
    here = [dev / "morphbench" / "morphbench" / "mb.py",   # модуль в своей папке внутри ветки
            dev / "morphbench" / "mb.py"]                  # прежняя раскладка, до 14.09
    here += sorted(dev.glob("*/morphbench/mb.py")) if dev.is_dir() else []
    for path in here:
        if path.is_file():
            return path
    raise SystemExit("не найден верстак: ни одного mb.py в %s" % (dev / "morphbench"))
