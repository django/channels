from importlib import import_module

from django.conf import settings

from asgiref.testing import ApplicationCommunicator

from ..auth import login, logout
from ..db import database_sync_to_async


class AuthCommunicator(ApplicationCommunicator):
    """
    ApplicationCommunicator subclass with authentication helpers.
    """
    
    def get_new_session(self):
        """
        Returns a new session object.
        """
        engine = import_module(settings.SESSION_ENGINE)
        return engine.SessionStore()

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
