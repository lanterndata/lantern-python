import setuptools
from setuptools import find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='lantern-django',
    version='0.0.0',
    description='Django client for Lantern',
    url='https://github.com/lanterndata/lantern-python',
    author='Di Qi',
    author_email='di@lantern.dev',
    license='BSL 1.1',
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
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[
        'django',
        'numpy'
    ]
)
