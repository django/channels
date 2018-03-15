from importlib import import_module

from django.conf import settings

from asgiref.testing import ApplicationCommunicator

from ..auth import login, logout
from ..db import database_sync_to_async


class AuthCommunicator(ApplicationCommunicator):
    """
    ApplicationCommunicator subclass with authentication helpers.
    """

    def __init__(self, application, scope, user):
        """
        Adds user and session to the scope.
        """
        if user:
            engine = import_module(settings.SESSION_ENGINE)
            scope.update({
                "user": user,
                "session": engine.SessionStore(),
            })
        super().__init__(application, scope)

    async def login(self):
        """
        Logs a user in if found in the scope.
        """
        if self.scope.get("user"):
            await login(self.scope, self.scope["user"])
            await database_sync_to_async(self.scope["session"].save)()

    async def logout(self):
        """
        Logs a scope's user out.
        """
        await logout(self.scope)
