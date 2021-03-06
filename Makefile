
install:
	@echo "installing spinup package locally"
	python3 -m pip install -e .

uninstall:
	pip3 uninstall spinup
	rm -i -rf spinup.egg-info
	find . -name "__pycache__" -type d -exec rm -i -rf {} \; || 1
