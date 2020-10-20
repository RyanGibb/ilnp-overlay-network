import network

# TODO add port number for multiplexing

def send(locator, message):
    # TODO add name resolution (FQDN -> locator)
    network.send(locator, message)

def receive():
    # TODO embed ILNP header info (and skinny transport header info - e.g. port)
    return network.receive()
