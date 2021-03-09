
install:
	@echo "Installing spinup package locally"
	python3 -m pip install -e .
	@echo
	@echo
	@echo "Run using python3 spinup"

clean:
	rm -i -rf spinup.egg-info
	find . -name "__pycache__" -type d -exec rm -i -rf {} \; || 1

uninstall:
	pip3 uninstall spinup

lint:
	@echo "Blackening code"
	black  -t py36 ./
	@echo
	@echo
	@echo "Running pylama on code"
	pylama
