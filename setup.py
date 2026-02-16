from setuptools import setup, find_packages

long_description = 'Performance monitoring CLI tool for Apple Silicon'

setup(
    name='agtop',
    version='0.1.2',
    author='Timothy Liu, binlecode',
    author_email='tlkh.xms@gmail.com, bin.le.code@gmail.com',
    url='https://github.com/binlecode/agtop',
    description='Performance monitoring CLI tool for Apple Silicon',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    packages=find_packages(),
    entry_points={
            'console_scripts': [
                'agtop = agtop.agtop:main',
            ]
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ),
    keywords='agtop apple-silicon powermetrics',
    install_requires=[
        "dashing",
        "psutil",
    ],
    extras_require={
        "dev": [
            "ruff",
        ],
    },
    zip_safe=False
)
