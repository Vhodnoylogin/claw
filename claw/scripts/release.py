r"""Собирает выпуск семейства CLAW: проверяет годность собранного и пакует архивы.

Зачем отдельный скрипт, а не упаковка папки руками. Выпуск — это не «сжать то, что лежит
в `mods\`»: между сборкой и выпуском стоит вопрос «а то ли там лежит». Скрипт отвечает
на него до того, как архив уедет наружу:

  * версия семейства из `recipes\build.json` совпадает с `meta.ini` каждого мода;
  * рядом с модом лежит манифест `claw-build.json` той же версии, и в нём все выходы «совпал»;
  * манифест собран нетронутым деревом рецептов и тем коммитом, на котором стоит ветка.

Описание мода не сочиняется здесь и не живёт в `meta.ini`: его исходник — `release\<имя>.en.md`
и `.ru.md`. Скрипт кладёт оба файла ВНУТРЬ архива и он же печатает текст для страницы мода,
поэтому разъехаться им негде.

Сам скрипт в архив не попадает — это сборщик, а не часть мода.

Запуск из папки модуля:

    python scripts/release.py [--list] [--force] [--out <папка>] [--no-assets]

    --list        только показать, что войдёт в выпуск, ничего не паковать
    --force       паковать вопреки замечаниям проверки (для пробных сборок)
    --out         куда класть архивы; по умолчанию `dist\` внутри модуля
    --no-assets   не раскладывать набор выпуска в `assets\release\<версия>\`

Набор в `assets\release\<версия>\` — то, что версионируется через LFS: он кладётся туда
на выпуск, а не на каждую сборку, см. `docs\versioning.md`.
"""
from __future__ import annotations

import configparser
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RELEASE = ROOT / "release"
RECIPES = ROOT / "recipes"
MANIFEST = "claw-build.json"


def project_paths():
    """Пути проекта. Корень ищется меткой, а не счётом родительских папок."""
    sys.path.insert(0, str(HERE))
    from locate import project_tools                     # noqa: WPS433
    sys.path.insert(0, str(project_tools(HERE)))
    from paths import P                                  # noqa: WPS433
    return P


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def family_version() -> str:
    """Версия семейства хранится в одном месте — в журнале сборки."""
    return str(load(RECIPES / "build.json")["version"])


def mod_version(folder: Path) -> str:
    meta = folder / "meta.ini"
    if not meta.is_file():
        return ""
    cfg = configparser.ConfigParser(strict=False, interpolation=None)
    try:
        cfg.read(meta, encoding="utf-8")
        return cfg.get("General", "version", fallback="") or ""
    except Exception:                                    # noqa: BLE001
        return ""


def head_commit() -> str:
    done = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    return done.stdout.strip() if done.returncode == 0 else ""


def check(folder: Path, version: str, commit: str) -> list[str]:
    """Замечания к моду. Пустой список — мод годен к выпуску."""
    notes: list[str] = []
    if not folder.is_dir():
        return ["папки мода нет: %s" % folder]

    got = mod_version(folder)
    if got != version:
        notes.append("версия в meta.ini — %s, а у семейства %s" % (got or "нет", version))

    path = folder / MANIFEST
    if not path.is_file():
        notes.append("нет манифеста %s: мод собран не журналом или собран давно" % MANIFEST)
        return notes

    built = load(path)
    if str(built.get("version")) != version:
        notes.append("манифест собран версией %s, а выпускается %s"
                     % (built.get("version"), version))
    if built.get("recipes", {}).get("dirty"):
        notes.append("манифест собран деревом рецептов с незакоммиченными правками")
    was = str(built.get("recipes", {}).get("commit", ""))
    if commit and was and was != commit:
        notes.append("манифест собран коммитом %s, ветка стоит на %s — нужна пересборка"
                     % (was[:7], commit[:7]))
    bad = [o for o in built.get("outputs", []) if o.get("state") != "совпал"]
    for out in bad:
        notes.append("сверка не сошлась: %s/%s — %s"
                     % (out.get("mod"), out.get("file"), out.get("state")))
    return notes


def contents(folder: Path, skip: set[str]) -> list[Path]:
    return [p for p in sorted(folder.rglob("*")) if p.is_file() and p.name not in skip]


