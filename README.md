# StarCraftBot

Agenci uczący się grać w StarCraft II na poziomie decyzji makro. Projekt z przedmiotu
Sieci neuronowe (Politechnika Wrocławska): porównanie trzech podejść o rosnącej
złożoności na wspólnym środowisku.

| Model | Podejście | Stan |
|-------|-----------|------|
| A | Tabelaryczny Q-Learning (bez sieci, punkt odniesienia) | Działa: 88% wygranych z Easy po 500 grach treningowych, wobec 61% agenta losowego ([wyniki](docs/wyniki.md), [opis](docs/model-a-q-learning.md)) |
| B | Deep Q-Learning (DQN) | Do zrobienia |
| C | Proximal Policy Optimization (PPO) | Do zrobienia |

Wszystkie modele grają Terranami przeciw Terranom, dostają ten sam wektor 24 cech
i wybierają jedną z 8 akcji makro (np. „zbuduj koszary", „szkol Marines", „atakuj").
Wykonaniem akcji zajmuje się wspólna warstwa skryptowa.

## Szybki start

Potrzebny jest Docker Desktop. Pierwsze budowanie pobiera linuksową wersję gry (około
4 GB), co oznacza akceptację licencji
[Blizzard AI and Machine Learning License](https://blzdistsc2-a.akamaihd.net/AI_AND_MACHINE_LEARNING_LICENSE.html).

```bash
docker compose build sc2
```

```bash
docker compose run --rm sc2 python -m scbot.doctor --launch
```

```bash
docker compose run --rm sc2 python -m scbot.play --agent scripted --difficulty VeryEasy
```

Pierwsza komenda buduje obraz z grą bez interfejsu graficznego, druga sprawdza
środowisko i startuje grę na próbę, trzecia rozgrywa pełną grę i wypisuje odczyty.
Szczegóły: [runbook 01](runbooks/01-srodowisko-docker.md) i [runbook 03](runbooks/03-pierwsza-gra.md).

Trening i ocena Modelu A:

```bash
docker compose run --rm sc2 python -m scbot.train_q --run-name q_baseline --difficulty Easy --episodes 500 --epsilon-decay-episodes 350 --initial-q 0.5 --num-envs 12
```

```bash
docker compose run --rm sc2 python -m scbot.evaluate --agent q --model runs/q_baseline/qtable.npz --difficulty Easy --episodes 30 --num-envs 10
```

## Gdzie co jest

| Katalog | Zawartość |
|---------|-----------|
| [`runbooks/`](runbooks/README.md) | Instrukcje krok po kroku: środowisko, pierwsza gra, trening, ewaluacja, testy, problemy |
| [`docs/`](docs/README.md) | Dokumentacja: architektura, środowisko, Model A, wyniki, rozwijanie, status |
| [`docs/przewodnik-po-kodzie.md`](docs/przewodnik-po-kodzie.md) | Punkt wejścia do czytania kodu: krok po kroku, z odnośnikami do linii |
| `src/scbot/env/` | Wspólne środowisko: obserwacje, akcje makro, nagroda, warstwa skryptowa, proces gry |
| `src/scbot/agents/` | Interfejs agenta, agent losowy i skryptowy, tabelaryczny Q-Learning |
| `src/scbot/*.py` | Skrypty: `doctor`, `play`, `train_q`, `evaluate` |
| `tests/` | Testy jednostkowe i integracyjne (z prawdziwą grą) |
| `docker/`, `compose.yaml` | Obraz z grą headless |
| `examples/` | Najmniejszy przykład użycia środowiska |

## Wymagania

- Docker Desktop (Windows, backend WSL 2) lub Docker z Compose (Linux), około 25 GB na dysku.
- Opcjonalnie [uv](https://docs.astral.sh/uv/) i Python 3.12 do pracy poza kontenerem
  (testy jednostkowe, linter, klient Windows). Zależności: `uv sync` albo
  `pip install -r requirements.txt`.

## Testy

```bash
uv run pytest
```

```bash
docker compose run --rm sc2 pytest -m sc2
```

Pierwsza komenda uruchamia testy jednostkowe, druga testy z prawdziwą grą.

## Źródła

- Punkt wyjścia: film [A.I. Learns to Play Starcraft 2](https://www.youtube.com/watch?v=q59wap1ELQ4)
  i kod [Sentdex/SC2RL](https://github.com/Sentdex/SC2RL). Różnice opisuje
  [docs/architektura.md](docs/architektura.md).
- Biblioteka sterująca grą: [BurnySC2/python-sc2](https://github.com/BurnySC2/python-sc2).
- Linuksowe wydania gry i mapy: [Blizzard/s2client-proto](https://github.com/Blizzard/s2client-proto).
