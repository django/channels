Delay Server
============

Channels ships with an optional app called delay. It listens to messages on the channel
`channels.delay` and dispatches them at a later point in time. It can also repeat messages
on an interval.

Getting Started with Delay
==========================

To Install the app add `channels.delay` to `INSTALLED_APPS`::

    INSTALLED_APPS = (
        ...
        'channels',
        'channels.delay'
    )

Run `migrate` to create the tables

`python manage.py migrate`

Run the delay process to start accepting messages

`python manage.py rundelay`

Now you're ready to start delaying messages.

Delaying Messages
=================

The delay protocol has two options for delaying messages. To delay a message by a fixed number of seconds
use the `delay` parameter. To delay a message every X seconds use the `interval` parameter.

Here's an example of each::

    from channels import Channel

    delayed_message = {
        'channel': 'example_channel',
        'content': {'x': 1},
        'delay': 10
    }
    # The message will be delayed 10 seconds by the server and then sent
    Channel('channels.delay').send(delayed_message, immediately=True)

    delayed_message = {
        'channel': 'example_channel',
        'content': {'y': 2},
        'interval': 10
    }
    # The message will be delayed 10 seconds then sent. It will repeat that message every 10 seconds forever.
    Channel('channels.delay').send(delayed_message, immediately=True)
