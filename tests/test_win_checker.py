from app.game.models import Faction, GamePlayer, GameSession, RoleKey
from app.game.win_checker import WinChecker


def session_with_roles(*roles: RoleKey) -> GameSession:
    session = GameSession(chat_id=-100, created_by=1)
    session.players = {
        index: GamePlayer(index, str(index), role=role) for index, role in enumerate(roles, start=1)
    }
    return session


def test_town_wins_when_mafia_and_maniac_are_gone() -> None:
    session = session_with_roles(RoleKey.CIVILIAN, RoleKey.DOCTOR)
    result = WinChecker().check(session)
    assert result.finished
    assert result.winner is Faction.TOWN


def test_mafia_wins_on_parity() -> None:
    session = session_with_roles(RoleKey.MAFIA_BOSS, RoleKey.CIVILIAN)
    result = WinChecker().check(session)
    assert result.finished
    assert result.winner is Faction.MAFIA


def test_maniac_wins_as_last_survivor() -> None:
    session = session_with_roles(RoleKey.MANIAC)
    result = WinChecker().check(session)
    assert result.finished
    assert result.winner is RoleKey.MANIAC


def test_suicide_wins_when_lynched() -> None:
    session = session_with_roles(RoleKey.SUICIDE, RoleKey.MAFIA_BOSS, RoleKey.CIVILIAN)
    result = WinChecker().check_lynch(session, 1)
    assert result.finished
    assert result.winner is RoleKey.SUICIDE
