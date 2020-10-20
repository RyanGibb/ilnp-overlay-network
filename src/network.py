import link

def send(locator, message):
    # TODO build ILNP header
    # TODO add address resolution and forwarding table
    # (locator -> interface, where an interface is a multicast group)
    interface = link.get_mcast_grp(locator, link.PackageType.DATA_PACKAGE)
    link.send(interface, message)

def receive():
    interface, message = link.receive()
    # TODO check if destination locator & nid is this machine
    return message
