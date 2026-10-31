"""Build game plugins from versioned Spriggit YAML into ignored target/.

Released record sources: src/main/resources/plugins/<name>/.
Reusable test sources: src/test/resources/plugins/<name>/.
Generated ESPs: target/plugins/released/ and target/test-assets/plugins/.
No compiled ESP is an authoring input or tracked source.

python build.py plugins [name ...]
python src/main/python/build-tools/plugin.py check [name ...]

The default compiler is the external Spriggit CLI on PATH, or the explicit
spriggit path in ignored build.local.json. An explicitly supplied legacy .sh
wrapper remains supported. A text roundtrip checks actual records rather than
assuming that rewritten plugin header bytes must match. This tool never installs.
"""
import filecmp
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
from locate import local_config                        # noqa: E402
_CONFIG = local_config(HERE)

TREES = (
    ("выпуск", ROOT / 'src/main/resources/plugins', ROOT / 'target/plugins/released'),
    ("проверка", ROOT / 'src/test/resources/plugins', ROOT / 'target/test-assets/plugins'),
)
WRAPPER = Path(_CONFIG.get('spriggit') or shutil.which('spriggit') or 'spriggit')
if not WRAPPER.is_absolute():
    WRAPPER = (ROOT/WRAPPER).resolve()

# Раскладка Spriggit: пакет задаёт формат текста, выпуск - набор полей записи.
# Плагины собраны под SkyrimSE даже для VR: формат записей у них общий, а флаг ESL
# читает мод Skyrim VR ESL Support.
PACKAGE = "Spriggit.Yaml"
RELEASE = "SkyrimSE"
VERSION = "0.41.0"


def git_bash():
    """Путь к bash из комплекта Git.

    Просто `bash` брать нельзя: в Windows на PATH первым стоит `System32\\bash.exe` -
    точка входа в WSL, и без установленного дистрибутива она отвечает отказом,
    который выглядит как отказ Spriggit. Поэтому bash берётся оттуда же, откуда git.
    """
    git = shutil.which("git")
    if git:
        candidate = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("bash")
    if found and "system32" not in found.lower():
        return found
    raise SystemExit("не найден bash из комплекта Git")


class Spriggit:
    """Обёртка над обёрткой: Toolkit уже чинит длинные пути, здесь - только доводы."""

    def __init__(self, wrapper):
        if not wrapper.is_file():
            raise SystemExit('Spriggit CLI not found; configure spriggit in build.local.json or PATH: %s' % wrapper)
        self.wrapper = wrapper
        self.bash = git_bash() if wrapper.suffix.lower() == '.sh' else None
        self.command_prefix = [self.bash, str(wrapper)] if self.bash else [str(wrapper)]

    def _run(self, *args):
        cmd = self.command_prefix + [str(a) for a in args]
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if done.returncode != 0:
            # Spriggit пишет и в поток ошибок, и в обычный: показывать оба, иначе
            # причина отказа теряется и остаётся голый код возврата.
            sys.stderr.write((done.stderr or "") + (done.stdout or ""))
            raise SystemExit("spriggit вернул %d" % done.returncode)

    def dump(self, esp, folder):
        self._run("serialize", "--InputPath", esp, "--OutputPath", folder,
                  "--GameRelease", RELEASE, "--PackageName", PACKAGE,
                  "--PackageVersion", VERSION)

    def build(self, folder, esp):
        self._run("deserialize", "--InputPath", folder, "--OutputPath", esp)


class Plugin:
    """Плагин - это пара «папка текста» и «файл .esp», а не одно из двух."""

    def __init__(self, tree, name, sources, built):
        self.tree = tree
        self.name = name
        self.source = sources / name
        self.esp = built / ("%s.esp" % name)

    def __str__(self):
        return "%-28s [%s]" % (self.name, self.tree)


