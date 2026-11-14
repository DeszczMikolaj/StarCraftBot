# 07. Rozwiązywanie problemów

Zacznij od diagnostyki, bo wskazuje większość problemów ze środowiskiem:

```bash
docker compose run --rm sc2 python -m scbot.doctor --launch
```

Gdy to nie wystarcza, włącz pełny log gry i python-sc2 zmienną `SCBOT_DEBUG`:

```bash
docker compose run --rm -e SCBOT_DEBUG=1 sc2 python -m scbot.play --agent scripted
```

## Docker

| Objaw | Przyczyna i rozwiązanie |
|-------|-------------------------|
| `open //./pipe/dockerDesktopLinuxEngine: Nie można odnaleźć określonego pliku` | Docker Desktop nie działa. Uruchom go i poczekaj na zakończenie startu. |
| Budowanie przerywa się podczas pobierania gry | Uruchom `docker compose build sc2` ponownie. Pobieranie jest wznawiane, a ukończone pliki zostają w pamięci podręcznej. |
| `sha256sum: WARNING: 1 computed checksum did NOT match` przy budowaniu | Pobrane archiwum różni się od tego, z którego zbudowano projekt. Nie obchodź tego bez sprawdzenia. Jeśli celowo zmieniasz wersję gry, podaj `--build-arg SC2_VERSION=... --build-arg SC2_SHA256=` (pusta suma wyłącza kontrolę). |
| `$'\r': command not found` w `install_sc2.sh` | Skrypt ma końce linii CRLF. Repozytorium wymusza LF przez `.gitattributes`; napraw kopię roboczą komendą `git add --renormalize .` i pobierz pliki ponownie. |
| `no space left on device` | Dysk Dockera jest pełny. Zwolnij miejsce: `docker system df`, potem `docker builder prune` i usunięcie nieużywanych obrazów. |
| `Bind for 127.0.0.1:6006 failed: port is already allocated` | Port TensorBoard jest zajęty, zwykle przez wcześniej uruchomiony kontener. `docker compose down` go zatrzyma. |
| Po przerwanym treningu zostały kontenery | `docker ps` pokaże działające, `docker compose down --remove-orphans` je usunie. |

## Gra i środowisko

| Objaw | Przyczyna i rozwiązanie |
|-------|-------------------------|
| `SC2 installation not found`, `the game worker exited unexpectedly (exit code 1)` albo `[FAIL] StarCraft II not found at ...` | Skrypt uruchomiono poza kontenerem na maszynie bez gry albo gra jest w nietypowym miejscu. Użyj `docker compose run --rm sc2 ...` lub ustaw `SC2PATH` ([runbook 02](02-klient-windows.md)). |
| `Map 'Simple64' was not found` / `[FAIL] map` | Brak paczki map `Melee` w katalogu `Maps` gry. W Dockerze przebuduj obraz, na Windows wykonaj krok 3 z [runbooka 02](02-klient-windows.md). |
| `SC2EnvError: the game did not answer within 240 s` | Gra nie wystartowała w czasie `start_timeout_s`. W Dockerze najczęściej maszyna jest przeciążona zbyt dużą liczbą równoległych gier: zmniejsz `--num-envs`. Na świeżej instalacji w Windows patrz tabela niżej. |
| `SC2EnvError: the game did not answer within 120 s` | Gra przestała odpowiadać w trakcie (`step_timeout_s`). Pojedynczy przypadek pętla treningowa obsługuje sama: restartuje grę pod tym samym numerem epizodu. |
| Pojedynczy komunikat `game failed (1 in a row), restarting it` z `WSServerHandshakeError: 404` | Przejściowy błąd połączenia przy starcie gry. Nie wymaga reakcji: pętla powtarza grę pod tym samym numerem. W treningu na 500 gier zdarzyło się to raz. |
| `SC2EnvError: the game worker failed:` z tracebackiem | Wyjątek w kodzie bota (`src/scbot/env/`). Traceback pochodzi z procesu gry. Odtwórz go pojedynczą grą z `SCBOT_DEBUG=1`. |
| Seria komunikatów `game failed (N in a row), restarting it`, po czym trening kończy się wyjątkiem `SC2EnvError` | Po 5 awariach bez żadnej ukończonej gry pomiędzy nimi pętla kończy pracę, żeby nie kręcić się w kółko. Tablica z ostatniego ukończonego epizodu jest zapisana. Znajdź przyczynę pojedynczą grą, potem wznów trening z `--resume`. |
| Gry kończą się remisem po 20 minutach | To limit czasu gry (`--max-game-minutes`), a nie błąd. Agent nie zdążył zniszczyć wszystkich budynków wroga. |

