"""
gamification/catalog.py

XP/Level (2026-09-16) — Blueprint §13's V2 list, built now that the core
loop is proven: "Light gamification: XP and a small number of
meaningful, non-essential unlockables." Sequenced deliberately after
everything else, per the founder's own stated priority order.

**Nothing here is persisted.** XP and level are computed live from
lifetime Task + Habit completions (gamification/routes.py), the exact
same "derive from permanent history, never a new stored field" pattern
companion-character-spec.md §5.E already established for the reserved
Growth stage, and that companion/mood_calculator.py already uses for
mood. This needed zero schema changes and zero migration.

**Hard constraints preserved from Blueprint §7/§16, Brand §9-10:**
- XP only ever accumulates. No streak, no decay, no loss on a missed day
  — there is no code path anywhere in this module that can make XP or
  level go down.
- No leaderboard, no comparison to other users — XP/level are private,
  visible only to the user themselves, computed per-user with no
  cross-user query anywhere in this module.
- Unlockables are cosmetic only (a UI accent color, a display-only badge)
  — nothing here gates or changes any actual product functionality.
  Reaching level 1 vs. level 10 changes what you can look at, never what
  you can do.
- No spendable currency, no shop-with-a-price — items unlock
  automatically at a level threshold, never "bought," so there's no
  economy to design monetization pressure into later.
- No manufactured scarcity — no "limited edition," no time-boxed drops.
  The full catalog is always visible (locked items show their
  threshold), so nothing here uses artificial urgency to drive
  engagement (Blueprint §14's explicit ban, applied to this feature).
"""

import math
from dataclasses import dataclass
from typing import Literal


def xp_for_level(level: int) -> int:
    """XP required to REACH this level. Level 1 is the starting level (0
    XP). A simple quadratic curve (10 * (level-1)^2) — deliberately
    slow-scaling relative to how few points a single completion is worth,
    so leveling up stays a once-in-a-while, noticeable event rather than
    something that happens every session (Brand §10's "earned delight"
    principle: a moment that happens too often stops registering as
    one). Explicitly tunable — this is a formula, not a design commitment,
    and the one named constant (XP_PER_COMPLETION below) is the first
    thing to adjust if leveling feels too fast or too slow once there's
    real usage to look at.
    """
    return 10 * (level - 1) ** 2


def level_for_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    return int(math.isqrt(xp // 10)) + 1


# 1 XP per completion, task or habit alike — no weighting one kind of
# completion over another. Simple and transparent (a user could work out
# their own XP by counting completions), and avoids an arbitrary judgment
# call about whether a task "counts more" than a habit.
XP_PER_COMPLETION = 1

UnlockKind = Literal["theme_accent", "badge"]


@dataclass(frozen=True)
class UnlockableItem:
    id: str
    kind: UnlockKind
    name: str
    description: str
    unlockLevel: int


# Theme accents: swaps the app's --color-assistant accent hue. All colors
# chosen from within the existing warm-neutral palette system — none of
# these are anything that could read as a status/urgency color (the
# design tokens' own comment is explicit that red is "structurally
# absent... not implemented at all," and that constraint applies here too).
# "Sage" (the current default) is always unlocked — level 1, everyone has it.
#
# Badges: pure display, a small trophy shelf, no functional effect
# whatsoever. Simple abstract line-art, not cat illustration — see this
# module's docstring for why cat cosmetics aren't what's being unlocked
# here.
UNLOCKABLE_ITEMS: list[UnlockableItem] = [
    UnlockableItem("theme-sage", "theme_accent", "Sage", "The original.", 1),
    UnlockableItem("badge-first-steps", "badge", "First Steps", "You showed up.", 2),
    UnlockableItem("theme-terracotta", "theme_accent", "Terracotta", "A warmer accent.", 3),
    UnlockableItem("badge-momentum", "badge", "Building Momentum", "A quiet streak of showing up — never tracked as a streak, just noticed.", 4),
    UnlockableItem("theme-dusty-blue", "theme_accent", "Dusty Blue", "A cooler accent.", 5),
    UnlockableItem("badge-steady-hand", "badge", "Steady Hand", "Consistency, not intensity.", 6),
    UnlockableItem("theme-golden", "theme_accent", "Golden", "A brighter accent.", 8),
    UnlockableItem("badge-quiet-consistency", "badge", "Quiet Consistency", "Still here.", 9),
    UnlockableItem("badge-old-friend", "badge", "Old Friend", "A long time now.", 13),
]


def unlocked_items(level: int) -> list[UnlockableItem]:
    return [item for item in UNLOCKABLE_ITEMS if item.unlockLevel <= level]
