import multiprocessing

import pytest
from django.conf import settings

from channels.testing.live import make_application


def _load_application(connection):
    """
    Load the test routing module in a fresh interpreter.

    Runs in a spawned child process, where Django is not set up:
    importing a routing module that imports models must still work,
    because make_application() sets Django up itself.
    """
    settings.ASGI_APPLICATION = "tests.sample_project.config.routing.application"
    try:
        application = make_application(static_wrapper=None)
    except BaseException as e:
        connection.send(("error", "%s: %s" % (type(e).__name__, e)))
    else:
        connection.send(("ok", type(application).__name__))
    finally:
        connection.close()


def test_make_application_in_fresh_interpreter():
    """
    The live server application loads without pre-loaded Django apps.

    Regression test for the Python 3.14 forkserver default: the server
    process is a fresh interpreter, so make_application() must set
    Django up itself before importing the application.
    """
    context = multiprocessing.get_context("spawn")
    parent_conn, child_conn = context.Pipe(duplex=False)
    process = context.Process(target=_load_application, args=(child_conn,))
    process.start()
    child_conn.close()
    try:
        assert parent_conn.poll(60), "loader process timed out"
        try:
            status, payload = parent_conn.recv()
        except EOFError:
            process.join(timeout=60)
            pytest.fail(
                "loader process exited without a result (exit code %s)"
                % process.exitcode
            )
    finally:
        process.join(timeout=60)
        parent_conn.close()
    assert process.exitcode == 0
    assert status == "ok", payload
