from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.game.models import ActionType, GameSession
from app.game.roles import get_role_definition


class GameLobbyCallback(CallbackData, prefix="game_lobby"):
    action: str


class NightActionCallback(CallbackData, prefix="night"):
    chat_id: int
    phase_number: int
    action: str
    target_id: int


class DayVoteCallback(CallbackData, prefix="day_vote"):
    chat_id: int
    phase_number: int
    target_id: int


class RevengeCallback(CallbackData, prefix="revenge"):
    chat_id: int
    target_id: int


def lobby_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Участвовать", callback_data=GameLobbyCallback(action="join"))
    builder.button(text="🚪 Выйти", callback_data=GameLobbyCallback(action="leave"))
    builder.button(text="👥 Игроки", callback_data=GameLobbyCallback(action="players"))
    builder.button(text="🌙 Начать игру", callback_data=GameLobbyCallback(action="start"))
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def night_target_keyboard(
    session: GameSession,
    actor_id: int,
    action_type: ActionType,
) -> InlineKeyboardMarkup:
    actor = session.require_player(actor_id)
    builder = InlineKeyboardBuilder()
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
            and get_role_definition(target.role).faction
            == get_role_definition(actor.role).faction
        ):
            continue
        builder.button(
            text=target.display_name[:32],
            callback_data=NightActionCallback(
                chat_id=session.chat_id,
                phase_number=session.phase_number,
                action=action_type.value,
                target_id=target.user_id,
            ),
        )
    builder.adjust(2)
    return builder.as_markup()


def day_vote_keyboard(session: GameSession) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for target in session.alive_players:
        builder.button(
            text=target.display_name[:32],
            callback_data=DayVoteCallback(
                chat_id=session.chat_id,
                phase_number=session.phase_number,
                target_id=target.user_id,
            ),
        )
    builder.button(
        text="⚪ Воздержаться",
        callback_data=DayVoteCallback(
            chat_id=session.chat_id,
            phase_number=session.phase_number,
            target_id=0,
        ),
    )
    builder.adjust(2)
    return builder.as_markup()


def revenge_keyboard(session: GameSession, best_friend_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for target in session.alive_players:
        builder.button(
            text=target.display_name[:32],
            callback_data=RevengeCallback(
                chat_id=session.chat_id,
                target_id=target.user_id,
            ),
        )
    builder.button(
        text="Никого не забирать",
        callback_data=RevengeCallback(chat_id=session.chat_id, target_id=0),
    )
    builder.adjust(2)
    return builder.as_markup()
