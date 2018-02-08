class PermissionsMixin(object):
    """
    Mixin to check if user has the correct permissions
    """
    perm = 'consumer.changeme'

    def websocket_connect(self, message):
        if self.has_permission():
            return super().websocket_connect(message)

        return self.close(code=-1)

    def has_permission(self):
        '''
        Check for connect permissions
        '''
        if self.perm:
            if self.scope["user"] and self.scope["user"].is_authenticated and self.scope["user"].has_perms(self.perm):
                return True

        return False


class AsyncPermissionsMixin(object):
    """
    Mixin to check if user has the correct permissions
    """
    perm = 'consumer.changeme'

    async def websocket_connect(self, message):
        if self.has_permission():
            return await super().websocket_connect(message)

        return await self.close(code=-1)

    def has_permission(self):
        '''
        Check for connect permissions
        '''
        if self.perm:
            if self.scope["user"] and self.scope["user"].is_authenticated and self.scope["user"].has_perms(self.perm):
                return True

        return False
