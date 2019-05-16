from typing import NoReturn


def monkeypatch_django() -> NoReturn:
    """
    Monkeypatches support for us into parts of Django.
    """
    # Ensure that the staticfiles version of runserver bows down to us
    # This one is particularly horrible
    from django.contrib.staticfiles.management.commands.runserver import (
        Command as StaticRunserverCommand,
    )
    from channels.management.commands.runserver import Command as RunserverCommand

    StaticRunserverCommand.__bases__ = (RunserverCommand,)