def stage(folder: Path, files: list[Path], docs: dict, spec: dict, into: Path) -> None:
    """Раскладывает содержимое мода и описание на двух языках во временную папку."""
    if into.exists():
        shutil.rmtree(into)
    into.mkdir(parents=True)
    for src in files:
        dst = into / src.relative_to(folder)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    for lang, name in docs.items():
        src = RELEASE / ("%s.%s.md" % (spec["description"], lang))
        if not src.is_file():
            raise SystemExit("нет описания: %s" % src)
        shutil.copy2(src, into / name)


def write_meta(archive: Path, spec: dict, version: str) -> Path:
    """Спутник .meta — тот же, что MO2 пишет для скачанного архива.

    modID нулевой намеренно: страницы на Nexus у мода пока нет, и выдуманный номер
    отправил бы MO2 искать обновление, которого не существует.
    """
    meta = archive.with_suffix(archive.suffix + ".meta")
    meta.write_text(
        "[General]\n"
        "gameName=SkyrimSE\n"
        "modID=0\n"
        "fileID=0\n"
        "url=\n"
        "name=%s\n"
        "modName=%s\n"
        "version=%s\n"
        "newestVersion=\n"
        "installed=false\n"
        "uninstalled=false\n"
        "paused=false\n"
        "removed=false\n" % (spec["mod"], spec["mod"], version),
        encoding="utf-8")
    return meta


def pack(seven: Path, folder: Path, archive: Path) -> None:
    if archive.exists():
        archive.unlink()
    # -mx=5 намеренно: меши уже сжаты внутри, а девятка тратит минуты ради процентов.
    done = subprocess.run([str(seven), "a", "-t7z", "-mx=5", str(archive), "*"],
                          cwd=str(folder), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise SystemExit("7-Zip отказал:\n" + (done.stdout or "")[-1500:])


def main(argv: list[str]) -> int:
    only_list = "--list" in argv
    force = "--force" in argv
    assets = "--no-assets" not in argv
    out = Path(argv[argv.index("--out") + 1]) if "--out" in argv else ROOT / "dist"

    P = project_paths()
    spec_all = load(RELEASE / "release.json")
    version = family_version()
    commit = head_commit()
    docs = spec_all["docs"]
    skip = set(spec_all.get("skip", []))

    print("семейство : %s %s" % (spec_all["family"], version))
    print("коммит    : %s" % (commit[:7] or "не определён"))

    plan: list[tuple[dict, Path, list[Path], list[str]]] = []
    for spec in spec_all["mods"]:
        folder = Path(P.mods) / spec["mod"]
        notes = check(folder, version, commit)
        files = contents(folder, skip) if folder.is_dir() else []
        size = sum(f.stat().st_size for f in files)
        print("\nмод       : %s%s" % (spec["mod"], "  [взрослый]" if spec.get("adult") else ""))
        print("файлов    : %d, %.1f МБ" % (len(files), size / 1048576.0))
        for note in notes:
            print("ЗАМЕЧАНИЕ : %s" % note)
        if not notes:
            print("проверка  : сошлось")
        plan.append((spec, folder, files, notes))

    stopped = [s["mod"] for s, _, _, n in plan if n]
    if stopped and not force:
        print("\nвыпуск не собран: есть замечания к %s." % ", ".join(stopped))
        print("Починить и пересобрать, либо --force для пробной сборки.")
        return 1
    if only_list:
        return 0

    seven = Path(str(P.seven_zip))
    if not seven.is_file():
        raise SystemExit("не найден 7-Zip: заполните ключ sevenZip в tools\\paths.json")
    out.mkdir(parents=True, exist_ok=True)

    for spec, folder, files, _ in plan:
        staged = ROOT / "work" / "release" / spec["id"]
        stage(folder, files, docs, spec, staged)
        archive = out / ("%s %s.7z" % (spec["archive"], version))
        pack(seven, staged, archive)
        write_meta(archive, spec, version)
        print("\nархив     : %s (%.1f МБ)"
              % (archive.name, archive.stat().st_size / 1048576.0))
        if assets:
            keep = ROOT / "assets" / "release" / version / spec["id"]
            if keep.exists():
                shutil.rmtree(keep)
            shutil.copytree(staged, keep)
            print("набор     : %s" % keep.relative_to(ROOT))

    print("\nТекст на страницу мода — release\\<имя>.en.md и .ru.md, они же лежат в архиве.")
    print("Набор в assets\\release\\%s коммитится вместе с меткой claw/%s." % (version, version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
