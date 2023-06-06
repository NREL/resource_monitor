"""
setup.py
"""
import logging
from pathlib import Path
from setuptools import setup, find_packages


logger = logging.getLogger(__name__)


here = Path(__file__).parent.absolute()

# with open("README.md", encoding="utf-8") as f:
#    readme = f.read()

version = None
with open(here / "resource_monitor" / "version.py", encoding="utf-8") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.strip().split()[2].strip('"').strip("'")


assert version is not None

setup(
    name="resource_monitor",
    version=version,
    description="Monitors system resource utilization",
    # long_description=readme,
    # long_description_content_type="text/markdown",
    maintainer="Daniel Thom",
    maintainer_email="daniel.thom@nrel.gov",
    url="https://github.nrel.gov/dthom/resource_monitor",
    packages=find_packages(),
    package_dir={"resource_monitor": "resource_monitor"},
    entry_points={
        "console_scripts": [
            "rmon=resource_monitor.cli.rmon:cli",
        ],
    },
    include_package_data=True,
    license="BSD license",
    zip_safe=False,
    keywords=["resource", "monitor", "system", "utilization"],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.10",
    ],
    test_suite="tests",
    install_requires=[
        "click",
        "connectorx>=0.3.1",
        "plotly",
        "polars~=0.17.9",
        "psutil",
        "pyarrow",
        "pydantic",
    ],
    extras_require={
        "dev": [
            "black",
            "flake8",
            "pre-commit",
            "pylint",
            "pytest",
            "pytest-cov",
        ],
    },
)
