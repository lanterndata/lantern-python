import setuptools

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='lantern-pinecone',
    version='0.0.7',
    description='Pinecone compatiable client for Lantern',
    url='https://github.com/lanterndata/lantern-python',
    author='Varik Matevosyan',
    author_email='varik@lantern.dev',
    license='BSL 1.1',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    project_urls = {
        "Bug Tracker": "https://github.com/lanterndata/lantern-python/issues",
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir = {"lantern_pinecone": "src"},
    python_requires = ">=3.8",
    install_requires= [
      'lantern-client ==0.0.5',
      'tqdm ==4.66.1',
      'pinecone-client ==2.2.4'
    ]
)
