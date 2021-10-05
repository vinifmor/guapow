
import os

from setuptools import setup, find_packages

DESCRIPTION = (
    "On-demand and auto performance optimizer for Linux applications."
)

AUTHOR = "Vinícius Moreira"
AUTHOR_EMAIL = "vinicius_fmoreira@hotmail.com"
NAME = 'guapow'
URL = f'https://github.com/vinifmor/{NAME}'

file_dir = os.path.dirname(os.path.abspath(__file__))

with open(f'{file_dir}/requirements.txt') as f:
    requirements = [line.strip() for line in f.readlines() if line]


with open(f'{file_dir}/{NAME}/__init__.py') as f:
    exec(f.readlines()[4])


setup(
    name=NAME,
    version=eval('__version__'),
    description=DESCRIPTION,
    long_description=DESCRIPTION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    python_requires=">=3.8",
    url=URL,
    packages=find_packages(exclude=["tests.*", "tests"]),
    package_data={NAME: ["dist/daemon/*", "dist/daemon/systemd/root/*", "dist/daemon/systemd/user/*"]},
    include_package_data=True,
    install_requires=requirements,
    test_suite="tests",
    entry_points={
        "console_scripts": [
            f"{NAME}={NAME}.runner.main:run",
            f"{NAME}-cli={NAME}.cli.main:run",
            f"{NAME}-opt={NAME}.service.optimizer.main:start",
            f"{NAME}-watch={NAME}.service.watcher.main:start"
        ]
    },
    license="zlib/libpng",
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: zlib/libpng License',
        'Operating System :: POSIX :: Linux',
        'Topic :: System',
        'Topic :: Utilities'
    ]
)
