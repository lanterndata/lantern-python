import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lantern-pinecone",
    version="0.0.8",
    description="Pinecone compatiable client for Lantern",
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
    packages=["lantern_pinecone"],
    package_dir={"lantern_pinecone": "."},
    python_requires=">=3.8",
    install_requires=[
        "lantern-client ==0.0.6",
        "tqdm >=4.66.3",
        "pinecone-client ==2.2.4",
    ],
)
