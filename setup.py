from setuptools import setup, find_packages

long_description = 'Performance monitoring CLI tool for Apple Silicon'

setup(
    name='asitop',
    version='0.0.25',
    author='Timothy Liu, binlecode',
    author_email='tlkh.xms@gmail.com, bin.le.code@gmail.com',
    url='https://github.com/binlecode/silitop',
    description='Performance monitoring CLI tool for Apple Silicon',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    packages=find_packages(),
    entry_points={
            'console_scripts': [
                'asitop = asitop.asitop:main'
            ]
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ),
    keywords='asitop',
    install_requires=[
        "dashing",
        "psutil",
    ],
    zip_safe=False
)
