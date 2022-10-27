from setuptools import find_packages, setup

from channels import __version__

setup(
    name="channels",
    version=__version__,
    url="http://github.com/django/channels",
    author="Django Software Foundation",
    author_email="foundation@djangoproject.com",
    description="Brings async, event-driven capabilities to Django 3.2 and up.",
    license="BSD",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    python_requires=">=3.7",
    install_requires=[
        "Django>=3.2",
        "asgiref>=3.5.0,<4",
    ],
    extras_require={
        "tests": [
            "pytest",
            "pytest-django",
            "pytest-asyncio",
            "async-timeout",
            "coverage~=4.5",
        ],
        "daphne": [
            "daphne>=4.0.0",
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
        "Framework :: Django :: 3",
        "Framework :: Django :: 3.2",
        "Framework :: Django :: 4",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Topic :: Internet :: WWW/HTTP",
    ],
)
