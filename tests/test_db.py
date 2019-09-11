import pytest

pytest_plugins = ["pytester"]


@pytest.mark.django_db
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "db_engine", ("django.db.backends.sqlite3", "django.db.backends.postgresql")
)
@pytest.mark.parametrize("conn_max_age", (0, 600))
async def test_database_sync_to_async(db_engine, conn_max_age, testdir):
    if db_engine == "django.db.backends.postgresql":
        pytest.importorskip("psycopg2")

    testdir.makeconftest(
        """
        from django.conf import settings

        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": %r,
                    "CONN_MAX_AGE": %d,
                    "NAME": "channels_tests",
                }
            },
            INSTALLED_APPS=[
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.admin",
                "channels",
            ],
        )
        """
        % (db_engine, conn_max_age)
    )
    p1 = testdir.makepyfile(
        """
        import pytest
        from channels.db import database_sync_to_async

        @pytest.mark.asyncio
        @pytest.mark.django_db
        async def test_inner():
            from django.contrib.auth.models import User
            from django.db import connections

            conn = connections["default"]
            assert conn.in_atomic_block

            assert User.objects.count() == 0

            @database_sync_to_async
            def create_obj(**kwargs):
                User.objects.create(**kwargs)

            await create_obj(username="alice")
            await create_obj(username="bob")
            assert User.objects.count() == 2

        @pytest.mark.django_db
        def test_check_rolled_back():
            from django.contrib.auth.models import User
            assert User.objects.count() == 0
        """
    )
    result = testdir.runpytest_subprocess(str(p1))
    assert result.ret == 0
