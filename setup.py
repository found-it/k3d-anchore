from setuptools import setup, find_packages
import pathlib

version = "0.1.0"
package_name = "spinup"
description = "CLI to spin up k3d anchore clusters locally"
package_data = {package_name: ["cli/*"]}
requirements = pathlib.Path("requirements.txt").read_text().splitlines()

setup(
    name="spinup",
    author="James Petersen",
    author_email="jpetersenames@gmail.com",
    description=description,
    url="https://github.com/found-it/k3d-anchore",
    packages=find_packages(),
    include_package_data=True,
    version=version,
    entry_points="""
        [console_scripts]
        spinup=spinup.cli:cli
        """,
    install_requires=requirements,
)
