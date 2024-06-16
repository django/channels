from unittest import mock

from asgiref.testing import ApplicationCommunicator as BaseApplicationCommunicator


def no_op():
    pass


class ApplicationCommunicator(BaseApplicationCommunicator):
    async def send_input(self, message):
        with mock.patch("channels.db.close_old_connections", no_op):
            return await super().send_input(message)

    async def receive_output(self, timeout=1):
        with mock.patch("channels.db.close_old_connections", no_op):
            return await super().receive_output(timeout)
