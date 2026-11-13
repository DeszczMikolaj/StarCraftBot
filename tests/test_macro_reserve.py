"""The macro layer must not let the agent spend minerals promised to an ordered building."""

from types import SimpleNamespace

from sc2.ids.unit_typeid import UnitTypeId

from scbot.config import MacroConfig
from scbot.env.macro import MacroExecutor

COSTS = {
    UnitTypeId.SCV: 50,
    UnitTypeId.MARINE: 50,
    UnitTypeId.SUPPLYDEPOT: 100,
    UnitTypeId.BARRACKS: 150,
    UnitTypeId.COMMANDCENTER: 400,
}


class FakeBot:
    """The few python-sc2 calls the affordability checks rely on."""

    def __init__(self, minerals: int, en_route: dict | None = None, supply_left: int = 10) -> None:
        self.minerals = minerals
        self.supply_left = supply_left
        self._en_route = en_route or {}

    def calculate_cost(self, unit_type: UnitTypeId) -> SimpleNamespace:
        return SimpleNamespace(minerals=COSTS[unit_type], vespene=0)

    def worker_en_route_to_build(self, unit_type: UnitTypeId) -> int:
        return self._en_route.get(unit_type, 0)

    def can_afford(self, unit_type: UnitTypeId) -> bool:
        needs_supply = unit_type in (UnitTypeId.SCV, UnitTypeId.MARINE)
        return self.minerals >= COSTS[unit_type] and (not needs_supply or self.supply_left >= 1)


def executor(minerals: int, en_route: dict | None = None, supply_left: int = 10) -> MacroExecutor:
    return MacroExecutor(FakeBot(minerals, en_route, supply_left), MacroConfig())


def test_nothing_is_reserved_without_pending_orders():
    macro = executor(minerals=150)

    assert macro.reserved_minerals() == 0
    assert macro.can_afford(UnitTypeId.BARRACKS)
    assert not macro.can_afford(UnitTypeId.COMMANDCENTER)
    assert macro.affordable_count(UnitTypeId.MARINE) == 3


def test_an_scv_walking_to_a_building_site_reserves_its_cost():
    macro = executor(minerals=450, en_route={UnitTypeId.COMMANDCENTER: 1})

    assert macro.reserved_minerals() == 400
    assert macro.free_minerals() == 50
    assert macro.can_afford(UnitTypeId.MARINE)
    assert not macro.can_afford(UnitTypeId.SUPPLYDEPOT)  # 450 in the bank, but 400 are spoken for
    assert macro.affordable_count(UnitTypeId.MARINE) == 1


def test_reserves_add_up_over_all_ordered_buildings():
    macro = executor(minerals=500, en_route={UnitTypeId.BARRACKS: 2, UnitTypeId.SUPPLYDEPOT: 1})

    assert macro.reserved_minerals() == 2 * 150 + 100
    assert macro.affordable_count(UnitTypeId.SCV) == 2


def test_a_reserve_larger_than_the_bank_blocks_all_spending():
    macro = executor(minerals=120, en_route={UnitTypeId.BARRACKS: 1})

    assert macro.free_minerals() == -30
    assert not macro.can_afford(UnitTypeId.SCV)
    assert macro.affordable_count(UnitTypeId.SCV) == 0


def test_supply_still_limits_units_when_minerals_are_free():
    macro = executor(minerals=300, supply_left=0)

    assert not macro.can_afford(UnitTypeId.MARINE)
    assert macro.can_afford(UnitTypeId.SUPPLYDEPOT)
