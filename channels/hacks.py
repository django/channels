import sys


def monkeypatch_django():
    """
    Monkeypatches support for us into parts of Django.
    """

    if (
        len(sys.argv) >= 2
        and sys.argv[0].endswith("manage.py")
        and sys.argv[1] == "runserver"
    ):
        # Ensure that the staticfiles version of runserver bows down to us
        # This one is particularly horrible
        from django.contrib.staticfiles.management.commands.runserver import (
            Command as StaticRunserverCommand,
        )

        from .management.commands.runserver import Command as RunserverCommand

        StaticRunserverCommand.__bases__ = (RunserverCommand,)
