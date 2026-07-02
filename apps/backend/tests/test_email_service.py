"""Unit tests for ``app.services.email``.

Delivery is disabled by default in the test environment (``EMAIL_ENABLED``
defaults to ``False``), so ``send_email`` must log-and-return-``False``
without ever opening an SMTP connection.
"""

import asyncio
from unittest.mock import patch

from app.services import email as email_service


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class TestRenderTemplate:
    def test_substitutes_tokens_from_real_template(self):
        html = email_service.render_template(
            "invite_user",
            organization_name="Marlowe Capital Partners",
            inviter_name="Eleanor Vance",
            role_label="Fund Manager",
            accept_url="https://app.example.com/invitations/accept?token=tok-1",
            invitee_email="alex@example.com",
            expires_at="July 15, 2026",
        )
        assert "Marlowe Capital Partners" in html
        assert "Eleanor Vance" in html
        assert "Fund Manager" in html
        assert "https://app.example.com/invitations/accept?token=tok-1" in html
        assert "alex@example.com" in html
        assert "July 15, 2026" in html
        # All tokens were substituted.
        assert "$organization_name" not in html
        assert "$accept_url" not in html

    def test_params_are_html_escaped(self):
        html = email_service.render_template(
            "invite_user",
            organization_name='<a href="https://evil.example">click</a>',
            inviter_name="R&D <Growth> Fund",
        )
        assert '<a href="https://evil.example">' not in html
        assert "&lt;a href=&quot;https://evil.example&quot;&gt;click&lt;/a&gt;" in html
        assert "R&amp;D &lt;Growth&gt; Fund" in html

    def test_safe_substitute_leaves_missing_tokens_intact(self):
        html = email_service.render_template(
            "invite_user", organization_name="Acme"
        )
        assert "Acme" in html
        # Unsupplied params do not raise; the raw token survives.
        assert "$accept_url" in html

    def test_template_reads_are_cached(self):
        email_service._template_cache.clear()
        email_service.render_template("welcome", organization_name="Acme")
        assert "welcome" in email_service._template_cache
        cached = email_service._template_cache["welcome"]
        # Second render must reuse the cached text, not re-read the file.
        with patch.object(
            email_service.Path, "read_text", side_effect=AssertionError("re-read")
        ):
            email_service.render_template("welcome", organization_name="Other")
        assert email_service._template_cache["welcome"] is cached

    def test_all_templates_render(self):
        for name in (
            "invite_user",
            "capital_call",
            "distribution",
            "welcome",
            "document_uploaded",
        ):
            assert "<html" in email_service.render_template(name)


class TestSendEmailDisabled:
    def test_returns_false_and_logs_without_smtp(self, caplog):
        with patch.object(email_service.smtplib, "SMTP") as smtp:
            with caplog.at_level("INFO"):
                result = email_service.send_email(
                    "to@example.com",
                    "Test subject",
                    "<html><body>hi</body></html>",
                    context={"organization_name": "Acme"},
                )
        assert result is False
        smtp.assert_not_called()
        disabled_logs = [
            r.message for r in caplog.records if "disabled" in r.message
        ]
        assert disabled_logs
        # Payload variables are logged, the full HTML body is not.
        assert "to@example.com" in disabled_logs[0]
        assert "Test subject" in disabled_logs[0]
        assert "Acme" in disabled_logs[0]
        assert "<body>" not in disabled_logs[0]

    def test_enabled_flag_alone_is_not_enough(self, monkeypatch):
        # EMAIL_ENABLED without SMTP_HOST / EMAIL_FROM still degrades.
        monkeypatch.setattr(email_service.settings, "EMAIL_ENABLED", True)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "")
        monkeypatch.setattr(email_service.settings, "EMAIL_FROM", "")
        with patch.object(email_service.smtplib, "SMTP") as smtp:
            assert email_service.send_email("a@b.c", "s", "<p>x</p>") is False
        smtp.assert_not_called()

    def test_async_wrapper_returns_false_when_disabled(self):
        result = _run(
            email_service.send_email_async("to@example.com", "s", "<p>x</p>")
        )
        assert result is False


class TestSendEmailEnabled:
    def test_sends_via_smtp_with_starttls_and_login(self, monkeypatch):
        monkeypatch.setattr(email_service.settings, "EMAIL_ENABLED", True)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(email_service.settings, "SMTP_PORT", 587)
        monkeypatch.setattr(email_service.settings, "SMTP_USERNAME", "mailer")
        monkeypatch.setattr(email_service.settings, "SMTP_PASSWORD", "secret")
        monkeypatch.setattr(email_service.settings, "SMTP_STARTTLS", True)
        monkeypatch.setattr(
            email_service.settings, "EMAIL_FROM", "noreply@example.com"
        )

        with patch.object(email_service.smtplib, "SMTP") as smtp_cls:
            smtp = smtp_cls.return_value.__enter__.return_value
            result = email_service.send_email(
                "to@example.com", "Hello", "<p>Hi</p>", "Hi"
            )

        assert result is True
        smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=30)
        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("mailer", "secret")
        (message,), _ = smtp.send_message.call_args
        assert message["From"] == "noreply@example.com"
        assert message["To"] == "to@example.com"
        assert message["Subject"] == "Hello"

    def test_smtp_failure_returns_false(self, monkeypatch):
        monkeypatch.setattr(email_service.settings, "EMAIL_ENABLED", True)
        monkeypatch.setattr(email_service.settings, "SMTP_HOST", "smtp.example.com")
        monkeypatch.setattr(
            email_service.settings, "EMAIL_FROM", "noreply@example.com"
        )
        with patch.object(
            email_service.smtplib, "SMTP", side_effect=OSError("refused")
        ):
            assert email_service.send_email("to@example.com", "s", "<p>x</p>") is False
