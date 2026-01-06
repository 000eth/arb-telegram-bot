from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# ---------- Модель настроек пользователя ----------


@dataclass
class UserSettings:
    coins: list[str] = field(default_factory=list)
    min_spread: float = 2.0
    min_profit_usd: float = 10.0
    sources: list[str] = field(default_factory=list)
    position_size_usd: float = 100.0
    leverage: float = 1.0
    interval_seconds: int = 60
    paused: bool = False
    scan_active: bool = False
    track_all_coins: bool = False
    track_all_exchanges: bool = False
    selected_exchanges: list[str] = field(default_factory=list)
    pending_action: str | None = None
    menu_message_id: int | None = None


# Глобальные хранилища (в будущем перенесём в БД)
user_settings: dict[int, UserSettings] = {}
last_notifications: dict[int, dict[str, datetime]] = {}


def get_user_settings(user_id: int) -> UserSettings:
    """Возвращает настройки пользователя, создаёт с дефолтами, если их ещё нет."""
    if user_id not in user_settings:
        user_settings[user_id] = UserSettings()
    if user_id not in last_notifications:
        last_notifications[user_id] = {}
    return user_settings[user_id]
