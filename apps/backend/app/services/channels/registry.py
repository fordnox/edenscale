from app.services.channels.base import NotificationChannel
from app.services.channels.email_channel import EmailChannel


class ChannelRegistry:
    def __init__(self) -> None:
        self._channels: dict[str, NotificationChannel] = {}

    def register(self, channel: NotificationChannel) -> None:
        self._channels[channel.channel_name] = channel

    def get(self, channel_name: str) -> NotificationChannel | None:
        return self._channels.get(channel_name)


def get_default_registry() -> ChannelRegistry:
    """Registry of live channels. Email is the only delivered channel today;
    SMS/push can be added here without touching the worker."""
    registry = ChannelRegistry()
    registry.register(EmailChannel())
    return registry
