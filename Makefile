
install:
	@echo "installing spinup package locally"
	python3 -m pip install -e .

uninstall:
	pip3 uninstall spinup
	rm -i -rf spinup.egg-info
	find . -name "__pycache__" -type d -exec rm -i -rf {} \; || 1

lint:
	@echo "Blackening code"
	black  -t py36 ./
	@echo
	@echo
	@echo "Running pylama on code"
	pylama
