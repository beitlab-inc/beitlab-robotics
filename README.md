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
`design/...` / `docs/...` assets from `../Balanced_robot`. Source files are not
duplicated. It copies the referenced assets into the generated site. Override
locations with `ROBOT_ROOT` and `BOARD_ROOT` environment variables when needed.
`make test` checks source routing and rejects asset paths that escape their project.

## GitHub Pages

The workflow checks out all three repositories. Set repository variables
`ROBOT_REPOSITORY` and `BOARD_REPOSITORY` to `owner/name` if their remote names
differ from `Balanced_robot` and `Robotics_board`. For private product repositories,
set `WORKSPACE_READ_TOKEN` to a token with read access to both; otherwise the workflow
uses GitHub's default token. No remote repository or token was created by the split.

Enable Pages with GitHub Actions as the source. Run the workflow manually after
product asset updates, or push a website change. Product repositories no longer
share this repository's push event. Set `site/site.json`'s `base_url` when a domain
is configured. Nothing is published by the local `make site` command.
