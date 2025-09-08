#!/usr/bin/env python3
"""
Setup script for DLNA Streamer package.
"""

from setuptools import find_packages, setup


# Read the README file for long description
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]


setup(
    name="dlna-streamer",
    version="1.0.0",
    author="Sebastian Yde Madsen",
    author_email="your-email@example.com",  # Replace with actual email
    description="A professional Python DLNA/UPnP media streaming application",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/dlna-streamer",  # Replace with actual URL
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Video",
        "Topic :: System :: Networking",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    entry_points={
        "console_scripts": [
            "dlna-stream=dlna_streamer.cli:main",
            "dlna-gui=dlna_streamer.gui:launch",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
