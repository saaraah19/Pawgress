from typing import Literal
from pydantic import BaseModel


class UnlockableItemResponse(BaseModel):
    id: str
    kind: Literal["theme_accent", "badge"]
    name: str
    description: str
    unlockLevel: int
    unlocked: bool


class GamificationStateResponse(BaseModel):
    completions: int
    xp: int
    level: int
    xpForCurrentLevel: int
    xpForNextLevel: int
    items: list[UnlockableItemResponse]
