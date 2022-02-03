from setuptools import find_packages, setup
from channels import __version__

setup(
    name='channels',
    version=__version__,
    url='http://github.com/django/channels',
    author='Django Software Foundation',
    author_email='foundation@djangoproject.com',
    description="Brings async, event-driven capabilities to Django. Django 2.2 and up only.",
    license='BSD',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    python_requires='>=3.7',
    install_requires=[
        'Django>=2.2',
        'asgiref>=3.5.0,<4',
        'daphne>=3.0,<4',
    ],
    extras_require={
        'tests': [
            "pytest",
            "pytest-django",
            "pytest-asyncio",
            "async-timeout",
            "coverage~=4.5",
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Framework :: Django',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
