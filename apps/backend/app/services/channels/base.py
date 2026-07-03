from abc import ABC, abstractmethod


class NotificationChannel(ABC):
    channel_name: str = ""

    @abstractmethod
    async def send(
        self,
        recipient_email: str,
        title: str,
        message: str,
        event_type: str,
        data: dict,
    ) -> dict:
        """Send a notification and return a delivery-status dict.

        ``title`` / ``message`` come straight from the event bus (the in-app
        Notification's subject/body). The email channel ignores them and uses
        ``event_type`` to pick a Resend template, forwarding ``data`` as the
        template variables. The return dict carries ``success`` and, on
        failure, ``error`` — the worker turns it into a NotificationLog row.
        """
        ...
