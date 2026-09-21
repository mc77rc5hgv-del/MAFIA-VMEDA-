from app.bot.keyboards.game import day_vote_keyboard, night_target_keyboard
from app.game.models import ActionType, GamePlayer, GameSession, RoleKey


def player(user_id: int, role: RoleKey) -> GamePlayer:
    return GamePlayer(user_id, f"Игрок {user_id}", role=role)


def callback_targets(markup: object) -> set[int]:
    keyboard = markup.inline_keyboard  # type: ignore[attr-defined]
    return {
        int(button.callback_data.rsplit(":", maxsplit=1)[1])
        for row in keyboard
        for button in row
        if button.callback_data is not None
    }


def test_mafia_keyboard_hides_teammates() -> None:
    session = GameSession(chat_id=-100, created_by=1, phase_number=1)
    session.players = {
        1: player(1, RoleKey.MAFIA_BOSS),
        2: player(2, RoleKey.MAFIA),
        3: player(3, RoleKey.LAWYER),
        4: player(4, RoleKey.CIVILIAN),
    }

    markup = night_target_keyboard(session, 1, ActionType.MAFIA_VOTE)

    assert callback_targets(markup) == {4}


def test_day_keyboard_supports_fifty_players_and_abstention() -> None:
    session = GameSession(chat_id=-1001234567890, created_by=1, phase_number=12)
    session.players = {
        user_id: player(user_id, RoleKey.CIVILIAN) for user_id in range(1, 51)
    }

    markup = day_vote_keyboard(session)

    buttons = [button for row in markup.inline_keyboard for button in row]
    assert len(buttons) == 51
    assert 0 in callback_targets(markup)
