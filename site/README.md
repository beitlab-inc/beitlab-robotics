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
| `assets/` | CSS, JS, the favicon, the video stills and the promo film (`assets/video/`) |

The promo film lives in `assets/video/` because the product repos are private and CI cannot read
their `out/` folders. To refresh it, copy the new render from `Balanced_robot/design/body_v1/out/video/`
over the file there.

`site/product/` holds the pictures the public pages show: robot renders and photographs of the
board. A local build reads the sibling project's file when it exists, and otherwise uses the copy.
The build puts it in `build/site/files/`. Pages refer to a picture with `{{repo:PATH}}`.
`{{root}}` is the relative path to the site root, so the site works under `user.github.io/<repo>/`
and on a custom domain.

Balance Robot v1 is a product for sale. This repository does not publish the STEP models, printed
parts, hardware list, schematics, circuit drawings, subsystems report, engineering book, or the
assembly film. Those stay in the private product projects.

The video stills in `assets/img/` (`hero-robot.jpg`, `promo-poster.jpg`)
are cut from the promo film: refresh them with `python3 tools/site/build_site.py --posters`
(needs opencv).

The homepage robot is live: `assets/js/robot3d.js` poses the URDF with three.js (vendored in
`assets/js/vendor/`, no CDN). The head pan and tilt servos follow the pointer, and scrolling turns
the camera once around the robot while the four-bar legs squat twice. The model is
`assets/robot/robot.json` and `robot.bin` (2 MB), packed from the ROS 2 description package with
`python3 tools/site/robot_model.py` (numpy only; run it after the URDF or its meshes change).

The 60-frame orbit in `assets/orbit/` (`f00.png`–`f59.png`) is the fallback for browsers without
WebGL or with Save-Data on, and the still shown with reduced motion. It is the same CAD scene as
`make renders`, with the plate and floor removed so the robot sits on the page.
Refresh it with the VTK environment `make renders` uses, after that scene exists:

```sh
uv run --no-project --with vtk==9.4.2 --with pillow --with numpy python tools/site/orbit_frames.py
```

## Publishing

`.github/workflows/pages.yml` builds from this repository alone and deploys website changes on
`main` or `master`. After a published render changes, copy that picture into `site/product/` at the
same path and commit it with the change. The build fails if a copy is missing, so a new reference
needs its copy first. Do not copy manufacturing files into this repository.

1. In the repository on GitHub, open **Settings → Pages** and set **Source** to **GitHub Actions**.
2. Push. The site appears at `https://<user>.github.io/<repo>/`.
3. **Custom domain, later:** in Settings → Pages → Custom domain, enter the domain and add the
   DNS records GitHub shows (a `CNAME` to `<user>.github.io` for a subdomain, or the four `A`
   records for an apex domain), then tick **Enforce HTTPS**. Set `"base_url"` in `site.json` to
   `https://<domain>` so the canonical links, `sitemap.xml` and the 404 page use it. With an
   Actions deploy no `CNAME` file is needed.

GitHub Pages allows 1 GB per site and 100 MB per file. The promo film is the largest file published here.
