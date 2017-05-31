import json


class JSON_Dict(dict):
    '''Convenience class for Channels' send() method when all you want to send is
    JSON text. Use this class as you would a (write-only) dictionary; all data
    will be automatically converted to the format Channels expects.

    You can add and change dictionary keys, as well as deleting them, all as you
    normally would with a dictionary. However, attempting to read them normally
    will raise KeyError (a consequence of having to deceive Channels). Instead,
    use the get_key method to read a value.

    Finally, the key 'text' is reserved and can't be used. Attempting to do so
    will raise ValueError.'''

    def __init__(self, input_dict=None, **kwargs):
        '''Initialize the instance with a single dictionary instance or subclass
        thereof or with keyword arguments defining the keys and values of the
        dictionary.'''
        if input_dict:
            if not isinstance(input_dict, dict):
                raise TypeError('input_dict must be a dictionary or a subclass thereof.')
            kwargs.update(input_dict)
        if 'text' in kwargs:
            raise ValueError("The key name 'text' is reserved.")
        self._data = kwargs
        self._update_text()

    def get_key(self, key):
        '''Call this method instead of instance[key] to read the value of a key.'''
        return self._data[key]

    def update(self, *args, **kwargs):
        __doc__ = self._data.update.__doc__
        [__doc__] # Silence test complaint about __doc__ being assigned but not used.
        self._data.update(*args, **kwargs)
        self._update_text()

    def __setitem__(self, key, value, autocall=False):
        if key == 'text':
            if autocall:
                dict.__setitem__(self, key, value)
            else:
                raise ValueError("The key name 'text' is reserved.")
        else:
            dict.__setitem__(self._data, key, value)
            self._update_text()

    def __delitem__(self, key):
        if key == 'text':
            raise ValueError("The key name 'text' is reserved.")
        del self._data[key]
        self._update_text()
    
    def __repr__(self):
        return 'JSON_Dict({})'.format(repr(self._data))

    def __str__(self):
        return str(self._data)

    def _update_text(self):
        self.__setitem__('text', json.dumps(self._data), autocall=True)
