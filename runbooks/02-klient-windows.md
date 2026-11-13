# 02. Klient Windows

**Cel:** uruchamiać te same skrypty na zwykłym kliencie gry w Windows, żeby oglądać bota
na żywo i odtwarzać powtórki.

> **Stan weryfikacji:** tej ścieżki nie dało się przećwiczyć w dniu pisania runbooka, bo
> klient gry nie był zainstalowany. Sprawdzone jest tylko to, co nie wymaga gry: `uv sync`
> oraz `scbot.doctor`, który poprawnie zgłasza brak instalacji. Kroki 1, 3 i 5 opisują
> oczekiwane zachowanie python-sc2 i wymagają potwierdzenia przy pierwszym użyciu.

Klient Windows zawsze otwiera okno gry, więc nie zastępuje środowiska headless z
[runbooka 01](01-srodowisko-docker.md). Służy do podglądu.

## Wymagania

- Konto Battle.net i około 30 GB miejsca na grę.
- [uv](https://docs.astral.sh/uv/) do zarządzania Pythonem.
- Zbudowany obraz Dockera, jeśli chcesz skopiować z niego mapy (krok 3).

## Kroki

### 1. Zainstaluj grę

Zainstaluj StarCraft II przez aplikację Battle.net (wersja darmowa wystarcza) i **uruchom
ją raz do menu głównego**. Pierwsze uruchomienie tworzy plik
`Dokumenty\StarCraft II\ExecuteInfo.txt`, po którym python-sc2 odnajduje instalację.

Jeśli gra jest poza domyślnym `C:\Program Files (x86)\StarCraft II` i skrypty jej nie
znajdują, wskaż katalog zmienną środowiskową i otwórz nowy terminal:

```powershell
setx SC2PATH "D:\Gry\StarCraft II"
```

### 2. Przygotuj środowisko Pythona

```bash
uv sync
```

Tworzy `.venv` z Pythonem 3.12 i zależnościami z `uv.lock`, w tym PyTorch z obsługą CUDA
(kilka GB przy pierwszym pobraniu).

### 3. Dodaj mapy

Projekt gra na mapie `Simple64` z paczki `Melee`, której nie ma w standardowej instalacji.
Skopiuj ją z obrazu Dockera:

```bash
docker create --name scbot-maps starcraftbot/sc2:4.10
```

```bash
docker cp scbot-maps:/root/StarCraftII/Maps/Melee ./Melee
```

```bash
docker rm scbot-maps
```

Przenieś powstały katalog `Melee` do `<katalog gry>\Maps\` (utwórz `Maps`, jeśli go nie
ma). Dla instalacji w `Program Files` Windows poprosi o uprawnienia administratora.
Docelowo plik ma leżeć pod `<katalog gry>\Maps\Melee\Simple64.SC2Map`.

### 4. Sprawdź środowisko

```bash
uv run python -m scbot.doctor
```

Wiersze `StarCraft II` i `map` powinny mieć status `ok`. Wiersz `torch` powinien
pokazywać `CUDA available`.

### 5. Zagraj z podglądem

```bash
uv run python -m scbot.play --agent scripted --difficulty VeryEasy --realtime
```

Otworzy się okno gry, a bot zagra w tempie człowieka. Bez `--realtime` gra biegnie tak
szybko, jak pozwala komputer.

## Oglądanie powtórek z Dockera

Pliki `.SC2Replay` zapisane przez kontener (np. `runs/<nazwa>/replays/`) otwiera się
dwuklikiem w kliencie Windows. Powtórki pochodzą z wersji 4.10, więc klient może najpierw
pobrać dane tej wersji. Tego również nie udało się jeszcze sprawdzić.

## Uwagi

- Klient Windows to nowsza wersja gry niż linuksowa 4.10. Nie mieszaj platform w obrębie
  jednego eksperymentu: tablica Q wytrenowana w Dockerze powinna być oceniana w Dockerze.
- Równoległe gry (`--num-envs`) na Windows otwierają tyle okien, ile jest gier.
