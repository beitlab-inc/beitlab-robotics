"""Product assets have one owner and cannot escape that project's root."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    'build_site', Path(__file__).resolve().parents[1] / 'tools/site/build_site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class AssetPaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.original = site.ROBOT_ROOT, site.BOARD_ROOT
        self.addCleanup(self.restore)
        root = Path(self.temp.name)
        site.ROBOT_ROOT, site.BOARD_ROOT = root / 'robot', root / 'board'
        for project, rel in ((site.ROBOT_ROOT, 'design/model.step'),
                             (site.ROBOT_ROOT, 'docs/book.html'),
                             (site.BOARD_ROOT, 'hardware/board.pdf')):
            path = project / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture')
        self.builder = site.Builder({'docs_nav': []})

    def restore(self):
        site.ROBOT_ROOT, site.BOARD_ROOT = self.original

    def test_assets_follow_owner(self):
        for rel, owner in [('design/model.step', site.ROBOT_ROOT),
                           ('docs/book.html', site.ROBOT_ROOT),
                           ('hardware/board.pdf', site.BOARD_ROOT)]:
            self.assertEqual(self.builder.repo_file(rel), owner / rel)
            self.assertTrue(self.builder.repo_file(rel).is_file())

    def test_site_copy_used_when_project_missing(self):
        saved = site.PRODUCT
        self.addCleanup(setattr, site, 'PRODUCT', saved)
        copies = Path(self.temp.name) / 'product'
        (copies / 'design').mkdir(parents=True)
        (copies / 'design/only_here.stl').write_text('fixture')
        site.PRODUCT = copies
        self.assertEqual(self.builder.repo_file('design/only_here.stl'), copies / 'design/only_here.stl')
        # The project file wins when both exist.
        self.assertEqual(self.builder.repo_file('design/model.step'), site.ROBOT_ROOT / 'design/model.step')

    def test_escape_and_unknown_prefix_rejected(self):
        for rel in ['/etc/passwd', '../board/hardware/board.pdf',
                    'design/../../board/hardware/board.pdf', 'tools/private.py', '']:
            with self.subTest(rel=rel), self.assertRaises(SystemExit):
                self.builder.repo_file(rel)

    def test_symlink_cannot_escape_owner(self):
        (site.ROBOT_ROOT / 'design/escape').symlink_to(site.BOARD_ROOT)
        with self.assertRaises(SystemExit):
            self.builder.repo_file('design/escape/hardware/board.pdf')

    def test_missing_required_asset_fails(self):
        with self.assertRaises(SystemExit):
            self.builder.fill('{{repo:design/missing.stl}}', {}, '', 'test')

    def test_missing_optional_asset_is_omitted(self):
        text = '<!--optional-->{{repo:design/missing.stl}}<!--/optional-->'
        self.assertEqual(self.builder.fill(text, {}, '', 'test'), '')
        self.assertEqual(len(self.builder.dropped), 1)


if __name__ == '__main__':
    unittest.main()
