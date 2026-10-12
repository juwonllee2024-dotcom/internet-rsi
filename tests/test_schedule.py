import unittest
from unittest.mock import patch
from scripts.schedule import eligible
from rsi.remote import RemoteStore


class ScheduleTests(unittest.TestCase):
    def status(self, **extra):
        return dict(paused=False, completed_today=0, daily_cycle_limit=4,
                    jobs=[dict(id=1, status='queued', expires=0)], **extra)

    def test_extra_schedule_requires_an_active_study(self):
        status = self.status()
        self.assertFalse(eligible(status, 'schedule', '53 * * * *', now=1000))
        self.assertTrue(eligible(status, 'schedule', '23 */6 * * *', now=1000))
        self.assertTrue(eligible(status, 'workflow_dispatch', now=1000))

    def test_study_expiration_and_reserved_cycle_limit_are_enforced(self):
        study = dict(started_at=0, ends_at=2000, completed=0, started=0, max_cycles=2)
        status = self.status(study=study)
        self.assertTrue(eligible(status, 'schedule', '53 * * * *', now=1000))
        self.assertFalse(eligible(status, 'schedule', '53 * * * *', now=2000))
        study['started'] = 2
        self.assertFalse(eligible(status, 'schedule', '53 * * * *', now=1000))

    def test_pause_daily_budget_and_other_worker_prevent_runtime_install(self):
        status = self.status()
        status['paused'] = True
        self.assertFalse(eligible(status, 'workflow_dispatch', now=1000))
        status['paused'] = False
        status['completed_today'] = 4
        self.assertFalse(eligible(status, 'workflow_dispatch', now=1000))
        status['completed_today'] = 0
        status['jobs'][0].update(status='running', expires=2000)
        self.assertFalse(eligible(status, 'workflow_dispatch', now=1000))
        self.assertTrue(eligible(status, 'workflow_dispatch', now=2000))

    def test_final_reserved_cycle_can_recover_after_lease_expiry(self):
        study = dict(id='study-a', started_at=0, ends_at=3000, completed=1, started=2, max_cycles=2)
        status = self.status(study=study)
        status['jobs'][0].update(status='running', study_id='study-a', expires=1000)
        self.assertTrue(eligible(status, 'schedule', '53 * * * *', now=2000))
        self.assertFalse(eligible(status, 'schedule', '53 * * * *', now=999))
        status['jobs'][0]['study_id'] = 'another-study'
        self.assertFalse(eligible(status, 'schedule', '53 * * * *', now=2000))

    def test_hosted_client_carries_preflight_study_identity(self):
        with patch.dict('os.environ', {'RSI_STUDY_ID': 'study-a'}):
            client = RemoteStore('https://example.test', 'test-token-with-more-than-24-characters')
            with patch.object(client, 'request', return_value=None) as request:
                client.claim('github-actions')
                self.assertEqual(request.call_args.args[1].get('study_id'), 'study-a')

    def test_server_expiration_wins_over_a_slow_runner_clock(self):
        study = dict(id='study-a', active=False, started_at=0, ends_at=2000,
                     completed=0, started=0, max_cycles=2)
        self.assertFalse(eligible(self.status(study=study), 'schedule', '53 * * * *', now=1999))


if __name__ == '__main__':
    unittest.main()
