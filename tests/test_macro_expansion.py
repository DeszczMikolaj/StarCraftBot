"""EXPAND must only be offered for a base location where a Command Center can be built."""

import asyncio
from types import SimpleNamespace

from sc2.position import Point2

from scbot.config import MacroConfig
from scbot.env.macro import MacroExecutor

# The four base locations of Simple64, seen from the bottom-right start position.
START = Point2((59.5, 27.5))
NATURAL = Point2((25.5, 23.5))
ENEMY_NATURAL = Point2((62.5, 64.5))
ENEMY_START = Point2((28.5, 60.5))


class Townhalls(list):
    @property
    def amount(self) -> int:
        return len(self)


class FakeBot:
    """The python-sc2 calls the expansion search relies on."""

    EXPANSION_GAP_THRESHOLD = 15

    def __init__(self, townhalls, blocked=(), unreachable=()) -> None:
        self.start_location = START
        self.enemy_start_locations = [ENEMY_START]
        self.expansion_locations_list = [START, NATURAL, ENEMY_NATURAL, ENEMY_START]
        self.townhalls = Townhalls(townhalls)
        self.placement_queries: list[Point2] = []
        self._blocked = set(blocked)
        self._unreachable = set(unreachable)
        self.client = SimpleNamespace(query_pathing=self._query_pathing)

    async def can_place_single(self, unit_type, position: Point2) -> bool:
        self.placement_queries.append(position)
        return position not in self._blocked

    async def _query_pathing(self, start: Point2, end: Point2) -> float | None:
        return None if end in self._unreachable else start.distance_to(end)


def expansion_site(bot: FakeBot, **config) -> Point2 | None:
    macro = MacroExecutor(bot, MacroConfig(**config))
    asyncio.run(macro.refresh_expansion_site())
    return macro.expansion_site


def test_the_free_base_on_our_side_of_the_map_is_chosen():
    assert expansion_site(FakeBot(townhalls=[START])) == NATURAL


def test_bases_on_the_enemy_side_are_never_offered():
    # Our natural is taken; the only free locations belong to the enemy's half.
    assert expansion_site(FakeBot(townhalls=[START, NATURAL])) is None


def test_a_blocked_location_is_not_offered():
    assert expansion_site(FakeBot(townhalls=[START], blocked=[NATURAL])) is None


def test_an_unreachable_location_is_not_offered():
    assert expansion_site(FakeBot(townhalls=[START], unreachable=[NATURAL])) is None


def test_no_search_when_the_base_limit_is_reached():
    bot = FakeBot(townhalls=[START])

    assert expansion_site(bot, max_townhalls=1) is None
    assert bot.placement_queries == []


def test_no_search_without_a_base_to_expand_from():
    bot = FakeBot(townhalls=[])

    assert expansion_site(bot) is None
    assert bot.placement_queries == []
