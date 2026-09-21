from collections.abc import Callable

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.game.models import ActionType, GamePlayer, GameSession
from app.game.roles import get_role_definition

TARGETS_PER_PAGE = 8

ACTION_CODES = {
    ActionType.MAFIA_VOTE: "m",
    ActionType.INSPECT: "i",
    ActionType.COMMISSIONER_SHOT: "s",
    ActionType.HEAL: "h",
    ActionType.MANIAC_KILL: "k",
    ActionType.BLOCK: "b",
    ActionType.WATCH: "w",
}
CODE_ACTIONS = {value: key for key, value in ACTION_CODES.items()}


class GameLobbyCallback(CallbackData, prefix="l"):
    game: str
    phase: int
    action: str


class NightActionCallback(CallbackData, prefix="n"):
    game: str
    phase: int
    action: str
    target: int


class NightPageCallback(CallbackData, prefix="np"):
    game: str
    phase: int
    action: str
    page: int


class DayVoteCallback(CallbackData, prefix="d"):
    game: str
    phase: int
    target: int


class DayPageCallback(CallbackData, prefix="dp"):
    game: str
    phase: int
    page: int


class RevengeCallback(CallbackData, prefix="r"):
    game: str
    phase: int
    target: int


class RevengePageCallback(CallbackData, prefix="rp"):
    game: str
    phase: int
    page: int


def lobby_keyboard(session: GameSession, bot_username: str | None = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    def callback(action: str) -> GameLobbyCallback:
        return GameLobbyCallback(
            game=session.callback_token,
            phase=session.phase_number,
            action=action,
        )

    builder.button(text="➕ Присоединиться", callback_data=callback("join"))
    builder.button(text="🚪 Покинуть игру", callback_data=callback("leave"))
    builder.button(text="✅ Я готов", callback_data=callback("ready"))
    builder.button(text="👥 Список игроков", callback_data=callback("players"))
    builder.button(text="🌙 Начать досрочно", callback_data=callback("start"))
    builder.button(text="🛑 Отменить игру", callback_data=callback("cancel"))
    if bot_username:
        builder.button(
            text="💬 Активировать личные сообщения",
            url=f"https://t.me/{bot_username}?start=mafia_{session.callback_token}",
        )
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def night_target_keyboard(
    session: GameSession,
    actor_id: int,
    action_type: ActionType,
    page: int = 0,
) -> InlineKeyboardMarkup:
    actor = session.require_player(actor_id)
    targets: list[GamePlayer] = []
    for target in session.alive_players:
        if target.user_id == actor_id and action_type is not ActionType.HEAL:
            continue
        if (
            action_type is ActionType.HEAL
            and target.user_id == actor_id
            and actor.metadata.get("self_heal_used")
        ):
            continue
        if (
            action_type is ActionType.MAFIA_VOTE
            and target.role is not None
            and actor.role is not None
            and get_role_definition(target.role).faction == get_role_definition(actor.role).faction
        ):
            continue
        targets.append(target)

    builder = InlineKeyboardBuilder()
    action_code = ACTION_CODES[action_type]
    for target in _page(targets, page):
        builder.button(
            text=target.display_name[:32],
            callback_data=NightActionCallback(
                game=session.callback_token,
                phase=session.phase_number,
                action=action_code,
                target=target.user_id,
            ),
        )
    builder.adjust(2)
    _add_pagination(
        builder,
        page,
        len(targets),
        lambda target_page: NightPageCallback(
            game=session.callback_token,
            phase=session.phase_number,
            action=action_code,
            page=target_page,
        ),
    )
    return builder.as_markup()


def day_vote_keyboard(session: GameSession, page: int = 0) -> InlineKeyboardMarkup:
    targets = session.alive_players
    builder = InlineKeyboardBuilder()
    for target in _page(targets, page):
        builder.button(
            text=target.display_name[:32],
            callback_data=DayVoteCallback(
                game=session.callback_token,
                phase=session.phase_number,
                target=target.user_id,
            ),
        )
    builder.adjust(2)
    _add_pagination(
        builder,
        page,
        len(targets),
        lambda target_page: DayPageCallback(
            game=session.callback_token,
            phase=session.phase_number,
            page=target_page,
        ),
    )
    builder.row(
        _button(
            "⚪ Воздержаться",
            DayVoteCallback(
                game=session.callback_token,
                phase=session.phase_number,
                target=0,
            ),
        )
    )
    return builder.as_markup()


def revenge_keyboard(
    session: GameSession,
    best_friend_id: int,
    page: int = 0,
) -> InlineKeyboardMarkup:
    del best_friend_id
    targets = session.alive_players
    builder = InlineKeyboardBuilder()
    for target in _page(targets, page):
        builder.button(
            text=target.display_name[:32],
            callback_data=RevengeCallback(
                game=session.callback_token,
                phase=session.phase_number,
                target=target.user_id,
            ),
        )
    builder.adjust(2)
    _add_pagination(
        builder,
        page,
        len(targets),
        lambda target_page: RevengePageCallback(
            game=session.callback_token,
            phase=session.phase_number,
            page=target_page,
        ),
    )
    builder.row(
        _button(
            "Никого не забирать",
            RevengeCallback(
                game=session.callback_token,
                phase=session.phase_number,
                target=0,
            ),
        )
    )
    return builder.as_markup()


def _page(items: list[GamePlayer], page: int) -> list[GamePlayer]:
    start = max(0, page) * TARGETS_PER_PAGE
    return items[start : start + TARGETS_PER_PAGE]


def _add_pagination(
    builder: InlineKeyboardBuilder,
    page: int,
    total: int,
    callback_factory: Callable[[int], CallbackData],
) -> None:
    buttons: list[InlineKeyboardButton] = []
    if page > 0:
        buttons.append(_button("⬅️", callback_factory(page - 1)))
    if (page + 1) * TARGETS_PER_PAGE < total:
        buttons.append(_button("➡️", callback_factory(page + 1)))
    if buttons:
        builder.row(*buttons)


def _button(text: str, callback_data: CallbackData) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=callback_data.pack())
