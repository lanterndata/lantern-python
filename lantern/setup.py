import setuptools

with open("README.md", "r", encoding = "utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='lantern-client',
    version='0.0.2',    
    description='Python client for Lantern',
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
    package_dir = {"lantern": "src"},
    python_requires = ">=3.6",
    install_requires= [
      'psycopg2 ==2.9.9',
      'numpy ==1.26.2'
    ]
)
