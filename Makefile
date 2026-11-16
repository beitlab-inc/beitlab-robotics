PYTHON ?= python3
.DEFAULT_GOAL := site
.PHONY: site site-serve help test
site:
	$(PYTHON) tools/site/build_site.py
site-serve:
	$(PYTHON) tools/site/build_site.py --serve
help:
	@echo "make site: build and link-check; make site-serve: local preview"

test:
	$(PYTHON) -m unittest discover -s tests -v
