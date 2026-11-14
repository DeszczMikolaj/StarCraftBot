# Przewodnik po kodzie

Jeden punkt wejścia do zrozumienia, jak ten projekt działa od środka. Prowadzi przez kod
w kolejności, w jakiej wykonuje się jedna gra: od komendy w terminalu, przez start
StarCraft II, pojedynczą decyzję agenta, aż po aktualizację tablicy Q i zapis wyników.

Dokument nie powtarza pozostałej dokumentacji. Odsyła do niej tam, gdzie jest szersze
uzasadnienie:

| Chcesz wiedzieć | Czytaj |
|-----------------|--------|
| Z jakich części składa się projekt i dlaczego tak | [architektura.md](architektura.md) |
| Co dokładnie znaczą cechy, akcje i nagroda | [srodowisko.md](srodowisko.md) |
| Jak działa Q-Learning i jego tablica | [model-a-q-learning.md](model-a-q-learning.md) |
| Co zmierzyliśmy i czego się nauczyliśmy | [wyniki.md](wyniki.md) |
| Jak dodać agenta, cechę, akcję | [rozwijanie.md](rozwijanie.md) |
| Co wpisać, żeby coś uruchomić | [runbooki](../runbooks/README.md) |

## Jak korzystać z przewodnika

1. Miej pod ręką działające środowisko ([runbook 01](../runbooks/01-srodowisko-docker.md)).
   Najwięcej zrozumiesz, uruchamiając kod równolegle z czytaniem.
2. Idź przystankami po kolei. Każdy to jeden plik: po co jest, co dzieje się w kolejnych
   liniach i dlaczego, oraz jedno ćwiczenie „sprawdź sam".
3. Odnośniki prowadzą do konkretnych linii. Test `tests/test_docs_links.py` sprawdza, że
   każdy z nich nadal wskazuje kod, o którym mówi, więc po zmianach w kodzie przewodnik
   nie rozjedzie się po cichu.

Komenda, do której będziemy wracać (jedna gra z wypisywaniem odczytów):

```bash
docker compose run --rm sc2 python -m scbot.play --agent scripted --difficulty VeryEasy
```

## Mapa przystanków

| # | Plik | Co zrozumiesz |
|---|------|---------------|
| 1 | `src/scbot/play.py`, `cli_common.py` | Jak komenda zamienia się w konfigurację, agenta i jedną grę |
| 2 | `src/scbot/config.py` | Wszystkie pokrętła środowiska w jednym miejscu |
| 3 | `src/scbot/runner.py` | Pętlę „obserwacja → akcja → nagroda" i jej wersję dla wielu gier |
| 4 | `src/scbot/env/sc2_env.py` | Co robią `reset()` i `step()` i jak pilnują procesu gry |
| 5 | `src/scbot/env/worker.py` | Proces gry: start StarCraft II i rozmowa przez potok |
| 6 | `src/scbot/env/bot.py` | Bota w grze: kiedy pyta o akcję i co wtedy wysyła |
| 7 | `src/scbot/env/decision_points.py` | Regułę „czy teraz pytać agenta" |
| 8 | `src/scbot/env/observation.py` | Jak odczyty z gry stają się wektorem 24 liczb |
| 9 | `src/scbot/env/reward.py` | Jak liczniki z gry stają się nagrodą |
| 10 | `src/scbot/env/actions.py`, `macro.py` | Maskę akcji, wykonanie akcji i samodzielną obsługę bazy |
| 11 | `src/scbot/agents/base.py`, `simple.py` | Interfejs agenta oraz agenta losowego i skryptowego |
| 12 | `src/scbot/agents/qlearning.py` | Dyskretyzację stanu, wybór akcji i aktualizację tablicy Q |
| 13 | `src/scbot/train_q.py`, `run_logging.py` | Skrypt treningowy i wszystko, co zapisuje |
| 14 | `evaluate.py`, `report.py`, `doctor.py` | Narzędzia wokół treningu |

Jeśli masz mało czasu, przeczytaj przystanki 3, 6, 10 i 12. To jest rdzeń.

## Najpierw całość: jedna decyzja od początku do końca

Zanim wejdziesz w pliki, prześledź jedną decyzję. Każdy krok to jedno miejsce w kodzie.
Zaczynamy w chwili, gdy agent właśnie dostał obserwację.

