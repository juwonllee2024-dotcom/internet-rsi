import unittest
try:
    from rsi.evaluation import arithmetic, grade_code, make_suite, evaluate_task
except ImportError:
    arithmetic = grade_code = make_suite = evaluate_task = None


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(arithmetic, 'safe evaluation not implemented')

    def test_calculator_is_bounded_and_cannot_access_host(self):
        self.assertEqual(arithmetic('(12 + 3) * 4'), 60)
        for text in ["__import__('os').system('echo unsafe')", '9 ** 9999999', 'x.y', '1/0', '2' * 500]:
            with self.assertRaises(ValueError):
                arithmetic(text)

    def test_code_is_interpreted_without_host_execution(self):
        tests = [([3], 9), ([-4], 16), ([0], 0)]
        self.assertTrue(grade_code('def solve(x):\n    return x * x', tests))
        self.assertFalse(grade_code('def solve(x):\n    return x + x', tests))
        self.assertFalse(grade_code("import os\ndef solve(x):\n    return os.system('echo unsafe')", tests))
        self.assertFalse(grade_code('def solve(x):\n    while True: pass', tests))

    def test_code_cannot_allocate_strings(self):
        self.assertFalse(grade_code("def solve(x):\n    return 'a' * x", [([2], 'aa')]))

    def test_holdout_is_repeatable_but_rotates(self):
        first = make_suite(123)
        self.assertEqual(first, make_suite(123))
        self.assertNotEqual(first, make_suite(456))
        self.assertEqual(len({t['id'] for t in first}), len(first))
        self.assertGreaterEqual(len({t['category'] for t in first}), 7)

    def test_irrelevant_calculator_call_cannot_satisfy_tool_task(self):
        class Replay:
            def __init__(self):
                self.responses=iter(['{"tool":"calculate","arguments":{"expression":"1+1"}}','{"answer":183}'])
            def generate(self,*args):
                return {'text':next(self.responses),'eval_count':20,'latency_s':1}
        from rsi.runtime import BASE_CONFIG
        task={'id':'calculator','category':'tool','prompt':'Use calculate for 37 * 5 - 2.',
              'expected':183,'calculation':'37 * 5 - 2','required_tools':['calculate']}
        self.assertFalse(evaluate_task(Replay(),BASE_CONFIG,task)['passed'])

    def test_truncation_retains_consumed_tokens_and_rejects_success(self):
        class Truncated:
            def generate(self,*args):
                return {'text':'{"answer":','eval_count':192,'prompt_eval_count':70,'latency_s':1,'truncated':True}
        from rsi.runtime import BASE_CONFIG
        result=evaluate_task(Truncated(),BASE_CONFIG,make_suite(123)[0])
        self.assertFalse(result['passed'])
        self.assertEqual(result['eval_count'],192)
        self.assertIn('truncated',result['error'])


if __name__ == '__main__':
    unittest.main()
