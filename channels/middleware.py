from functools import partial
from typing import Callable

from channels.typing import Scope


class BaseMiddleware:
    """
    Base class for implementing ASGI middleware. Inherit from this and
    override the setup() method if you want to do things before you
    get to.

    Note that subclasses of this are not self-safe; don't store state on
    the instance, as it serves multiple application instances. Instead, use
    scope.
    """

    def __init__(self, inner):
        """
        Middleware constructor - just takes inner application.
        """
        self.inner = inner

    # TODO what does partial return?
    # should not be supported for now https://github.com/python/mypy/issues/1484
    def __call__(self, scope: Scope):
        """
        ASGI constructor; can insert things into the scope, but not
        run asynchronous code.
        """
        # Copy scope to stop changes going upstream
        scope = dict(scope)
        # Allow subclasses to change the scope
        self.populate_scope(scope)
        # Call the inner application's init
        inner_instance = self.inner(scope)
        # Partially bind it to our coroutine entrypoint along with the scope
        return partial(self.coroutine_call, inner_instance, scope)

    async def coroutine_call(
        self, inner_instance, scope: Scope, receive: Callable, send: Callable
    ) -> None:
        """
        ASGI coroutine; where we can resolve items in the scope
        (but you can't modify it at the top level here!)
        """
        await self.resolve_scope(scope)
        await inner_instance(receive, send)

    def populate_scope(self, scope: Scope) -> None:
        raise NotImplementedError(
            "{} is missing the implementation of the method `populate_scope()`".format(
                self.__class__.__name__
            )
        )

    def resolve_scope(self, scope: Scope) -> None:
        raise NotImplementedError(
            "{} is missing the implementation of the method `resolve_scope()`".format(
                self.__class__.__name__
            )
        )
