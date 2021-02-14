import struct
import time

import util
from util import NetworkException

DISCOVERY_NEXT_HEADER = 43

# hostname   -> [ (loc, nid, timestamp) ]
host_map = {}

# (identifier, locator) -> (hostname, timestamp)
inverse_host_map = {}


def getaddrinfo(addr):
    hst, port = addr
    entries = host_map.get(hst)
    if entries != None:
        valid_entries = []
        for loc, nid, timestamp in entries:
            if time.time() - timestamp < ttl:
                valid_entries.append((loc, nid, timestamp))
        if len(valid_entries) == 0:
            host_map[hst] = None
            valid_entries = None
        elif len(entries) > len(valid_entries):
            host_map[hst] = valid_entries
        entries = valid_entries
    if entries == None:
        raise NetworkException("No mapping for hostname '%s'" % hst)
    # TODO more sophisticated choice
    entry = entries[0]
    loc, nid, _ = entry
    return loc, nid, port


def gethostbyaddr(addr):
    loc, nid, port = addr
    key = (loc, nid)
    entry = inverse_host_map.get(key)
    if entry != None:
        hst, timestamp = entry
        # If mapping expired
        if time.time() - timestamp > ttl:
            inverse_host_map[key] = None
            entry = None
    if entry == None:
        raise NetworkException("No mapping for addr '%s:%s'" % (loc, nid))
    return hst, port


def get_solititation(loc, nid):
    message = struct.pack("!8s8s?",
        # implicit advertisement
        util.hex_to_bytes(nid, 8),
        util.hex_to_bytes(loc, 8),
        # solititation
        True,
    )
    # null terminated string
    message += local_hst.encode('utf-8')
    return message


def get_advertisement(loc, nid):
    message = struct.pack("!8s8s?",
        util.hex_to_bytes(nid, 8),
        util.hex_to_bytes(loc, 8),
        # not solititation
        False,
    )
    message += local_hst.encode('utf-8')
    return message


def process_message(message, recieved_interface):
    timestamp = time.time()

    # 17 bytes of struct
    message_struct = message[:17]
    (
        nid_bytes,
        loc_bytes,
        solititation,
    ) = struct.unpack("!8s8s?", message_struct)
    nid = util.bytes_to_hex(nid_bytes)
    loc = util.bytes_to_hex(loc_bytes)
    hst = message[17:].decode('utf-8')
    
    inverse_host_map[(loc, nid)] = hst, timestamp
    
    entries = host_map.get(hst)
    if entries == None:
        host_map[hst] = [(loc, nid, timestamp)]
    else:
        already_mapped = False
        for i in range(len(entries)):
            l, n, _ = entries[i]
            if l == loc and n == nid:
                already_mapped = True
                # update timestamp
                entries[i] = loc, nid, timestamp
                break
        if not already_mapped:
            entries.append((loc, nid, timestamp))
        host_map[hst] = entries

    if log_file != None:
        util.write_log(log_file, "\n\t%s\n\t%s" % (
            "%s => %s" % (hst, host_map[hst]),
            "%s:%s => %s" % (loc, nid, inverse_host_map[(loc, nid)])
        ))

    return solititation


# Update host coresponding to (loc, nid) if it exists
def locator_update(loc, nid, new_locs):
    timestamp = time.time()
    entry = inverse_host_map.get((loc, nid))
    if entry != None:
        hst, _
        host_map[hst] = [(loc, nid, timestamp) for loc in new_locs]
        if log_file != None:
            util.write_log(log_file, "\n\t%s" % (
                "%s => %s" % (nid, nid_to_locs[nid])
            ))


def startup():
    config_section = util.config["discovery"]

    global log_file
    log_file = util.get_log_file("discovery")

    # local hostname
    global local_hst
    local_hst = config_section["hostname"]

    # Time between sending solititations in seconds
    global wait_time, ttl
    if "wait_time" in config_section:
        wait_time = config_section["wait_time"]
    else:
        wait_time = 10
    # discovery TTL is 3 times the wait time
    ttl = 3 * wait_time
