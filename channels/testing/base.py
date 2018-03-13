from importlib import import_module

from asgiref.testing import ApplicationCommunicator
from django.conf import settings

from ..auth import login
from ..db import database_sync_to_async


class AuthCommunicator(ApplicationCommunicator):
    """
    ApplicationCommunicator subclass that logs in if scope has a user.
    """

    async def login(self):
        """
        Logs in if scope has a user.
        """
        if self.scope["user"]:
            # The session might have been set by the SessionMiddleware
            if not self.scope.get("session"):
                engine = import_module(settings.SESSION_ENGINE)
                self.scope["session"] = engine.SessionStore()
            await login(self.scope, self.scope["user"])
            await database_sync_to_async(self.scope["session"].save)()
