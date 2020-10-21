import network

# TODO add port number for multiplexing


def send(locator, message):
    # TODO add name resolution (FQDN -> nid & locator)
    network.send(locator, message.encode('utf-8'))


def receive():
    data = network.receive()
    message = data.decode('utf-8')
    # TODO embed ILNP header info (and skinny transport header info - e.g. port)
    return message