## Trening i tablica Q

| Objaw | Przyczyna i rozwiązanie |
|-------|-------------------------|
| `runs/<nazwa>/qtable.npz already exists` | Run o tej nazwie już istnieje. Dodaj `--resume`, żeby go kontynuować, albo wybierz inną `--run-name`. |
| `nothing to resume` | Podano `--resume` dla nazwy, pod którą nie ma zapisanej tablicy. Sprawdź `--run-name`. |
| `the run already has N episodes; raise --episodes` | `--episodes` to docelowa łączna liczba gier w runie, nie liczba dodatkowych. Podaj wartość większą niż N. |
| `the Q-table was trained with a different action set` | Tablica powstała przed zmianą listy akcji makro. Kolumny tablicy odpowiadają akcjom, więc starej tablicy nie da się użyć. Wytrenuj nową. |
| `unknown observation feature` przy wczytywaniu tablicy | Tablica korzysta z cechy, którą usunięto lub przemianowano w `observation.py`. Cechy wolno tylko dopisywać na końcu. |
| Komputer zwalnia, gry trwają coraz dłużej | Za dużo gier naraz. Sprawdź `docker stats`; jedna gra to około 1,5 rdzenia i 0,5–0,8 GB pamięci. |
| TensorBoard nie pokazuje nowego runu | Odśwież stronę. Wykresy pojawiają się dopiero po pierwszej ukończonej grze. |

## Windows (klient gry)

| Objaw | Przyczyna i rozwiązanie |
|-------|-------------------------|
| `[FAIL] StarCraft II not found at C:\Program Files (x86)\StarCraft II (default location)`, choć gra jest zainstalowana | Gra jest w innym katalogu i jeszcze nie była uruchomiona. Ustaw `SC2PATH` na czas pierwszego startu (krok 4 [runbooka 02](02-klient-windows.md)). |
| `the game did not answer within 240 s`, a na ekranie jest małe okno „Preparing game data" | Pierwszy start świeżej instalacji: gra dociąga dane i do tego czasu nie przyjmuje połączeń. Powtarzaj komendę, pobieranie jest wznawiane (krok 5 [runbooka 02](02-klient-windows.md)). |
| `uv sync` pobiera kilka GB | To PyTorch z CUDA. Dzieje się raz, potem pliki są w pamięci podręcznej uv. |
| `torch ... CPU only` w diagnostyce na Windows | Zainstalował się wariant bez CUDA albo sterownik karty jest za stary dla CUDA 12.6. Zaktualizuj sterownik NVIDIA i wykonaj `uv sync --reinstall-package torch`. |
| Błąd `RuntimeError` o `freeze_support` lub w kółko startujące procesy | Własny skrypt używający `SC2MacroEnv` nie ma strażnika `if __name__ == "__main__":`. Na Windows jest on wymagany, bo gra działa w osobnym procesie. |

## Gdzie szukać dalej

- Jak działa środowisko i proces gry: [docs/architektura.md](../docs/architektura.md).
- Znaczenie cech, akcji i nagrody: [docs/srodowisko.md](../docs/srodowisko.md).
