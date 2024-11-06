import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lantern-client",
    version="0.0.5",
    description="Python client for Lantern",
    url="https://github.com/lanterndata/lantern-python",
    author="Varik Matevosyan",
    author_email="varik@lantern.dev",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Bug Tracker": "https://github.com/lanterndata/lantern-python/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=["lantern"],
    package_dir={"lantern": "."},
    python_requires=">=3.8",
    install_requires=["psycopg2-binary ==2.9.10", "numpy"],
)
