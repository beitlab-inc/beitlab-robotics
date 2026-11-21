"""The Markdown that AI agents read keeps headings, links, tables and code, and drops page chrome."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'agent_text', Path(__file__).resolve().parents[1] / 'tools/site/agent_text.py')
agent_text = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_text)

PAGE = 'https://example.com/docs/board/'


class AgentText(unittest.TestCase):
    def md(self, html, local_md=True):
        return agent_text.html_to_markdown(html, PAGE + 'x.html', local_md)

    def test_structure(self):
        out = self.md('<h1>T</h1><p>Hi <strong>you</strong> and <code>x</code></p>'
                      '<ul><li>a</li><li>b</li></ul>'
                      '<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>'
                      '<pre><code>int x;\nint y;</code></pre>')
        self.assertIn('# T', out)
        self.assertIn('Hi **you** and `x`', out)
        self.assertIn('- a\n- b', out)
        self.assertIn('| A | B |\n| --- | --- |\n| 1 | 2 |', out)
        self.assertIn('```\nint x;\nint y;\n```', out)

    def test_links_are_absolute_and_point_to_markdown(self):
        out = self.md('<p><a href="../getting-started.html#a">s</a> <a href="https://x.org/p.html">e</a></p>')
        self.assertIn('[s](https://example.com/docs/getting-started.md#a)', out)
        self.assertIn('[e](https://x.org/p.html)', out)

    def test_chrome_is_dropped(self):
        out = self.md('<p class="kicker">K</p><div class="share-row"><a href="/s">Share</a></div><p>Body</p>')
        self.assertNotIn('Share', out)
        self.assertNotIn('K\n', out)
        self.assertIn('Body', out)


if __name__ == '__main__':
    unittest.main()