def collect(argv):
    """Плагины обоих деревьев, заданные доводом или все.

    Плагин опознаётся по ЛЮБОЙ из двух половин: по папке текста или по файлу .esp.
    Искать только по тексту нельзя - тогда `dump` не нашёл бы плагин, у которого
    текста ещё нет, а это ровно тот случай, ради которого `dump` и нужен.
    """
    found = []
    for tree, sources, built in TREES:
        names = set()
        if sources.is_dir():
            names.update(p.name for p in sources.iterdir() if p.is_dir())
        if built.is_dir():
            names.update(p.stem for p in built.glob("*.esp"))
        for name in sorted(names):
            found.append(Plugin(tree, name, sources, built))
    if argv:
        chosen = [p for p in found if p.name in argv]
        missing = set(argv) - {p.name for p in chosen}
        if missing:
            raise SystemExit("нет таких плагинов: %s" % ", ".join(sorted(missing)))
        return chosen
    if not found:
        raise SystemExit("не найдено ни одного исходника плагина")
    return found


def differs(left, right):
    """Различия двух деревьев текста - списком путей, а не первым попавшимся."""
    out = []
    stack = [("", filecmp.dircmp(str(left), str(right)))]
    while stack:
        prefix, node = stack.pop()
        for name in node.left_only:
            out.append("только в исходнике: %s%s" % (prefix, name))
        for name in node.right_only:
            out.append("только в собранном: %s%s" % (prefix, name))
        # Compare actual text, including files with identical size/mtime. Windows
        # CRLF serialization is not a changed record; different values still fail.
        for name in node.common_files:
            left_text = Path(node.left, name).read_text(encoding='utf-8-sig')
            right_text = Path(node.right, name).read_text(encoding='utf-8-sig')
            same = (json.loads(left_text) == json.loads(right_text) if name == 'spriggit-meta.json'
                    else left_text == right_text)
            if not same:
                out.append("различается: %s%s" % (prefix, name))
        for name, sub in node.subdirs.items():
            stack.append(("%s%s/" % (prefix, name), sub))
    return out


def cmd_dump(sp, plugin):
    if not plugin.esp.is_file():
        raise SystemExit("нет плагина: %s" % plugin.esp)
    if plugin.source.exists():
        shutil.rmtree(plugin.source)
    sp.dump(plugin.esp, plugin.source)
    print("   %s .esp -> текст (%d файлов)" % (plugin, len(list(plugin.source.rglob("*")))))
    return True


def cmd_build(sp, plugin):
    plugin.esp.parent.mkdir(parents=True, exist_ok=True)
    sp.build(plugin.source, plugin.esp)
    print("   %s текст -> .esp (%d байт)" % (plugin, plugin.esp.stat().st_size))
    return True


def cmd_check(sp, plugin):
    """Собрать во временное, разложить обратно и сверить текст с текстом."""
    scratch = ROOT/'target/spriggit-check'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as tmp:
        tmp = Path(tmp)
        esp = tmp / ("%s.esp" % plugin.name)
        sp.build(plugin.source, esp)
        again = tmp / "again"
        sp.dump(esp, again)
        bad = differs(plugin.source, again)
    if bad:
        print("   %s РАЗОШЁЛСЯ:" % plugin)
        for line in bad:
            print("      %s" % line)
        return False
    mark = "" if plugin.esp.is_file() else "   (хранимого .esp нет!)"
    print("   %s текст сходится%s" % (plugin, mark))
    return plugin.esp.is_file()


CMDS = {"dump": cmd_dump, "build": cmd_build, "check": cmd_check}


def main(argv):
    if not argv or argv[0] not in CMDS:
        raise SystemExit(__doc__)
    action, rest = CMDS[argv[0]], argv[1:]
    sp = Spriggit(WRAPPER)
    print("%s:" % argv[0])
    ok = all([action(sp, plugin) for plugin in collect(rest)])
    print("итог: %s" % ("сошлось" if ok else "ЕСТЬ РАСХОЖДЕНИЯ"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main(sys.argv[1:]))
