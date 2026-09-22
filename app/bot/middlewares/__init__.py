"""Custom middlewares will be added as persistence is connected."""

from app.bot.middlewares.game_chat_guard import GameChatGuardMiddleware

__all__ = ["GameChatGuardMiddleware"]
