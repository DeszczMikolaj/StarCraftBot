"""Supply Depots must not be offered when plenty of free supply is already secured."""

from types import SimpleNamespace

from sc2.ids.unit_typeid import UnitTypeId

from scbot.config import MacroConfig
from scbot.env.macro import MacroExecutor


class FakeBot:
    """The python-sc2 calls ``spare_supply`` relies on."""

    def __init__(self, supply_left: int, depots_under_construction: int, depots_ordered: int):
        self.supply_left = supply_left
        self._under_construction = depots_under_construction
        self._ordered = depots_ordered

    def structures(self, unit_type: UnitTypeId) -> SimpleNamespace:
        assert unit_type is UnitTypeId.SUPPLYDEPOT
        return SimpleNamespace(not_ready=SimpleNamespace(amount=self._under_construction))

    def worker_en_route_to_build(self, unit_type: UnitTypeId) -> int:
        assert unit_type is UnitTypeId.SUPPLYDEPOT
        return self._ordered


def spare_supply(supply_left: int, under_construction: int = 0, ordered: int = 0) -> int:
    bot = FakeBot(supply_left, under_construction, ordered)
    return MacroExecutor(bot, MacroConfig()).spare_supply()


def test_spare_supply_is_the_free_supply_when_no_depot_is_coming():
    assert spare_supply(supply_left=5) == 5


def test_depots_on_the_way_count_as_supply_already_secured():
    assert spare_supply(supply_left=3, under_construction=1) == 3 + 8
    assert spare_supply(supply_left=3, under_construction=1, ordered=1) == 3 + 16


def test_default_limit_leaves_room_for_two_depots_of_headroom():
    limit = MacroConfig().max_spare_supply

    assert spare_supply(supply_left=0, under_construction=1) < limit  # a second depot is fine
    assert spare_supply(supply_left=0, under_construction=2) >= limit  # a third is not
    assert spare_supply(supply_left=20) >= limit  # plenty of room: no depot needed
