r"""Находит корень проекта и соседние модули — поиском метки, а не счётом родителей.

Зачем. Скрипты сборки ходят наружу модуля за двумя вещами: за `tools\paths` проекта
и за верстаком `dev\morphbench`. Раньше путь считался счётом родительских папок
(`ROOT.parent.parent`), и это молча привязывало код к глубине, на которой лежит модуль.
Стоило переложить модуль на уровень глубже — и сборка искала `tools` не там, где он есть.

Правило проекта то же самое: пути выводятся, а не зашиваются. Счёт родителей — такая же
зашитая величина, как абсолютный путь, только менее заметная.

Метка корня — файл `tools\paths.py`: он есть в проекте всегда, потому что через него
выводятся все остальные пути.
"""
from __future__ import annotations

from pathlib import Path

#: Метки корня. Первая — прежняя раскладка, когда `tools\\` лежал прямо в корне проекта.
#: Вторая — нынешняя: всё версионируемое уехало в рабочую копию `wt-claude-projects\\`,
#: и модуль путей лежит в её общей части. Проверяются обе, потому что модуль обязан
#: собираться и там, где раскладка ещё прежняя.
MARKER = Path("tools") / "paths.py"
WORKTREE = Path("wt-claude-projects")
MARKER_WT = WORKTREE / "admin" / "tools" / "paths.py"


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
    dev = project_root(start) / "dev"
    here = [dev / "morphbench" / "morphbench" / "mb.py",   # модуль в своей папке внутри ветки
            dev / "morphbench" / "mb.py"]                  # прежняя раскладка, до 14.09
    here += sorted(dev.glob("*/morphbench/mb.py")) if dev.is_dir() else []
    for path in here:
        if path.is_file():
            return path
    raise SystemExit("не найден верстак: ни одного mb.py в %s" % (dev / "morphbench"))
