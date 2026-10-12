"""Fresh synthetic holdout tasks and host-isolated deterministic graders."""
import ast
import hashlib
import json
import math
import operator
import random
import time

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}


def expression(node, variables=None, depth=0):
    if depth > 15:
        raise ValueError('Expression too deep')
    variables = variables or {}
    run = lambda child: expression(child, variables, depth + 1)
    if isinstance(node, ast.Constant) and type(node.value) in (int, float, bool):
        result = node.value
    elif isinstance(node, ast.Name) and node.id in variables:
        result = variables[node.id]
    elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
        result = OPS[type(node.op)](run(node.left), run(node.right))
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        result = -run(node.operand) if isinstance(node.op, ast.USub) else +run(node.operand)
    elif isinstance(node, ast.IfExp):
        result = run(node.body if run(node.test) else node.orelse)
    elif isinstance(node, ast.Compare) and len(node.ops) == 1:
        compare = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt,
                   ast.GtE: operator.ge, ast.Eq: operator.eq, ast.NotEq: operator.ne}
        if type(node.ops[0]) not in compare:
            raise ValueError('Unsupported comparison')
        result = compare[type(node.ops[0])](run(node.left), run(node.comparators[0]))
    else:
        raise ValueError('Unsupported operation')
    if isinstance(result, (int, float)) and (not math.isfinite(result) or abs(result) > 1e12):
        raise ValueError('Numeric bound exceeded')
    if isinstance(result, (str, list, tuple)) and len(result) > 1000:
        raise ValueError('Size bound exceeded')
    return result


def arithmetic(text):
    try:
        if not isinstance(text, str) or len(text) > 128:
            raise ValueError('Expression too long')
        tree = ast.parse(text, mode='eval')
        if any(not isinstance(n, (ast.Expression, ast.Constant, ast.BinOp, ast.UnaryOp,
                                 ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod,
                                 ast.USub, ast.UAdd)) for n in ast.walk(tree)):
            raise ValueError('Calculator permits bounded arithmetic only')
        return expression(tree.body)
    except (SyntaxError, TypeError, ZeroDivisionError, OverflowError) as e:
        raise ValueError('Invalid arithmetic') from e


def grade_code(code, tests):
    """Interpret a single pure solve function; never exec or eval its source."""
    try:
        if not isinstance(code, str) or len(code) > 2000:
            return False
        tree = ast.parse(code)
        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
            return False
        function = tree.body[0]
        if (function.name != 'solve' or function.decorator_list or function.args.defaults
                or function.args.vararg or function.args.kwarg or function.args.kwonlyargs
                or len(function.body) != 1 or not isinstance(function.body[0], ast.Return)):
            return False
        for inputs, expected in tests:
            if len(inputs) != len(function.args.args):
                return False
            variables = dict(zip((a.arg for a in function.args.args), inputs))
            if expression(function.body[0].value, variables) != expected:
                return False
        return True
    except (ValueError, SyntaxError, TypeError, KeyError, IndexError, ZeroDivisionError, OverflowError):
        return False


def make_suite(seed):
    rng = random.Random(seed)
    a, b, c = rng.randint(13, 71), rng.randint(3, 12), rng.randint(2, 9)
    code = str(rng.randint(10000, 99999))
    def task(name, category, prompt, expected, **extra):
        return dict(id=name, category=category, prompt=prompt, expected=expected, **extra)
    return [
        task('arithmetic', 'reasoning', f'Compute ({a} + {b}) * {c}.', (a + b) * c),
        task('word-problem', 'reasoning', f'{a} boxes each hold {b} items. Remove {c} items in total. How many remain?', a * b - c),
        task('instruction', 'instruction', f'Return answer as an object with exactly keys color and count: color is blue, count is {b}.', {'color': 'blue', 'count': b}),
        task('code', 'coding', f'Return answer as Python code: one function solve(x) returning x * {b} + {c}. Use one return statement, no imports.',
             None, tests=[([x], x * b + c) for x in (-7, 0, 13)]),
        task('plan', 'planning', 'Return answer as the ordered list of all steps. build requires prepare; test requires build; release requires test. Steps: release, test, prepare, build.', ['prepare', 'build', 'test', 'release']),
        task('calculator', 'tool', f'Use calculate to compute {a} * {b} - {c}. Then give result.', a * b - c, required_tools=['calculate']),
        task('recall', 'memory', 'Retrieve the value at key memo from memory_get. Return that exact string.', code, memory={'memo': code}, required_tools=['memory_get']),
        task('agent', 'agent', f'Calculate {a} + {b}; store result at key total using memory_put; retrieve it with memory_get; return result.',
             a + b, required_tools=['calculate', 'memory_put', 'memory_get'])]


def suite_hash(suite):
    return hashlib.sha256(json.dumps(suite, sort_keys=True).encode()).hexdigest()


TOOL_INSTRUCTIONS = '''Return only JSON. Final response: {"answer": value}. To use a tool: {"tool": "calculate", "arguments": {"expression": "12+3"}} or {"tool": "memory_put", "arguments": {"key": "total", "value": 15}} or {"tool": "memory_get", "arguments": {"key": "memo"}}. Wait for tool result before next call. No other tools exist.'''


def evaluate_task(runtime, config, task):
    started = time.monotonic()
    memory = dict(task.get('memory', {}))
    calls, outputs = [], []
    messages = [{'role': 'system', 'content': config['system_prompt'] + '\n' + TOOL_INSTRUCTIONS},
                {'role': 'user', 'content': task['prompt']}]
    passed, error = False, None
    try:
        for _ in range(5):
            response = runtime.generate(messages, config)
            outputs.append(response)
            envelope = json.loads(response['text'])
            if 'answer' in envelope:
                answer = envelope['answer']
                passed = grade_code(answer, task['tests']) if task['category'] == 'coding' else answer == task['expected']
                passed = passed and all(t in calls for t in task.get('required_tools', []))
                if task['id'] == 'agent':
                    passed = passed and memory.get('total') == task['expected'] and calls == ['calculate', 'memory_put', 'memory_get']
                break
            tool, arguments = envelope['tool'], envelope['arguments']
            if tool == 'calculate':
                result = arithmetic(arguments['expression'])
            elif tool == 'memory_put':
                key, value = arguments['key'], arguments['value']
                if not isinstance(key, str) or len(key) > 64 or len(json.dumps(value)) > 512 or len(memory) >= 8:
                    raise ValueError('Memory bounds exceeded')
                memory[key] = value
                result = {'stored': key}
            elif tool == 'memory_get':
                result = memory[arguments['key']]
            else:
                raise ValueError('Tool not permitted')
            calls.append(tool)
            messages.extend([{'role': 'assistant', 'content': response['text']},
                             {'role': 'user', 'content': 'Tool result: ' + json.dumps(result)}])
        else:
            error = 'agent step budget exhausted'
    except Exception as e:
        error = type(e).__name__ + ': ' + str(e)[:160]
    return {'id': task['id'], 'category': task['category'], 'passed': bool(passed),
            'latency_s': time.monotonic() - started, 'eval_count': sum(x['eval_count'] for x in outputs),
            'prompt_eval_count': sum(x.get('prompt_eval_count', 0) for x in outputs),
            'error': error, 'tool_calls': calls, 'outputs': outputs,
            'cost_usd': None, 'energy_joules': None}
