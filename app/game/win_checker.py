from app.game.models import Faction, GameSession, RoleKey, WinResult
from app.game.roles import get_role_definition


class WinChecker:
    def check(self, session: GameSession) -> WinResult:
        alive = session.alive_players
        mafia = [
            player
            for player in alive
            if player.role is not None and get_role_definition(player.role).faction is Faction.MAFIA
        ]
        maniac_alive = any(player.role is RoleKey.MANIAC for player in alive)
        non_mafia = [player for player in alive if player not in mafia]

        if len(alive) == 1 and maniac_alive:
            return WinResult(True, RoleKey.MANIAC, "Маньяк остался единственным выжившим")
        if mafia and len(mafia) >= len(non_mafia):
            return WinResult(True, Faction.MAFIA, "Мафия сравнялась числом с остальными")
        if not mafia and not maniac_alive:
            return WinResult(True, Faction.TOWN, "Все представители мафии и Маньяк устранены")
        return WinResult(False)

    def check_lynch(self, session: GameSession, lynched_user_id: int) -> WinResult:
        player = session.require_player(lynched_user_id)
        if player.role is RoleKey.SUICIDE:
            return WinResult(True, RoleKey.SUICIDE, "Самоубийца победил на дневном голосовании")
        return self.check(session)
