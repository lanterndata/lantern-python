import setuptools

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='lantern-pinecone',
    version='0.0.3',    
    description='Pinecone compatiable client for Lantern',
    url='https://github.com/lanterndata/lantern-python-client',
    author='Varik Matevosyan',
    author_email='varik@lantern.dev',
    license='BSL 1.1',
    long_description = long_description,
    long_description_content_type = "text/markdown",
    project_urls = {
        "Bug Tracker": "https://github.com/lanterndata/lantern-python-client/issues",
    },
    classifiers = [
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir = {"lantern_pinecone": "src"},
    python_requires = ">=3.6",
    install_requires= [
      'lantern-client ==0.0.2',
      'tqdm ==4.66.1',
      'pinecone-client ==2.2.4'
    ]
)
