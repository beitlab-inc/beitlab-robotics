# Beitlab Robotics website

The static company site and product documentation, published with GitHub Pages.

```sh
make site          # build into build/site/ and check every local link and #anchor
make site-serve    # the same, then serve it on http://localhost:8000
```

## Layout

| Path | What it is |
| --- | --- |
| `site.json` | Site name, optional `repo_url` (adds a GitHub link to the header) and `base_url`, and the docs sidebar order |
| `_layouts/` | Page shells (`home.html`, `docs.html`) and shared fragments (`head`, `header`, `footer`) |
| `pages/` | One HTML file per page, each starting with a `<!--meta ... -->` block (title, description, layout, section) |
| `assets/` | CSS, JS, the favicon, the video stills and the two videos (`assets/video/`) |

The two videos live in `assets/video/` because the product repos are private and CI cannot read
their `out/` folders. To refresh them, copy the new renders from `Balanced_robot/design/body_v1/out/video/`
over the files there and update the sizes in `pages/index.html` and `pages/docs/robot/assembly.html`.

Product files (renders, PDFs, STL and STEP models, the bill of materials, the book) are copies in
`site/product/`, with the same paths as in the sibling projects. A local build reads the sibling
project's generated file when it exists, so it always sees the latest output; otherwise it uses the
copy. The build puts the file in `build/site/files/`. Pages refer to them like this:

- `{{repo:hardware/SUBSYSTEMS.pdf}}` is the URL of that file; `{{size:...}}` is its size.
- `{{mdtable:design/body_v1/out/options/option_B/hardware_bom.md}}` renders a generated Markdown table.
- `<!--optional--> ... <!--/optional-->` is left out, with a note, if a file inside it is missing.
- `{{root}}` is the relative path to the site root, so the site works under
  `user.github.io/<repo>/` and on a custom domain.

So after `make body`, `make renders`, `make videos` or a board rebuild, the next site build
picks up the new outputs. The board schematic comes from the frozen release
(`hardware/releases/carrier-v0.8/`); when a new revision is frozen, update that path in
`pages/docs/board/index.html`. Boards are sold only by Beitlab Robotics, so the site
deliberately publishes no fabrication files (Gerbers, BOM, placement or assembly drawings).

The video stills in `assets/img/` (`hero-robot.jpg`, `promo-poster.jpg`, `assembly-poster.jpg`)
are cut from the videos in `assets/video/`: refresh them with `python3 tools/site/build_site.py --posters`
(needs opencv).

The homepage scroll is a 60-frame orbit in `assets/orbit/` (`f00.png`–`f59.png`), the same
CAD scene as `make renders`, with the plate and floor removed so the robot sits on the page.
Refresh it with the VTK environment `make renders` uses, after that scene exists:

```sh
uv run --no-project --with vtk==9.4.2 --with pillow --with numpy python tools/site/orbit_frames.py
```

## Publishing

`.github/workflows/pages.yml` builds from this repository alone and deploys website changes on
`main` or `master`. After a product output changes, copy the file into `site/product/` (same path,
e.g. `cp ../Balanced_robot/design/body_v1/out/options/option_B/hardware_bom.md site/product/design/body_v1/out/options/option_B/`)
and commit it with the change. The build fails if a copy is missing, so a new reference needs its copy first.

1. In the repository on GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions**.
2. Push. The site appears at `https://<user>.github.io/<repo>/`.
3. **Custom domain, later:** in Settings → Pages → Custom domain, enter the domain and add the
   DNS records GitHub shows (a `CNAME` to `<user>.github.io` for a subdomain, or the four `A`
   records for an apex domain), then tick **Enforce HTTPS**. Set `"base_url"` in `site.json` to
   `https://<domain>` so the canonical links, `sitemap.xml` and the 404 page use it. With an
   Actions deploy no `CNAME` file is needed.

The built site is about 96 MB, mostly the two videos (64 MB) and the STEP models. GitHub Pages
allows 1 GB per site and 100 MB per file.
