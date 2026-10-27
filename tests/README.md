# Проверочное: то, что в выпуск не идёт никогда

Здесь живут моды и плагины, собранные **исключительно ради проверки**. Они не часть
семейства CLAW, не выкладываются и удаляются после прогона без сожалений. Отсюда и
раскладка: своё поддерево, а не полка рядом с выпускаемым.

    plugins\<имя>\            исходник проверочного плагина: дерево .yaml от Spriggit
    assets\plugins\*.esp      его продукт, в репозитории через Git LFS
    scripts\papyrus\*.psc     скрипты, которые нужны только проверочным плагинам

Имя каждого начинается с `test_` — **приставкой, а не суффиксом**: список модов в MO2
отсортирован по имени, и приставка собирает всё проверочное в одно место, тогда как суффикс
разбросал бы его по всему списку. Приставку получает и папка мода, и его плагин.

Собираются они тем же ключом, что и выпускаемые, — `scripts\plugin.py` знает оба дерева:

    python scripts/plugin.py check                 оба дерева
    python scripts/plugin.py build "test_CLAW - Companion"

## `test_CLAW - Companion`

**Зачем.** В игре нет ни одной вервольфицы: все шестнадцать ванильных особей мужского пола.
А тела CLAW два, и женское собрано отдельно — грудью и сужением талии. Проверить его
не на ком, и этот мод создаёт того, на ком можно.

Он даёт двух неписей и заклинание:

| запись | что это |
|---|---|
| `CLAWCompanionUlva` | нордка-последовательница; внешность, раса и голос унаследованы шаблоном от `HousecarlWhiterun`, поэтому лицо генерировать не надо и серого лица не будет |
| `CLAWCompanionUlvaBeast` | та же героиня на расе `WerewolfBeastRace`, женского пола — **единственная вервольфица в сборке** |
| `CLAWBeastFormSpell` + `CLAWBeastFormEffect` | заклинание, переключающее любого актёра между расой нордов и расой вервольфа |

Превращения заклинанием у игры нет: своё она делает квестовым скриптом через `SetRace`,
здесь сделано так же, скриптовым эффектом. Прежняя раса **не запоминается** — обе заданы
свойствами эффекта, потому что хранить её негде: эффект памяти между применениями не имеет,
а `StorageUtil` потянул бы за собой PapyrusUtil и заголовки SKSE.

Вызов в игре: `help CLAW 0`, затем `player.placeatme <id> 1`. Заклинание:
`player.addspell <id CLAWBeastFormSpell>`.

Имена записей латиницей нарочно: Mutagen пишет строки латинской кодировкой, и кириллица
превратилась бы в вопросительные знаки.

## Проверки сборщика вне игры

`python -m unittest discover -s tests -p "test_*.py" -v` проверяет отказ от
неполной установки, сохранение происхождения при повторной сверке и обнаружение
изменённых либо лишних файлов перед упаковкой. Blender и игра для этих тестов не нужны.

## `test_CLAW - Wild Preset Fixture`

This isolated test plugin defines six initially-beast NPC bases: Sever, Klyk,
Buryi, Luna, Vyuga and Tucha. The first three are male and the last three female;
all use `WerewolfBeastRace`, level10, weight50 and unaggressive fixture AI.
It contains no placed references, quests, scripts, templates or vanilla overrides.
Installing the plugin spawns nothing. A manual test operator creates its owned
references only on the owner's group command. These female fixtures supplement
the older Ulva test described above.

`fixtures/CLAW-Human-Contrast.xml` supplies six ordinary HUMAN BodySlide/OBody
presets for HIMBO and 3BA: Slim, Muscular and Heavy for each sex. The same human
coefficients are used for human-to-beast linkage and originally-beast OBody
source bootstrap. Both XML endpoints are equal; existing human NPC base weights
are not changed. The XML and fixture plugin are test resources, never part of a
release package.

The six bases have local IDs `0x800..0x805`; resolve them against this exact ESL
plugin name rather than guessing a runtime FE index. Runtime preset distribution
configuration, source-family declarations and group-command implementation are
separate explicit scene requirements. No working automatic assignment, rendered
deformation, safe runtime contact or implemented group handler is inferred from
an offline build. The source bootstrap test must not be replaced by a tester's
manual `GenActor`, preset assignment or temporary human transformation.

Group removal means hiding only same-run owned references and retaining their
registry/state. Adding a hidden group re-enables those references; repeated add
must not duplicate them or reroll presets. The wild group is absent from initial
human scene preparation and appears only on a separate owner command. Actual
group operations require the testing tool's qualified implementation.
