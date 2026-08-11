"""Safe expression evaluator for rules engine.

This evaluator provides a sandboxed way to evaluate expressions
without using Python's eval() or exec().
"""

import ast
import operator
from typing import Any

from app.features.rules.expressions.functions import BUILTIN_FUNCTIONS


class ExpressionEvaluator:
    """Safe expression evaluator using AST parsing."""

    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
        ast.Eq: operator.eq,
        ast.NotEq: operator.ne,
        ast.Lt: operator.lt,
        ast.LtE: operator.le,
        ast.Gt: operator.gt,
        ast.GtE: operator.ge,
        ast.And: lambda a, b: a and b,
        ast.Or: lambda a, b: a or b,
        ast.Not: operator.not_,
        ast.In: lambda a, b: a in b,
        ast.NotIn: lambda a, b: a not in b,
    }

    MAX_RECURSION = 50

    def __init__(self):
        self.functions = BUILTIN_FUNCTIONS.copy()
        self._recursion_depth = 0

    def evaluate(
        self,
        expression: str,
        row: dict[str, Any],
        variables: dict[str, Any] | None = None,
    ) -> Any:
        """Evaluate an expression against a data row.

        Args:
            expression: The expression string to evaluate
            row: Dictionary of column values from the current row
            variables: Additional variables available in the expression

        Returns:
            The result of evaluating the expression
        """
        if not expression or not expression.strip():
            return None

        variables = variables or {}
        context = {**variables, **row}

        self._recursion_depth = 0

        try:
            tree = ast.parse(expression, mode="eval")
            return self._eval_node(tree.body, context)
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}")
        except RecursionError:
            raise ValueError("Expression too complex (max recursion exceeded)")

    def _eval_node(self, node: ast.AST, context: dict[str, Any]) -> Any:
        """Recursively evaluate an AST node."""
        self._recursion_depth += 1
        if self._recursion_depth > self.MAX_RECURSION:
            raise ValueError("Max recursion depth exceeded")

        try:
            if isinstance(node, ast.Constant):
                return node.value

            elif isinstance(node, ast.Num):
                return node.n

            elif isinstance(node, ast.Str):
                return node.s

            elif isinstance(node, ast.Name):
                name = node.id
                if name in context:
                    return context[name]
                elif name == "True":
                    return True
                elif name == "False":
                    return False
                elif name == "None":
                    return None
                else:
                    return None

            elif isinstance(node, ast.BinOp):
                left = self._eval_node(node.left, context)
                right = self._eval_node(node.right, context)
                op = self.OPERATORS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                if left is None or right is None:
                    if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
                        left = 0 if left is None else left
                        right = 0 if right is None else right
                return op(left, right)

            elif isinstance(node, ast.UnaryOp):
                operand = self._eval_node(node.operand, context)
                op = self.OPERATORS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(operand)

            elif isinstance(node, ast.Compare):
                left = self._eval_node(node.left, context)
                for op, comparator in zip(node.ops, node.comparators):
                    right = self._eval_node(comparator, context)
                    op_func = self.OPERATORS.get(type(op))
                    if op_func is None:
                        raise ValueError(f"Unsupported comparison: {type(op).__name__}")
                    if not op_func(left, right):
                        return False
                    left = right
                return True

            elif isinstance(node, ast.BoolOp):
                op = self.OPERATORS.get(type(node.op))
                result = self._eval_node(node.values[0], context)
                for value in node.values[1:]:
                    result = op(result, self._eval_node(value, context))
                return result

            elif isinstance(node, ast.IfExp):
                test = self._eval_node(node.test, context)
                if test:
                    return self._eval_node(node.body, context)
                else:
                    return self._eval_node(node.orelse, context)

            elif isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name not in self.functions:
                    raise ValueError(f"Unknown function: {func_name}")

                args = [self._eval_node(arg, context) for arg in node.args]

                kwargs = {}
                for keyword in node.keywords:
                    kwargs[keyword.arg] = self._eval_node(keyword.value, context)

                return self.functions[func_name](*args, **kwargs)

            elif isinstance(node, ast.Subscript):
                value = self._eval_node(node.value, context)
                if isinstance(node.slice, ast.Index):
                    index = self._eval_node(node.slice.value, context)
                else:
                    index = self._eval_node(node.slice, context)
                return value[index]

            elif isinstance(node, ast.List):
                return [self._eval_node(elt, context) for elt in node.elts]

            elif isinstance(node, ast.Tuple):
                return tuple(self._eval_node(elt, context) for elt in node.elts)

            elif isinstance(node, ast.Dict):
                keys = [self._eval_node(k, context) for k in node.keys]
                values = [self._eval_node(v, context) for v in node.values]
                return dict(zip(keys, values))

            elif isinstance(node, ast.Attribute):
                value = self._eval_node(node.value, context)
                if hasattr(value, node.attr):
                    attr = getattr(value, node.attr)
                    if callable(attr):
                        raise ValueError(f"Method calls not allowed: {node.attr}")
                    return attr
                elif isinstance(value, dict):
                    return value.get(node.attr)
                return None

            else:
                raise ValueError(f"Unsupported expression type: {type(node).__name__}")

        finally:
            self._recursion_depth -= 1

    def register_function(self, name: str, func: callable) -> None:
        """Register a custom function for use in expressions."""
        self.functions[name] = func
