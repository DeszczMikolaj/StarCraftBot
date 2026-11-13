# 05. Ewaluacja i powtórki

**Cel:** zmierzyć skuteczność agenta przeciw wbudowanej SI na serii gier bez uczenia
i zapisać gry do obejrzenia.

**Wymagania:** zbudowany obraz ([runbook 01](01-srodowisko-docker.md)); dla agenta `q`
zapisana tablica Q ([runbook 04](04-trening-q-learning.md)).

## Kroki

### 1. Uruchom serię gier

```bash
docker compose run --rm sc2 python -m scbot.evaluate --agent q --model runs/q_baseline/qtable.npz --difficulty Easy --episodes 30 --num-envs 10 --out runs/q_baseline/eval_easy.json
```

| Opcja | Znaczenie |
|-------|-----------|
| `--agent` | `q` (tablica z `--model`), `scripted` albo `random`. |
| `--difficulty` | Poziom wbudowanej SI: `VeryEasy`, `Easy`, `Medium`, `MediumHard`, `Hard`, `Harder`, `VeryHard`. |
| `--episodes` | Liczba gier. |
| `--num-envs` | Ile gier naraz. Każda zajmuje około 1,5 rdzenia i 0,5–0,8 GB pamięci. |
| `--seed` | Bazowe ziarno. Gra numer `n` dostaje ziarno `seed + n`. |
| `--out` | Plik JSON z wynikami wszystkich gier. |
| `--replay-dir` | Katalog, do którego trafi powtórka każdej gry. |

W ewaluacji agent Q-Learning gra zachłannie (bez eksploracji) i nie zmienia tablicy.

### 2. Odczytaj podsumowanie

```text
games:       12
W / L / T:   12 / 0 / 0
win rate:    100.0%  (95% CI 75.7% - 100.0%)
mean return: ...
mean game:   5.3 min
mean killed / lost value: 3360 / 271
```

- `W / L / T` to wygrane, przegrane i remisy. Remis oznacza osiągnięcie limitu czasu gry
  (domyślnie 20 minut, opcja `--max-game-minutes`).
- `95% CI` to przedział ufności Wilsona dla odsetka wygranych. Przy kilkunastu grach jest
  szeroki. Do porównywania modeli zakładaj 50–100 gier, tak jak w założeniach turnieju.
- `killed / lost value` to średnia wartość zniszczonych jednostek wroga i własnych strat.

### 3. Porównaj z agentami odniesienia

Te same komendy z `--agent scripted` i `--agent random` dają punkt odniesienia. Wyniki
zebrane w projekcie są w [docs/wyniki.md](../docs/wyniki.md).

## Powtórki

Zapis wszystkich gier ewaluacji:

```bash
docker compose run --rm sc2 python -m scbot.evaluate --agent scripted --difficulty Easy --episodes 4 --replay-dir replays/scripted_easy
```

Zapis pojedynczej gry z podglądem odczytów:

```bash
docker compose run --rm sc2 python -m scbot.play --agent scripted --replay replays/gra.SC2Replay
```

Trening zapisuje powtórkę co 50. grę do `runs/<nazwa>/replays/` (opcja `--replay-every`).

Powtórki ogląda się w kliencie Windows, patrz [runbook 02](02-klient-windows.md). Wersja
linuksowa gry nie ma interfejsu graficznego.

## Weryfikacja

- Liczba gier w podsumowaniu zgadza się z `--episodes`.
- Plik podany w `--out` istnieje i zawiera pole `episodes` z listą gier.
