import logging

from channels import Group

logger = logging.getLogger(__name__)


TEST_GROUP = "test-group"


def ws_connect(message):
    logger.debug("Received ws connect")
    path = message.content['path']
    if path.endswith("group/"):
        logger.debug("Connect request for group channel, adding to group channel")
        Group(TEST_GROUP).add(message.reply_channel)


def ws_disconnect(message):
    logger.debug("Received ws disconnect")
    path = message.content['path']
    if path.endswith("group/"):
        logger.debug("Disconnect request for group channel, removing from group channel")
        Group(TEST_GROUP).discard(message.reply_channel)


def ws_message(message):
    """Echoes messages back to the client"""
    logger.debug("Received ws message: {}".format(message))

    path = message.content['path']

    if path.endswith("group/"):
        logger.debug("Message is on group channel, going to send a response to the group...")
        message.reply_channel.send({'content': 'Message received on group channel, sening response to group'})
        Group(TEST_GROUP).send({
            'text': message.content['text']
        })
    else:
        logger.debug("Message received on echo channel, sending echo..")
        message.reply_channel.send(
            {'text': message.content['text']}
        )
