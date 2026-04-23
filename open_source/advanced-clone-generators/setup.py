from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="advanced-clone-generators",
    version="1.0.0",
    author="IntegrityDesk",
    author_email="contact@integritydesk.example.com",
    description="Advanced clone type generators for code plagiarism detection benchmarking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/integritydesk/advanced-clone-generators",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Security",
    ],
    python_requires=">=3.8",
    install_requires=[
        # Core dependencies only
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black",
            "flake8",
            "mypy",
        ],
    },
    keywords="plagiarism detection code clones benchmarking obfuscation",
    project_urls={
        "Bug Reports": "https://github.com/integritydesk/advanced-clone-generators/issues",
        "Source": "https://github.com/integritydesk/advanced-clone-generators",
        "Documentation": "https://github.com/integritydesk/advanced-clone-generators#readme",
    },
)</content>
<parameter name="filePath">/home/tsun/Documents/CodeProvenance/open_source/advanced-clone-generators/setup.py