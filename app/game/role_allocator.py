from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.game.models import RoleKey


@dataclass(frozen=True, slots=True)
class RoleBalanceConfig:
    min_players: int
    max_players: int
    mafia_ratio: float
    mafia_minimum: int
    role_unlocks: dict[RoleKey, int]

    @classmethod
    def from_yaml(cls, path: Path) -> RoleBalanceConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            min_players=int(raw["min_players"]),
            max_players=int(raw["max_players"]),
            mafia_ratio=float(raw["mafia_ratio"]),
            mafia_minimum=int(raw["mafia_minimum"]),
            role_unlocks={RoleKey(key): int(value) for key, value in raw["role_unlocks"].items()},
        )


class RoleAllocator:
    def __init__(self, config: RoleBalanceConfig, rng: random.Random | None = None) -> None:
        self.config = config
        self.rng = rng or random.SystemRandom()

    def build_deck(self, player_count: int) -> list[RoleKey]:
        if not self.config.min_players <= player_count <= self.config.max_players:
            raise ValueError(
                f"Допустимо от {self.config.min_players} до {self.config.max_players} игроков"
            )

        mafia_slots = max(
            self.config.mafia_minimum,
            math.ceil(player_count * self.config.mafia_ratio),
        )
        deck: list[RoleKey] = [RoleKey.MAFIA_BOSS]

        if self._unlocked(RoleKey.LAWYER, player_count) and mafia_slots >= 3:
            deck.append(RoleKey.LAWYER)
        deck.extend([RoleKey.MAFIA] * (mafia_slots - len(deck)))

        special_order = (
            RoleKey.COMMISSIONER,
            RoleKey.DOCTOR,
            RoleKey.WARRANT_OFFICER,
            RoleKey.LUCKY,
            RoleKey.BEST_FRIEND,
            RoleKey.MANIAC,
            RoleKey.SNOW_WHITE,
            RoleKey.HOMELESS,
            RoleKey.SUICIDE,
        )
        for role in special_order:
            if self._unlocked(role, player_count) and len(deck) < player_count:
                deck.append(role)

        deck.extend([RoleKey.CIVILIAN] * (player_count - len(deck)))
        self.rng.shuffle(deck)
        return deck

    def assign(self, user_ids: list[int]) -> dict[int, RoleKey]:
        deck = self.build_deck(len(user_ids))
        shuffled_users = list(user_ids)
        self.rng.shuffle(shuffled_users)
        return dict(zip(shuffled_users, deck, strict=True))

    def _unlocked(self, role: RoleKey, player_count: int) -> bool:
        threshold = self.config.role_unlocks.get(role)
        return threshold is not None and player_count >= threshold
