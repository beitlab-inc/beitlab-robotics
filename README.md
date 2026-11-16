# Beitlab Robotics landing page

Website source and deployment tooling, separated from the product projects.

```text
beitlab/
├── Balanced_robot/     # firmware, mechanics, ROS, simulation and robot docs
├── Robotics_board/    # electronics and board releases
└── Robotics_landing/  # this project
```

Run `make site` to build and check every local link, or `make site-serve` for
local preview at http://localhost:8000. Output is `build/site/` and is fully
self-contained for static hosting. See [site authoring](site/README.md).

- `site/pages/`: editable pages, including `docs/getting-started.html`.
- `site/_layouts/`: shared page templates.
- `site/assets/`: website styling, scripts and images.
- `tools/site/build_site.py`: static builder and link checker (Python standard library).
- `.github/workflows/pages.yml`: GitHub Pages build/deploy workflow.

The builder reads `hardware/...` product assets from `../Robotics_board` and
`design/...` / `docs/...` assets from `../Balanced_robot` when those projects exist. Otherwise
it uses the copies in `site/product/`, which the Pages workflow relies on. Override the sibling
locations with `ROBOT_ROOT` and `BOARD_ROOT`. `make test` checks source routing and rejects asset
paths that escape their project.

## GitHub Pages

The workflow checks out only this repository. The product files and videos it needs are committed
under `site/product/` and `site/assets/video/`, so no token or product repository is required.

Enable Pages with GitHub Actions as the source. Push a website change, or run the workflow
manually. Set `site/site.json`'s `base_url` when a domain is configured. Nothing is published
by the local `make site` command.
