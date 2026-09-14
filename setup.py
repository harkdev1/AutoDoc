from setuptools import setup, find_packages

setup(
    name="autodoc",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "google-genai",
    ],
    entry_points={
        "console_scripts": [
            "autodoc=autodoc.cli:cli",
        ],
    },
)