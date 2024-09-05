from setuptools import setup

version = "0.2.dev0"

long_description = "\n\n".join([open("README.rst").read(), open("CHANGES.rst").read()])

install_requires = [
    "click",
    "netCDF4",
    "pandas",
    "threedi-api-client>=4.0.0",
    "threedigrid>=1.0.16",
]
tests_require = [
    "pytest",
    "pytest-cov",
    "pytest-black",
    "pytest-flakes",
]

setup(
    name="batch-calculator",
    version=version,
    description="3Di batch calculations",
    long_description=long_description,
    # Get strings from http://www.python.org/pypi?%3Aaction=list_classifiers
    classifiers=["Programming Language :: Python", "Framework :: Django"],
    keywords=[],
    author="Daan van Ingen",
    author_email="daan.vaningen@nelen-schuurmans.nl",
    url="https://github.com/nens/batch-calculator",
    license="MIT",
    packages=["batch_calculator"],
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    extras_require={
        "test": tests_require
    },
    entry_points={
        "console_scripts": [
            "run-rain-series-simulations = batch_calculator.rain_series_simulations:create_rain_series_simulations",
            "process-rain-series-results = batch_calculator.process_results:process_results",
        ]
    },
)
