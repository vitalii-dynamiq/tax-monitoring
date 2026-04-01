"""
Tests for the APScheduler-based monitoring scheduler.
"""

from unittest.mock import patch

from app.services.scheduler import start_scheduler, stop_scheduler


class TestStartScheduler:
    def test_skips_without_api_key(self):
        with patch("app.services.scheduler.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            mock_settings.monitoring_scheduler_interval_seconds = 60
            # Should not raise, just log and return
            with patch("app.services.scheduler.scheduler") as mock_sched:
                start_scheduler()
                mock_sched.add_job.assert_not_called()
                mock_sched.start.assert_not_called()

    def test_starts_with_api_key(self):
        with patch("app.services.scheduler.settings") as mock_settings:
            mock_settings.anthropic_api_key = "sk-test"
            mock_settings.monitoring_scheduler_interval_seconds = 60
            mock_settings.anthropic_model = "claude-sonnet-4-6"
            with patch("app.services.scheduler.scheduler") as mock_sched:
                start_scheduler()
                mock_sched.add_job.assert_called_once()
                mock_sched.start.assert_called_once()


class TestStopScheduler:
    def test_stops_running_scheduler(self):
        with patch("app.services.scheduler.scheduler") as mock_sched:
            mock_sched.running = True
            stop_scheduler()
            mock_sched.shutdown.assert_called_once_with(wait=False)

    def test_noop_when_not_running(self):
        with patch("app.services.scheduler.scheduler") as mock_sched:
            mock_sched.running = False
            stop_scheduler()
            mock_sched.shutdown.assert_not_called()
