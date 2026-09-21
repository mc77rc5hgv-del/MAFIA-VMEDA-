from aiogram.filters import BaseFilter
from aiogram.types import Message


class ChatTypeFilter(BaseFilter):
    def __init__(self, *chat_types: str) -> None:
        self.chat_types = set(chat_types)

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types
