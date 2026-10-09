import unittest

from complete_source_excerpts import PARSERS, complete_bounds, replace_document


class SourceCompletionTests(unittest.TestCase):
    def bounds(self, code, start, end, language='java'):
        return complete_bounds(code.splitlines(), PARSERS[language].parse(code.encode()), start, end)

    def test_partial_function_includes_signature_and_all_branches(self):
        code = 'class Example {\n  /** Commit or roll back. */\n  void run() {\n    if (ready) {\n      commit();\n    } else {\n      rollback();\n    }\n  }\n  void next() {}\n}\n'
        self.assertEqual(self.bounds(code, 5, 6), (2, 9))

    def test_multi_method_window_does_not_drop_last_function(self):
        code = 'int first() {\n return 1;\n}\nint second() {\n return 2;\n}\n'
        self.assertEqual(self.bounds(code, 2, 5, 'c'), (1, 6))

    def test_field_window_does_not_expand_the_entire_class(self):
        code = 'class Example {\n  int value;\n  void run() {}\n}\n'
        self.assertEqual(self.bounds(code, 2, 2), (2, 2))

    def test_completion_is_idempotent_with_leading_comments(self):
        code = '// Role\n// Boundary\nvoid run() {\n work();\n}\n'
        bounds = self.bounds(code, 4, 4, 'c')
        self.assertEqual(bounds, (1, 5))
        self.assertEqual(self.bounds(code, *bounds, 'c'), bounds)

    def test_markdown_preserves_source_newline_not_old_window_padding(self):
        url = 'https://github.com/example/repo/blob/' + 'a'*40 + '/test.c#L2-L3'
        source = f'[test.c · L2—L3]({url})\n\n```c\n work();\n\n```'
        updates = {('example/repo', 'a'*40, 'test.c', '2', '3'): (' work();\n', 'void run() {\n work();\n}', 1, 3)}
        rendered, count = replace_document(source, updates, markdown=True)
        self.assertEqual(count, 1)
        self.assertIn('L1—L3', rendered)
        self.assertIn(' work();\n}\n```', rendered)
        self.assertNotIn(' work();\n}\n\n```', rendered)

    def test_architecture_description_includes_nested_encoding(self):
        lines = ['instruct barrier() %{', '  format %{', '    "barrier"', '  %}', '  ins_encode %{', '    emit();', '  %}', '%}']
        self.assertEqual(complete_bounds(lines, None, 2, 6, 'x86.ad'), (1, 8))


if __name__ == '__main__':
    unittest.main()
