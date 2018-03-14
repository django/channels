from importlib import import_module

from asgiref.testing import ApplicationCommunicator
from django.conf import settings

from ..auth import login, logout
from ..db import database_sync_to_async


class AuthCommunicator(ApplicationCommunicator):
    """
    ApplicationCommunicator subclass with authentication helpers.
    """

    async def login(self):
        """
        Logs a user in if found in the scope.
        """
        if self.scope["user"]:
            # The session might have been set by the SessionMiddleware
            if not self.scope.get("session"):
                engine = import_module(settings.SESSION_ENGINE)
                self.scope["session"] = engine.SessionStore()
            await login(self.scope, self.scope["user"])
            await database_sync_to_async(self.scope["session"].save)()

    async def logout(self):
        """
        Logs a scope's user out.
        """
        await logout(self.scope)
