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

    async def __call__(self, scope, receive, send):
        """
        ASGI constructor; can insert things into the scope, but not
        run asynchronous code.
        """
        # Copy scope to stop changes going upstream
        scope = dict(scope)
        # Allow subclasses to change the scope
        self.populate_scope(scope)
        # Partially bind it to our coroutine entrypoint along with the scope
        return await self.coroutine_call(self.inner, scope, receive, send)

    async def coroutine_call(self, inner, scope, receive, send):
        """
        ASGI coroutine; where we can resolve items in the scope
        (but you can't modify it at the top level here!)
        """
        await self.resolve_scope(scope)
        await inner(scope, receive, send)
