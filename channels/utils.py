import fnmatch
import types


def name_that_thing(thing):
    """
    Returns either the function/class path or just the object's repr
    """
    # Instance method
    if hasattr(thing, "im_class"):
        # Mocks will recurse im_class forever
        if hasattr(thing, "mock_calls"):
            return "<mock>"
        return name_that_thing(thing.im_class) + "." + thing.im_func.func_name
    # Other named thing
    if hasattr(thing, "__name__"):
        if hasattr(thing, "__class__") and not isinstance(thing, (types.FunctionType, types.MethodType)):
            if thing.__class__ is not type and not issubclass(thing.__class__, type):
                return name_that_thing(thing.__class__)
        if hasattr(thing, "__self__"):
            return "%s.%s" % (thing.__self__.__module__, thing.__self__.__name__)
        if hasattr(thing, "__module__"):
            return "%s.%s" % (thing.__module__, thing.__name__)
    # Generic instance of a class
    if hasattr(thing, "__class__"):
        return name_that_thing(thing.__class__)
    return repr(thing)


def apply_channel_filters(channels, only_channels, exclude_channels):
    """
    Applies our include and exclude filters to the channel list and returns it
    """
    if only_channels:
        channels = [
            channel for channel in channels
            if any(
                fnmatch.fnmatchcase(channel, pattern)
                for pattern in only_channels
            )
        ]
    if exclude_channels:
        channels = [
            channel for channel in channels
            if not any(
                fnmatch.fnmatchcase(channel, pattern)
                for pattern in exclude_channels
            )
        ]
    return channels
