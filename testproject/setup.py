from setuptools import find_packages, setup

setup(
    name='channels-benchmark',
    packages=find_packages(),
    py_modules=['benchmark'],
    install_requires=['autobahn', 'Twisted'],
)
