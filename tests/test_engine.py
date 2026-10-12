import json
import tempfile
import unittest
from pathlib import Path
from rsi.store import Store
from rsi.runtime import MODEL
try:
    from rsi.engine import run_cycle, candidate_from_proposal
except ImportError:
    run_cycle = candidate_from_proposal = None


class FixtureRuntime:
    """Infrastructure fixture only. Never used for actual research evidence."""
    identity = {'model': MODEL, 'digest': 'test-only'}
    def inspect(self):
        return self.identity
    def generate(self, messages, config):
        proposal = 'hypothesis' in messages[-1]['content']
        text = json.dumps({'hypothesis': 'clearer output instructions', 'system_prompt': 'Be precise.', 'think': False}) if proposal else '{"answer": 0}'
        return {'text': text, 'latency_s': 1, 'eval_count': 8, 'prompt_eval_count': 10}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(run_cycle, 'RSI engine not implemented')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / 'state.sqlite')

    def test_complete_real_protocol_queues_next_cycle(self):
        result = run_cycle(self.store, FixtureRuntime(), 'test')
        self.assertEqual(len(result['samples']['baseline']), 8)
        self.assertEqual(len(result['samples']['candidate']), 8)
        self.assertFalse(result['decision']['accepted'])
        self.assertEqual(self.store.claim('test')['id'], 2)

    def test_proposal_cannot_replace_model_or_escape_config_bounds(self):
        from rsi.runtime import BASE_CONFIG
        for proposal in [{'hypothesis': 'x', 'system_prompt': 'x', 'think': False, 'model': 'other'},
                         {'hypothesis': 'x', 'system_prompt': 'x' * 4000, 'think': False},
                         {'hypothesis': 'x', 'system_prompt': 'x', 'think': 'yes'}]:
            with self.assertRaises(ValueError):
                candidate_from_proposal(proposal, BASE_CONFIG)


if __name__ == '__main__':
    unittest.main()
