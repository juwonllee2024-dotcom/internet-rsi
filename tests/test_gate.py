import unittest
try:
    from rsi.gate import compare
except ImportError:
    compare = None


def sample(name, passed, latency=2.0):
    return {'id': name, 'category': 'reasoning', 'passed': passed,
            'latency_s': latency, 'eval_count': 20, 'error': None}


class GateTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(compare, 'evidence gate not implemented')

    def test_improvement_requires_paired_complete_evidence(self):
        decision = compare([sample('a', False), sample('b', True)],
                           [sample('a', True), sample('b', True)], ['a', 'b'])
        self.assertTrue(decision['accepted'])
        self.assertFalse(compare([sample('a', False)], [sample('a', True)], ['a', 'b'])['accepted'])

    def test_task_regression_rejected_even_when_average_ties(self):
        decision = compare([sample('a', True), sample('b', False)],
                           [sample('a', False), sample('b', True)], ['a', 'b'])
        self.assertFalse(decision['accepted'])
        self.assertIn('regression', decision['reason'])

    def test_execution_improvement_distinguished_from_quality(self):
        decision = compare([sample('a', True, 2)], [sample('a', True, 1)], ['a'])
        self.assertTrue(decision['accepted'])
        self.assertEqual(decision['kind'], 'execution')
        self.assertFalse(compare([sample('a', True)], [sample('a', True)], ['a'])['accepted'])

    def test_invalid_metrics_duplicates_and_truncation_rejected(self):
        base = [sample('a', False)]
        for candidate in [[sample('a', True, float('nan'))], [sample('a', True, -1)],
                          [sample('a', True), sample('a', True)], []]:
            self.assertFalse(compare(base, candidate, ['a'])['accepted'])


if __name__ == '__main__':
    unittest.main()