| Krok | Gdzie | Co się dzieje |
|------|-------|---------------|
| 1 | [wybór akcji](../src/scbot/runner.py#L143-L144) | Pętla epizodów pyta agenta o akcję (`agent.act`) i wysyła ją do środowiska (`step_async`). |
| 2 | [`step_async`](../src/scbot/env/sc2_env.py#L119-L129) | Środowisko sprawdza akcję i wkłada do potoku komunikat `("action", n)`. |
| 3 | [`PipeBridge.decide`](../src/scbot/env/worker.py#L38-L43) | W procesie gry bot czekał na `recv()`. Dostaje numer akcji. |
| 4 | [wykonanie akcji](../src/scbot/env/bot.py#L127-L135) | Bot zamienia numer na `MacroAction`, zapamiętuje chwilę decyzji i każe warstwie makro wykonać akcję. |
| 5 | [`execute`](../src/scbot/env/macro.py#L192-L226) | Warstwa makro wybiera robotnika, miejsce budowy albo zmienia tryb armii. |
| 6 | [`on_step`](../src/scbot/env/bot.py#L62-L68) | Po akcji bot robi porządki (`housekeeping`): robotnicy, przerwane budowy, armia. |
| 7 | biblioteka python-sc2 | Rozkazy idą do gry, gra symuluje 8 pętli i znów woła `on_step`. |
| 8 | [`on_step`](../src/scbot/env/bot.py#L62-L68) | Co czwarty krok bot liczy maskę akcji i pyta regułę z przystanku 7, czy to punkt decyzyjny. |
| 9 | [`_decide`](../src/scbot/env/bot.py#L109-L126) | Jeśli tak: liczy nagrodę od poprzedniej decyzji, czyta stan gry, pakuje wszystko w `StepData`. |
| 10 | [`PipeBridge.decide`](../src/scbot/env/worker.py#L38-L43) | `StepData` idzie potokiem do procesu głównego, a bot znów czeka na akcję. |
| 11 | [`collect`](../src/scbot/env/sc2_env.py#L142-L157) | Środowisko odbiera odpowiedź i oddaje ją jako wynik `step()`. |
| 12 | [odbiór odpowiedzi](../src/scbot/runner.py#L103-L124) | Pętla epizodów przekazuje przejście agentowi (`agent.observe`). |
| 13 | [`observe`](../src/scbot/agents/qlearning.py#L175-L202) | Q-Learning poprawia jedną komórkę tablicy. Wracamy do kroku 1. |

Między krokiem 7 a 9 może minąć od 1,43 s do 60 s czasu gry. Dlaczego nie jest to stały
odstęp, wyjaśnia [srodowisko.md](srodowisko.md#punkty-decyzyjne).

---

## Przystanek 1: od komendy do gry

Pliki: [`play.py`](../src/scbot/play.py), [`cli_common.py`](../src/scbot/cli_common.py).

`play` to najprostszy skrypt w projekcie i dobry wzór dla własnych. Robi cztery rzeczy.

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`main`](../src/scbot/play.py#L50-L61) | Buduje parser opcji. Opcje środowiska i agenta są wspólne dla wszystkich skryptów, więc dodają je funkcje z `cli_common`. | Żeby `--difficulty` czy `--map` znaczyły to samo w `play`, `train_q` i `evaluate`. |
| [`env_config_from_args`](../src/scbot/cli_common.py#L58-L68) | Zamienia opcje na obiekt `EnvConfig` (przystanek 2). | Dalej kod nie zna już argumentów, tylko konfigurację. |
| [`build_agent`](../src/scbot/cli_common.py#L84-L91) | Tworzy agenta: losowego, skryptowego albo wczytuje tablicę Q z pliku. | Jedno miejsce, do którego dopisuje się nowe typy agentów. |
| [`on_step`](../src/scbot/play.py#L72-L74) | Funkcja wołana po każdej decyzji. Tu wypisuje co dziesiątą. | Pętla epizodów nic nie drukuje sama; kto chce widzieć kroki, podaje taką funkcję. |
| [`run_episode`](../src/scbot/play.py#L76-L88) | Tworzy środowisko, rozgrywa jedną grę, zawsze zamyka środowisko (`finally`). | Bez `close()` po błędzie zostałby osierocony proces gry. |
| [`format_step`](../src/scbot/play.py#L37-L47) | Składa wiersz, który widzisz na ekranie, z `info["raw"]` i maski akcji. | To gotowa ściąga, jak czytać `info`. |

**Sprawdź sam.** Uruchom `play` z `--print-every 1`. Zobaczysz każdą decyzję i to, że
odstępy czasu gry między nimi są nierówne.

## Przystanek 2: konfiguracja

Plik: [`config.py`](../src/scbot/config.py). Trzy niezmienne klasy danych. Nic tu się nie
wykonuje, ale każda liczba, którą będziesz chciał zmienić, jest tutaj.

| Linie | Co zawiera |
|-------|------------|
| [`RewardConfig`](../src/scbot/config.py#L21-L35) | Wagi nagrody: wygrana, przegrana, remis i cztery składniki pomocnicze. |
| [`MacroConfig`](../src/scbot/config.py#L38-L58) | Limity i odległości warstwy skryptowej: ile SCV, baz, koszar, zapasu populacji, promień obrony, minimalny czas rozkazu dla armii. |
| [`EnvConfig`](../src/scbot/config.py#L61-L82) | Mapa, przeciwnik, czas (krok bota, interwał, czekanie, limit gry), limity czasu oczekiwania na grę. Zawiera w sobie dwie poprzednie klasy. |
| [`__post_init__`](../src/scbot/config.py#L84-L90) | Odrzuca bezsensowne ustawienia już przy tworzeniu obiektu. |
| [`loops_per_interval`](../src/scbot/config.py#L92-L100) | Przelicza interwał na pętle gry i sekundy (32 pętle, 1,43 s). |

Klasy są zamrożone (`frozen=True`), bo obiekt konfiguracji jest wysyłany do procesu gry.
Zmieniony wariant tworzy się przez `dataclasses.replace(EnvConfig(), difficulty="Easy")`.

**Sprawdź sam.** W `MacroConfig` zmień `army_mode_commit_seconds` z 30 na 5 i zagraj
agentem losowym (`--agent random`). W podsumowaniu zobaczysz dużo więcej akcji `ATTACK`
i `RETREAT`. Potem cofnij zmianę.

## Przystanek 3: pętla epizodów

Plik: [`runner.py`](../src/scbot/runner.py). To tutaj spotykają się agent i środowisko.
Cała nauka i wszystkie decyzje dzieją się w tym jednym procesie.

Najpierw wersja dla jednej gry, bo jest tylko opakowaniem:
[`run_episode`](../src/scbot/runner.py#L178-L200) woła `run_episodes` z jednym
środowiskiem i jednym epizodem.

Właściwa pętla to [`run_episodes`](../src/scbot/runner.py#L49-L175). Każde środowisko
dostaje „slot" ([`_Slot`](../src/scbot/runner.py#L35)), który pamięta, w której grze
jest, ostatnią obserwację i ostatnią akcję.

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`start`](../src/scbot/runner.py#L83-L90) | Zaczyna grę w slocie: `reset_async` z ziarnem `seed + numer epizodu` i ewentualną ścieżką powtórki. | Ziarno zależne od numeru sprawia, że grę numer `n` da się odtworzyć. |
| [`start_next`](../src/scbot/runner.py#L92-L98) | Przydziela slotowi kolejny numer epizodu albo wyłącza slot, gdy numery się skończyły. | Numeracja w kolejności startu. |
| [`advance`](../src/scbot/runner.py#L100-L107) | Odbiera jedną odpowiedź z gry (`collect`). Pierwsza odpowiedź po `reset` to tylko obserwacja początkowa. | Przy pierwszej nie ma jeszcze poprzedniej akcji, więc nie ma czego uczyć. |
| [`observe`](../src/scbot/runner.py#L108-L117) | Przy uczeniu podaje agentowi przejście: poprzednia obserwacja, akcja, nagroda, nowa obserwacja, nowa maska, czy koniec, ile interwałów minęło. | To jest jedyne miejsce, w którym agent się uczy. |
| [`on_step`](../src/scbot/runner.py#L118-L123) | Woła funkcję obserwatora (wypisywanie, zapis do `steps.jsonl`). | Logowanie jest poza pętlą, żeby jej nie zaśmiecać. |
| [koniec gry](../src/scbot/runner.py#L126-L141) | Zamyka epizod u agenta, składa podsumowanie i oddaje wyniki w kolejności numerów, nawet jeśli późniejsza gra skończyła się wcześniej. Potem slot zaczyna następną grę. | Żeby numer w plikach wyników zawsze znaczył tę samą grę. |
| [następna akcja](../src/scbot/runner.py#L143-L145) | Gra trwa: agent wybiera akcję, slot wysyła ją do gry i nie czeka na odpowiedź. | Dzięki temu inne gry mogą w tym czasie symulować. |
| [pętla główna](../src/scbot/runner.py#L147-L175) | Startuje wszystkie sloty, a potem w kółko czeka (`wait`), aż którakolwiek gra odpowie, i ją obsługuje. | Gry odpowiadają w różnym tempie; nikt na nikogo nie czeka. |
| [awaria gry](../src/scbot/runner.py#L164-L174) | Gdy gra padnie, ten sam epizod startuje od nowa. Po pięciu awariach bez żadnej ukończonej gry pętla się poddaje. | Pojedynczy błąd startu gry nie powinien zabijać godzinnego treningu. |

Na końcu pliku jest [`wilson_interval`](../src/scbot/runner.py#L203-L211), czyli
przedział ufności dla odsetka wygranych używany w ewaluacji.

**Sprawdź sam.** Testy tego pliku nie potrzebują gry. Przeczytaj `FakeEnv`
w `tests/test_agents_and_runner.py` i uruchom `uv run pytest tests/test_agents_and_runner.py -v`.
Nazwy testów mówią, co pętla gwarantuje.

## Przystanek 4: środowisko Gymnasium

Plik: [`sc2_env.py`](../src/scbot/env/sc2_env.py). Klasa `SC2MacroEnv` nie wie nic
o StarCraft. Jej zadanie to rozmowa z procesem gry i pilnowanie, żeby ten proces żył.

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`__init__`](../src/scbot/env/sc2_env.py#L53-L63) | Deklaruje przestrzeń obserwacji (24 liczby) i akcji (8). Nie startuje gry. | Gra startuje dopiero przy pierwszym `reset`, więc samo utworzenie środowiska nic nie kosztuje. |
| [`reset`](../src/scbot/env/sc2_env.py#L67-L76) i [`step`](../src/scbot/env/sc2_env.py#L78-L81) | Każde to dwie połowy: wyślij żądanie, odbierz odpowiedź. | Połowy są osobno dostępne dla pętli wielu gier. |
| [`reset_async`](../src/scbot/env/sc2_env.py#L101-L117) | Porzuca grę w toku (jeśli jest), upewnia się, że proces gry działa, wysyła `("reset", {...})` i ustawia termin odpowiedzi. | Start gry trwa kilka sekund, stąd osobny, dłuższy limit czasu. |
| [`step_async`](../src/scbot/env/sc2_env.py#L119-L129) | Sprawdza, czy wolno teraz wysłać akcję, i wysyła `("action", n)`. | Błędy użycia (akcja przed `reset`, dwie akcje pod rząd) mają dawać jasny komunikat. |
| [`collect`](../src/scbot/env/sc2_env.py#L142-L157) | Czeka na odpowiedź, zapamiętuje, czy gra trwa, i zachowuje maskę akcji. | Stan „czy jesteśmy w grze" decyduje, co wolno zrobić potem. |
| [`check_health`](../src/scbot/env/sc2_env.py#L159-L174) | Zgłasza błąd, jeśli proces gry umarł albo minął termin odpowiedzi. | Zawieszona gra nie może zawiesić treningu. |
| [`_ensure_worker`](../src/scbot/env/sc2_env.py#L178-L188) | Tworzy potok i startuje proces gry (`worker_main`, przystanek 5). | Proces żyje przez wiele gier; nowy powstaje tylko po awarii. |
| [`_receive`](../src/scbot/env/sc2_env.py#L198-L211) | Odpytuje potok co pół sekundy. Komunikat `("step", ...)` to wynik, każdy inny to błąd z procesu gry. | Błąd w kodzie bota wraca tu jako `SC2EnvError` z oryginalnym tracebackiem. |
| [`_stop_worker`](../src/scbot/env/sc2_env.py#L213-L221) i [`_kill_process_tree`](../src/scbot/env/sc2_env.py#L224-L238) | Zabijają proces gry razem z uruchomionym przez niego StarCraft II. | Samo zabicie procesu Pythona zostawiłoby grę działającą w tle. |

Wyjątek [`SC2EnvError`](../src/scbot/env/sc2_env.py#L28) oznacza zawsze to samo: gra
padła, przestała odpowiadać albo środowisko zostało użyte w złej kolejności.

**Sprawdź sam.** Uruchom [`examples/random_gym_loop.py`](../examples/random_gym_loop.py).
To 15 linii, które używają wyłącznie `reset`, `step` i `close`.

## Przystanek 5: proces gry

Plik: [`worker.py`](../src/scbot/env/worker.py). Ten kod działa w osobnym procesie.
Nagłówek pliku opisuje protokół komunikatów; tabela jest też
w [architektura.md](architektura.md#przebieg-jednej-decyzji).

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`worker_main`](../src/scbot/env/worker.py#L99-L104) | Proces staje się liderem własnej grupy procesów i wycisza logi gry. | Grupa pozwala zabić Pythona i StarCraft II jednym sygnałem. Logi gry zalałyby terminal. |
| [pętla komunikatów](../src/scbot/env/worker.py#L106-L119) | Czeka na `reset`, rozgrywa grę, wraca do czekania. Wyjątek z gry zamienia na komunikat `("error", traceback)`. | Proces przeżywa wiele gier, więc Python i biblioteki ładują się raz. |
| [`_run_episode`](../src/scbot/env/worker.py#L68-L82) | Ustawia ziarno, tworzy most (`PipeBridge`) i bota (`MacroBot`). | Bot dostaje most, a nie potok, więc nie wie, z kim rozmawia. |
| [`run_game`](../src/scbot/env/worker.py#L83-L93) | Funkcja python-sc2: startuje StarCraft II, tworzy grę Terran kontra wbudowany Terran i woła metody bota aż do końca gry. | Od tej linii sterowanie ma biblioteka; nasz kod działa tylko w wywołaniach zwrotnych bota. |
| [ostatni krok](../src/scbot/env/worker.py#L94-L96) | Dopiero po zamknięciu gry wysyła końcowy `StepData`. | Powtórka jest zapisywana przy zamykaniu gry. Gdyby wynik poszedł wcześniej, plik powtórki mógłby jeszcze nie istnieć. |
| [`PipeBridge.decide`](../src/scbot/env/worker.py#L38-L43) | Wysyła punkt decyzyjny i blokuje się na `recv()`, aż przyjdzie akcja. | Gra nie biegnie w czasie rzeczywistym, więc może czekać dowolnie długo. |
| [`_configure_output`](../src/scbot/env/worker.py#L51-L65) | Przekierowuje standardowe wyjście procesu donikąd, chyba że ustawiono `SCBOT_DEBUG`. | StarCraft II dziedziczy wyjście procesu i pisze tam swój log startowy. |

**Sprawdź sam.** Uruchom grę z pełnym logiem i porównaj go z tabelą:

```bash
docker compose run --rm -e SCBOT_DEBUG=1 sc2 python -m scbot.play --agent scripted --max-game-minutes 1
```

## Przystanek 6: bot w grze

Plik: [`bot.py`](../src/scbot/env/bot.py). Klasa `MacroBot` dziedziczy po `BotAI`
z python-sc2. Biblioteka sama woła jej metody: `on_start` raz, `on_step` co krok bota
(co 8 pętli gry), `on_unit_created` przy każdej nowej jednostce, `on_end` na końcu.

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`__init__`](../src/scbot/env/bot.py#L36-L50) | Zapamiętuje most i konfigurację, zeruje liczniki. | Jeden obiekt bota to jedna gra. |
| [`on_start`](../src/scbot/env/bot.py#L54-L56) | Ustawia, że krok bota to 8 pętli gry, i tworzy warstwę makro. | Warstwa makro potrzebuje gotowego bota, a ten jest gotowy dopiero tutaj. |
| [`on_unit_created`](../src/scbot/env/bot.py#L58-L60) | Zlicza ukończone jednostki według typu. | Z tych liczników powstają nagrody za Marines i SCV. |
| [`on_step`](../src/scbot/env/bot.py#L62-L68) | Co `decision_interval` kroków liczy maskę akcji i sprawdza, czy to punkt decyzyjny. Jeśli tak, woła `_decide`. Zawsze na końcu robi `housekeeping`. | Decyzja jest przed porządkami, żeby porządki widziały już nowy tryb armii. |
| [`_decision_due`](../src/scbot/env/bot.py#L100-L107) | Przekazuje pytanie „czy teraz" do funkcji z przystanku 7. | Reguła jest osobną, czystą funkcją, więc da się ją testować bez gry. |
| [nagroda](../src/scbot/env/bot.py#L109-L117) | Czyta liczniki i liczy nagrodę od poprzedniej decyzji. Pierwsza decyzja w grze tylko ustawia punkt odniesienia. | Nagroda to zawsze zmiana liczników, więc potrzebny jest stan początkowy. |
| [obserwacja](../src/scbot/env/bot.py#L119-L126) | Składa `info` (surowe odczyty, maska, składniki nagrody) i pakuje je z wektorem obserwacji w `StepData`. | `StepData` to dokładnie to, co zwraca `step()`. |
| [`decide`](../src/scbot/env/bot.py#L127-L127) | Wysyła punkt decyzyjny mostem i czeka na numer akcji. | Tu proces gry stoi, dopóki agent nie odpowie. |
| [po decyzji](../src/scbot/env/bot.py#L129-L135) | Zapamiętuje pętlę gry decyzji i (dla `NO_OP`) maskę opcji, z których agent zrezygnował. Wykonuje akcję i aktualizuje statystyki. | Te dwie wartości są wejściem reguły z przystanku 7. |
| [`on_end`](../src/scbot/env/bot.py#L70-L89) | Liczy nagrodę końcową, dokłada `result` i podsumowanie gry, oddaje ostatni krok mostowi. Remis oznacza limit czasu, więc `truncated`, a nie `terminated`. | Agent musi odróżnić koniec gry od ucięcia. |
| [`_read_raw`](../src/scbot/env/bot.py#L149-L179) | Jedyne miejsce, w którym stan gry z python-sc2 zamienia się na słownik odczytów. Klucze to nazwy cech z przystanku 8. | Nowa cecha obserwacji wymaga jednej linii tutaj. |
| [`_reward_counters`](../src/scbot/env/bot.py#L181-L199) | Zbiera narastające liczniki: wyszkolone jednostki oraz wartość zniszczeń i strat z punktacji gry. | Wejście dla nagrody (przystanek 9). |
| [`_info`](../src/scbot/env/bot.py#L201-L210) | Buduje słownik `info`. | Lista kluczy jest w [srodowisko.md](srodowisko.md#słownik-info). |
| [`_episode_summary`](../src/scbot/env/bot.py#L212-L228) | Podsumowanie gry dołączane do ostatniego kroku. | Z niego powstaje wiersz w `episodes.csv`. |

Rzeczy, które łatwo przeoczyć:

- `self.minerals`, `self.workers`, `self.structures(...)`, `self.state.score` pochodzą
  z `BotAI`. Dokumentacja tych pól jest w python-sc2, nie w tym projekcie.
- python-sc2 nie zgłasza w `on_unit_created` jednostek obecnych na starcie gry, więc
  pierwsze 12 SCV nie liczy się do nagrody.
- Wyjątek w `on_step` przerywa grę i wraca do procesu głównego jako `SC2EnvError`.

**Sprawdź sam.** Dopisz na początku `_decide` linię
`print(self.time_formatted, mask, file=sys.stderr)` (i `import sys` na górze), uruchom
`play` i zobacz maski w chwilach decyzji. Wyjście standardowe procesu gry jest wyciszone,
dlatego `stderr`. Potem usuń zmianę.

## Przystanek 7: kiedy pytać agenta

Plik: [`decision_points.py`](../src/scbot/env/decision_points.py). Jedna funkcja,
[`decision_due`](../src/scbot/env/decision_points.py#L21-L45), wołana co interwał.
Czyta się ją z góry na dół jak listę reguł, z których pierwsza pasująca wygrywa.

| Linie | Reguła |
|-------|--------|
| [35–36](../src/scbot/env/decision_points.py#L35-L36) | Pierwsza decyzja w grze: zawsze pytaj. |
| [37–38](../src/scbot/env/decision_points.py#L37-L38) | Minęło 60 s bez decyzji: pytaj, nawet jeśli nic nie da się zrobić. To bezpiecznik. |
| [39–40](../src/scbot/env/decision_points.py#L39-L40) | Dostępne jest tylko `NO_OP`: nie pytaj, nie ma wyboru. |
| [41–42](../src/scbot/env/decision_points.py#L41-L42) | Poprzednia akcja nie była czekaniem: pytaj od razu, gdy jest wybór. |
| [43–44](../src/scbot/env/decision_points.py#L43-L44) | Agent czeka, ale pojawiła się akcja, której nie było, gdy wybierał `NO_OP`: pytaj. |
| [45](../src/scbot/env/decision_points.py#L45) | Agent czeka i nic nowego się nie pojawiło: pytaj dopiero po 10 s. |

Uzasadnienie tej konstrukcji i pomiary są
w [srodowisko.md](srodowisko.md#punkty-decyzyjne) oraz [wyniki.md](wyniki.md).

**Sprawdź sam.** `tests/test_decision_points.py` ma po jednym teście na regułę. Zmień
`wait_intervals` w wywołaniu i zobacz, który test przestanie przechodzić.

## Przystanek 8: obserwacja

Plik: [`observation.py`](../src/scbot/env/observation.py).

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`FEATURES`](../src/scbot/env/observation.py#L26-L51) | Lista 24 cech: nazwa, skala, opis. Kolejność na liście to kolejność w wektorze. | Jedno źródło prawdy. Długość wektora, nazwy i skale wynikają z tej listy. |
| [stałe pochodne](../src/scbot/env/observation.py#L53-L57) | Nazwy, indeksy, skale, długość wektora i górne obcięcie. | Reszta kodu importuje te stałe zamiast liczyć sama. |
| [`to_vector`](../src/scbot/env/observation.py#L60-L66) | Sprawdza, że są wszystkie odczyty, dzieli przez skale, obcina do [0, 2], zamienia na `float32`. | Sieci uczą się lepiej na wartościach rzędu jedności; brak odczytu ma być błędem od razu. |
| [`to_raw`](../src/scbot/env/observation.py#L69-L76) | Odwrotność: z wektora z powrotem do surowych wartości, z zaokrągleniem. | Agent skryptowy i dyskretyzacja tablicy Q myślą w surowych jednostkach (minerały, sztuki). |

Znaczenie każdej cechy: [srodowisko.md](srodowisko.md#obserwacja).

**Sprawdź sam.** W interpreterze (`uv run python`) wykonaj:

```python
from scbot.env.observation import FEATURE_NAMES, to_raw, to_vector

raw = dict.fromkeys(FEATURE_NAMES, 0.0) | {"minerals": 250, "marines": 12}
obs = to_vector(raw)
print(obs[:3], to_raw(obs)["minerals"])
```

## Przystanek 9: nagroda

Plik: [`reward.py`](../src/scbot/env/reward.py). Wagi są w `RewardConfig` (przystanek 2).

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`RewardCounters`](../src/scbot/env/reward.py#L13-L23) | Cztery liczniki narastające przez całą grę. | Bot podaje stan liczników, a nie zdarzenia, więc nagroda nie zależy od tego, jak często pytamy. |
| [`_WEIGHT_NAMES`](../src/scbot/env/reward.py#L27-L32) | Łączy licznik z nazwą jego wagi w `RewardConfig`. | Nowy składnik nagrody wymaga wpisu tutaj. |
| [`step`](../src/scbot/env/reward.py#L45-L53) | Dla każdego licznika liczy przyrost od poprzedniego wywołania i mnoży przez wagę. Zwraca sumę i rozbicie na składniki. | Rozbicie trafia do `info["reward_components"]` i do logów. |
| [`finish`](../src/scbot/env/reward.py#L55-L64) | Ostatni krok: przyrosty jak wyżej plus nagroda końcowa za wynik gry. | Wygrana, przegrana i remis są rozróżniane tylko tutaj. |

Tabela wag i ich skala: [srodowisko.md](srodowisko.md#nagroda).

**Sprawdź sam.** `uv run pytest tests/test_reward.py -v`. Trzy testy pokazują całe
zachowanie tej klasy.

## Przystanek 10: akcje i warstwa makro

Pliki: [`actions.py`](../src/scbot/env/actions.py), [`macro.py`](../src/scbot/env/macro.py).

[`MacroAction`](../src/scbot/env/actions.py#L8-L22) to lista ośmiu akcji. Numer akcji
jest jednocześnie numerem kolumny w tablicy Q, dlatego nowe akcje dopisuje się tylko na
końcu.

Klasa [`MacroExecutor`](../src/scbot/env/macro.py#L52) ma trzy zadania: powiedzieć, co da się teraz zrobić,
wykonać wybraną akcję i utrzymywać bazę oraz armię między decyzjami.

**Stan i pytania pomocnicze.**

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [stałe](../src/scbot/env/macro.py#L30-L44) | Typy budynków, odległości i krok siatki przy szukaniu miejsca budowy. | Liczby związane z rozmieszczaniem budynków są w jednym miejscu. |
| [`ArmyMode`](../src/scbot/env/macro.py#L47-L49) | Dwa tryby armii: obrona i atak. | `ATTACK` i `RETREAT` tylko przełączają tryb; rozkazy wydaje `_control_army`. |
| [`pending_structures`](../src/scbot/env/macro.py#L77-L80) | Budynki w budowie plus SCV idące, żeby budowę zacząć. | „W drodze" też się liczy, inaczej agent zleciłby ten sam budynek kilka razy. |
| [`reserved_minerals`](../src/scbot/env/macro.py#L82-L93) | Suma kosztów budynków, do których SCV dopiero idzie. | Gra pobiera koszt przy rozpoczęciu budowy, a nie przy rozkazie. |
| [`can_afford`](../src/scbot/env/macro.py#L98-L101) i [`affordable_count`](../src/scbot/env/macro.py#L103-L106) | Czy stać nas na coś z minerałów wolnych, czyli po odjęciu rezerwy, i na ile sztuk. | Zlecony budynek ma powstać, nawet jeśli agent chciałby wydać te pieniądze. |
| [`spare_supply`](../src/scbot/env/macro.py#L108-L111) | Wolna populacja powiększona o magazyny zlecone i w budowie (po 8 na magazyn). | Magazyn na zapas ponad potrzeby to czysta strata, więc maska go nie oferuje. |
| [`threats`](../src/scbot/env/macro.py#L113-L120) | Jednostki wroga bliżej niż `defend_radius` od któregokolwiek naszego budynku. | To one uruchamiają obronę i cechę `enemy_near_base`. |
| [`army_mode_locked`](../src/scbot/env/macro.py#L122-L127) | Czy od ostatniej zmiany trybu armii minęło mniej niż 30 s gry. | Rozkaz ma trwać na tyle długo, żeby armia zdążyła dojść. |
| [`rally_point`](../src/scbot/env/macro.py#L129-L137) | Punkt zbiórki: przed bazą najbliższą wrogowi, w stronę środka mapy. | Tu armia czeka w trybie obrony. |

**Maska akcji.** [`available_actions`](../src/scbot/env/macro.py#L139-L188) buduje tablicę ośmiu wartości
logicznych. Czyta się ją akcja po akcji:

| Linie | Akcja | Warunek |
|-------|-------|---------|
| [143](../src/scbot/env/macro.py#L143) | `NO_OP` | Zawsze dostępna. |
| [148–153](../src/scbot/env/macro.py#L148-L153) | `TRAIN_SCV` | Bezczynne Command Center, stać nas, a SCV żywych i w produkcji jest mniej niż limit. |
| [155–161](../src/scbot/env/macro.py#L155-L161) | `BUILD_SUPPLY_DEPOT` | Limit populacji poniżej 200, zapas populacji (z magazynami w drodze) poniżej 16, stać nas, mniej niż dwa magazyny w budowie. |
| [163–170](../src/scbot/env/macro.py#L163-L170) | `BUILD_BARRACKS` | Poniżej limitu koszar, mniej niż dwie w budowie, jest gotowy magazyn, stać nas. |
| [172–177](../src/scbot/env/macro.py#L172-L177) | `EXPAND` | Znane jest miejsce, w którym da się postawić bazę, baz jest mniej niż limit, żadna nie jest w budowie, stać nas. |
| [179–181](../src/scbot/env/macro.py#L179-L181) | `TRAIN_MARINE` | Są bezczynne koszary i stać nas. |
| [183–187](../src/scbot/env/macro.py#L183-L187) | `ATTACK` / `RETREAT` | Tryb armii nie jest zablokowany. `ATTACK` w obronie, gdy armia istnieje; `RETREAT` w ataku. |

Maska musi być uczciwa: akcja oznaczona jako dostępna ma się dać wykonać. Akcja, która
jest oferowana, a potem odrzucana, nic nie kosztuje i uczący się agent zaczyna jej
nadużywać ([wyniki.md](wyniki.md)).

**Wykonanie akcji.** [`execute`](../src/scbot/env/macro.py#L192-L226):

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [194–195](../src/scbot/env/macro.py#L194-L195) | Akcja spoza maski nie jest wykonywana; funkcja zwraca `False`. | Agent, który ignoruje maskę, nie psuje gry, a środowisko to raportuje. |
| [198–205](../src/scbot/env/macro.py#L198-L205) | Szkolenie: w każdym bezczynnym budynku jedna jednostka, ale nie więcej, niż pozwalają wolne minerały. | Jedna decyzja uruchamia całą dostępną produkcję. |
| [206–217](../src/scbot/env/macro.py#L206-L217) | Budowa magazynu lub koszar: `bot.build` z python-sc2 szuka wolnego miejsca wokół punktu z [`_build_anchor`](../src/scbot/env/macro.py#L228-L236) i wybiera robotnika. | Agent nie decyduje, gdzie i kim budować. |
| [`_expand`](../src/scbot/env/macro.py#L238-L246) | Stawia Command Center dokładnie w zapamiętanym miejscu. Po niepowodzeniu przestaje je oferować do następnego sprawdzenia. | Odrzucona ekspansja nie może być oferowana w kółko. |
| [220–225](../src/scbot/env/macro.py#L220-L225) | `ATTACK` i `RETREAT` wołają [`_set_army_mode`](../src/scbot/env/macro.py#L277-L281): zmiana trybu i zapamiętanie chwili zmiany. | Od tej chwili liczy się 30 s blokady. |

[`refresh_expansion_site`](../src/scbot/env/macro.py#L248-L275) wybiera miejsce pod następną bazę: lokalizacja
bliższa naszemu startowi niż startowi wroga, niezajęta przez nas, na której da się teraz
postawić Command Center i do której da się dojść. Jest wołana co kilka sekund w ramach
porządków.

**Porządki między decyzjami.** [`housekeeping`](../src/scbot/env/macro.py#L285-L292) działa w każdym kroku
bota, niezależnie od tego, czy agent był pytany:

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [287–291](../src/scbot/env/macro.py#L287-L291) | Co 8 kroków bota: rozsyła bezczynnych robotników, odświeża miejsce pod bazę, dosyła SCV do przerwanych budów, opuszcza magazyny. | To czynności, których agent nie powinien musieć się uczyć. |
| [`_control_army`](../src/scbot/env/macro.py#L307-L312) | Co krok: ustala, czy trzeba odświeżyć rozkazy (zmiana trybu albo minęło 12 kroków). | Rozkazy nie są wysyłane w każdym kroku, żeby nie zalewać gry. |
| [atak](../src/scbot/env/macro.py#L314-L319) | W trybie ataku jednostki bezczynne (i wszystkie przy odświeżeniu) idą z atakiem na cel. | Nowo wyszkolone jednostki same dołączają. |
| [odwrót](../src/scbot/env/macro.py#L321-L325) | Tuż po `RETREAT` cała armia dostaje zwykły ruch do punktu zbiórki. | Ruch bez ataku, żeby jednostki nie zatrzymywały się po drodze. |
| [obrona](../src/scbot/env/macro.py#L327-L332) | W obronie, gdy są zagrożenia, armia atakuje najbliższe. | Obrona bazy nie wymaga decyzji agenta. |
| [zbiórka](../src/scbot/env/macro.py#L334-L336) | Bez zagrożeń bezczynne jednostki wracają do punktu zbiórki. | Armia nie rozchodzi się po mapie. |
| [`_attack_target`](../src/scbot/env/macro.py#L338-L363) | Cel ataku: najbliższy znany budynek wroga, potem start wroga, a gdy jest pusty, kolejne lokalizacje baz. | Gra kończy się po zniszczeniu wszystkich budynków, więc trzeba je znaleźć. |

Warunki dostępności i opis zachowania prozą: [srodowisko.md](srodowisko.md#akcje).

**Sprawdź sam.** Uruchom `play --agent random --print-every 1` i patrz na końcówkę
wiersza (`can: ...`). Zobaczysz, jak maska zmienia się z minerałami i jak `ATTACK`
znika na 30 s po każdej zmianie trybu armii.

## Przystanek 11: interfejs agenta i agenci odniesienia

Pliki: [`base.py`](../src/scbot/agents/base.py), [`simple.py`](../src/scbot/agents/simple.py).

Agent to klasa z trzema metodami:

| Metoda | Kiedy jest wołana | Co ma zrobić |
|--------|-------------------|--------------|
| [`act`](../src/scbot/agents/base.py#L20) | W każdym punkcie decyzyjnym | Zwrócić numer akcji. Dostaje obserwację, maskę i flagę `explore`. |
| [`observe`](../src/scbot/agents/base.py#L27) | Po każdym kroku w trakcie treningu | Nauczyć się z jednego przejścia. Domyślnie nic nie robi. |
| [`end_episode`](../src/scbot/agents/base.py#L46) | Po każdej grze treningowej | Np. zmniejszyć eksplorację. Domyślnie nic nie robi. |

Dwaj agenci bez uczenia:

- [`RandomAgent`](../src/scbot/agents/simple.py#L16-L25) losuje równomiernie spośród
  dostępnych akcji. To dolne odniesienie.
- [`ScriptedAgent`](../src/scbot/agents/simple.py#L28-L82) to lista priorytetów
  sprawdzanych po kolei: [armia](../src/scbot/agents/simple.py#L54-L60),
  [magazyny](../src/scbot/agents/simple.py#L62-L68),
  [SCV, koszary, Marines, ekspansja](../src/scbot/agents/simple.py#L70-L82). Pierwszy
  spełniony i dostępny warunek wygrywa. To górne odniesienie: pokazuje, że zestaw akcji
  wystarcza do wygrania z Easy.

**Sprawdź sam.** W `ScriptedAgent` zmień `attack_at_marines` z 16 na 4 i porównaj wynik
z Easy (`evaluate --agent scripted --difficulty Easy --episodes 10 --num-envs 5`).

## Przystanek 12: tabelaryczny Q-Learning

Plik: [`qlearning.py`](../src/scbot/agents/qlearning.py). Opis algorytmu jest
w [model-a-q-learning.md](model-a-q-learning.md); tu idziemy po kodzie.

**Dyskretyzacja.**

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`BinSpec`](../src/scbot/agents/qlearning.py#L33-L58) | Jedna cecha i jej progi. `n` progów daje `n + 1` koszyków. | Progi są w surowych jednostkach, żeby dało się je czytać („150 minerałów"). |
| [`DEFAULT_BINS`](../src/scbot/agents/qlearning.py#L63-L72) | Osiem cech i ich progi, razem 7200 stanów. | Tablica musi być mała, żeby stany powtarzały się wystarczająco często. |
| [`StateDiscretizer.__call__`](../src/scbot/agents/qlearning.py#L86-L93) | Bierze z obserwacji wybrane cechy, cofa skalowanie, zaokrągla i dla każdej znajduje numer koszyka. Wynik to krotka liczb, czyli stan. | Krotka jest kluczem słownika, którym jest tablica Q. |

**Agent.**

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`QLearningConfig`](../src/scbot/agents/qlearning.py#L114-L122) | Hiperparametry: α, γ, harmonogram ε, wartość początkowa. | Zapisują się razem z tablicą. |
| [`__init__`](../src/scbot/agents/qlearning.py#L130-L141) | Tablica `q` i licznik odwiedzin `visits` to słowniki `stan → 8 liczb`. Na starcie puste. | Pamiętane są tylko stany, które faktycznie wystąpiły. |
| [`epsilon_at`](../src/scbot/agents/qlearning.py#L150-L154) | ε maleje liniowo z liczbą ukończonych gier, od wartości początkowej do końcowej. | Na początku eksploracja, potem korzystanie z tablicy. |
| [`act`](../src/scbot/agents/qlearning.py#L156-L162) | Z prawdopodobieństwem ε losuje dostępną akcję, w przeciwnym razie bierze zachłanną. | Losuje tylko spośród akcji z maski. |
| [`greedy_action`](../src/scbot/agents/qlearning.py#L164-L171) | Najwyższe Q wśród dostępnych akcji. Stan nieznany albo remis rozstrzyga losowanie. | Bez losowania remisów agent zawsze wybierałby akcję o najniższym numerze. |
| [stan i wiersz](../src/scbot/agents/qlearning.py#L185-L187) | Zamienia obserwację na stan i bierze jego wiersz z tablicy (tworzy go, jeśli nie istnieje). | |
| [cel uczenia](../src/scbot/agents/qlearning.py#L189-L198) | Cel to nagroda plus zdyskontowana najlepsza wartość następnego stanu, liczona tylko po dostępnych tam akcjach. Dyskonto to `gamma ** intervals_elapsed`. Po końcu gry cel to sama nagroda. | Kroki mają różną długość, więc dyskonto musi zależeć od czasu. |
| [aktualizacja](../src/scbot/agents/qlearning.py#L200-L202) | Przesuwa `Q(s, a)` o ułamek α w stronę celu i zwiększa licznik odwiedzin. | To jest cała reguła Q-Learningu. |
| [`_row`](../src/scbot/agents/qlearning.py#L207-L213) | Nowy stan dostaje wiersz wypełniony wartością `initial_q`. | Wartość początkowa decyduje, jak agent traktuje nieznane akcje. |
| [`save`](../src/scbot/agents/qlearning.py#L217-L244) | Zapisuje stany, wartości, odwiedziny i metadane do `.npz`, najpierw do pliku tymczasowego. | Przerwany zapis nie niszczy poprzedniej tablicy. |
| [`load`](../src/scbot/agents/qlearning.py#L246-L265) | Wczytuje plik i odmawia, jeśli lista akcji jest inna niż obecna. | Kolumny tablicy odpowiadają akcjom. |

**Sprawdź sam.** `tests/test_qlearning.py` zawiera test
`test_learns_the_better_action_on_a_two_step_task`: agent uczy się na dwukrokowym
zadaniu bez gry. Uruchom go i prześledź w debuggerze jedno wywołanie `observe`.
Zapisaną tablicę obejrzysz kodem z [model-a-q-learning.md](model-a-q-learning.md#plik-tablicy).

## Przystanek 13: skrypt treningowy i jego pliki

Pliki: [`train_q.py`](../src/scbot/train_q.py), [`run_logging.py`](../src/scbot/run_logging.py).

`train_q` nie zawiera pętli gry. Składa agenta, środowiska i trzy funkcje, a pętlę
z przystanku 3 woła raz.

| Linie | Co się dzieje | Dlaczego |
|-------|---------------|----------|
| [`parse_args`](../src/scbot/train_q.py#L29-L74) | Opcje treningu, Q-Learningu, zapisu i środowiska. | Opis każdej jest w [runbooku 04](../runbooks/04-trening-q-learning.md). |
| [nowy albo wznowiony](../src/scbot/train_q.py#L94-L115) | Z `--resume` wczytuje tablicę; bez niego odmawia nadpisania istniejącej. | Żeby nie stracić wytrenowanej tablicy przez pomyłkę w nazwie. |
| [numeracja](../src/scbot/train_q.py#L117-L120) | Pierwszy epizod to następny po ostatnim zapisanym w `episodes.csv`. | Wznowiony trening kontynuuje numerację. |
| [`config.json`](../src/scbot/train_q.py#L122-L135) | Zapisuje ustawienia środowiska, agenta i dyskretyzacji. | Żeby po miesiącu było wiadomo, na czym run był liczony. |
| [`replay_path`](../src/scbot/train_q.py#L147-L150) | Co 50. gra dostaje ścieżkę powtórki. | |
| [`on_step`](../src/scbot/train_q.py#L152-L154) | Co 10. decyzja trafia do `steps.jsonl`. | Surowe odczyty do późniejszej analizy. |
| [`on_episode`](../src/scbot/train_q.py#L156-L170) | Po każdej grze: wiersz do CSV i TensorBoard, wiersz na ekran, zapis tablicy, co 25 gier checkpoint. | Tablica jest na dysku po każdej grze, więc przerwanie niczego nie traci. |
| [`run_episodes`](../src/scbot/train_q.py#L172-L185) | Tworzy tyle środowisk, ile wynosi `--num-envs`, i oddaje sterowanie pętli epizodów. | |
| [przerwanie](../src/scbot/train_q.py#L186-L192) | Ctrl+C zapisuje tablicę; środowiska są zamykane zawsze. | |

W `run_logging.py`: [`EPISODE_COLUMNS`](../src/scbot/run_logging.py#L14) to kolumny
`episodes.csv`, [`episode_row`](../src/scbot/run_logging.py#L39) składa jeden wiersz,
a [`RunLogger`](../src/scbot/run_logging.py#L71) pisze do CSV, JSONL i TensorBoard.

**Sprawdź sam.** Krótki trening na dwóch grach naraz, z dwuminutowymi grami:

```bash
docker compose run --rm sc2 python -m scbot.train_q --run-name proba --episodes 4 --num-envs 2 --max-game-minutes 2
```

Potem otwórz `runs/proba/episodes.csv` i `runs/proba/steps.jsonl` i znajdź w nich pola
opisane wyżej.

## Przystanek 14: narzędzia

| Plik | Do czego | Najważniejsze miejsce |
|------|----------|-----------------------|
| [`evaluate.py`](../src/scbot/evaluate.py) | Seria gier bez uczenia i podsumowanie z przedziałem ufności | [`main`](../src/scbot/evaluate.py#L28) używa tej samej pętli co trening, z `learn=False` |
| [`report.py`](../src/scbot/report.py) | Tabela z przebiegu treningu w blokach gier | [`summarise_blocks`](../src/scbot/report.py#L24) |
| [`doctor.py`](../src/scbot/doctor.py) | Diagnostyka środowiska | [`check_game`](../src/scbot/doctor.py#L93) i [`check_launch`](../src/scbot/doctor.py#L141) |

## Testy jako dokumentacja

Każdy test opisuje w nazwie jedno zachowanie. Gdy nie jesteś pewien, co kod gwarantuje,
zacznij od testów.

| Plik testów | Którego przystanku dotyczy | Wymaga gry |
|-------------|----------------------------|------------|
| `tests/test_agents_and_runner.py` | 3 i 11 | nie |
| `tests/test_decision_points.py` | 7 | nie |
| `tests/test_observation.py` | 8 | nie |
| `tests/test_reward.py` | 9 | nie |
| `tests/test_macro_reserve.py`, `tests/test_macro_expansion.py` | 10 | nie |
| `tests/test_qlearning.py` | 12 | nie |
| `tests/test_report.py` | 14 | nie |
| `tests/test_env_integration.py` | 4, 5, 6 i 10 razem | tak |
| `tests/test_docs_links.py` | ten dokument | nie |

## Słowniczek

| Pojęcie | Znaczenie w tym projekcie |
|---------|---------------------------|
| Pętla gry | Najmniejszy krok symulacji StarCraft II, 1/22,4 s czasu gry. |
| Krok bota | 8 pętli gry. Tak często python-sc2 woła `on_step`. |
| Interwał decyzyjny | 4 kroki bota, 1,43 s czasu gry. Najmniejszy odstęp między decyzjami. |
| Punkt decyzyjny | Chwila, w której agent jest pytany o akcję. Nie każdy interwał nim jest. |
| Akcja makro | Jedna z 8 decyzji wysokiego poziomu, np. „zbuduj koszary". |
| Maska akcji | 8 wartości logicznych: które akcje da się teraz wykonać. |
| Warstwa makro (skryptowa) | Kod, który akcję makro zamienia na rozkazy dla jednostek. |
| Epizod | Jedna gra od startu do wygranej, przegranej albo limitu czasu. |
| Proces gry (worker) | Osobny proces Pythona, który prowadzi grę i rozmawia ze środowiskiem przez potok. |
| Run | Jeden trening: katalog `runs/<nazwa>/` z tablicą, logami i powtórkami. |
