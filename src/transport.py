import network

# TODO add port number for multiplexing
# TODO add socket object to keep track of state like port and buffers


def send(addr, message):
    locator    = ":".join(addr.split(":")[:4])
    identifier = ":".join(addr.split(":")[4:])
    network.send(locator, identifier, message.encode('utf-8'))


def receive():
    data, src_identifier, src_locator, dst_identifier, dst_locator = network.receive()
    message = data.decode('utf-8')
    return message, ":".join([src_identifier, src_locator]), ":".join([dst_identifier, dst_locator])
