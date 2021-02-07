import struct
import time

import util
from util import NetworkException

DISCOVERY_NEXT_HEADER = 43

# hostnames   -> identifiers
hst_to_nid = {}
# identifiers -> locators
nid_to_locs = {}

# identifiers -> hostnames
nid_to_hst = {}


def getaddrinfo(addr):
    hst, port = addr
    entry = hst_to_nid.get(hst)
    if entry != None:
        nid, timestamp = entry
        # If mapping expired
        if time.time() - timestamp > ttl:
            hst_to_nid[hst] = None
            entry = None
    if entry == None:
        raise NetworkException("No addr mapping for hostname '%s'" % hst)
    return nid, port


def gethostbyaddr(addr):
    nid, port = addr
    entry = nid_to_hst.get(nid)
    if entry != None:
        hst, timestamp = entry
        # If mapping expired
        if time.time() - timestamp > ttl:
            nid_to_hst[nid] = None
            entry = None
    if entry == None:
        raise NetworkException("No addr mapping for nid '%s'" % nid)
    return hst, port


def get_locs(nid):
    locs = nid_to_locs.get(nid)
    if locs != None:
        valid_locs = [(loc, timestamp) for loc, timestamp in locs if time.time() - timestamp < ttl]
        if len(valid_locs) == 0:
            nid_to_locs[nid] = None
            valid_locs = None
        elif len(locs) > len(valid_locs):
            nid_to_locs[nid] = valid_locs
        locs = valid_locs
    if locs == None:
        raise NetworkException("No locators mapping for nid '%s'" % nid)
    return [loc for loc, _ in locs]


def get_solititation(loc):
    message = struct.pack("!8s8s?",
        # implicit advertisement
        util.hex_to_bytes(local_nid, 8),
        util.hex_to_bytes(loc, 8),
        # solititation
        True,
    )
    # null terminated string
    message += local_hst.encode('utf-8')
    return message


def get_advertisement(loc):
    message = struct.pack("!8s8s?",
        util.hex_to_bytes(local_nid, 8),
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
    
    hst_to_nid[hst] = nid, timestamp
    nid_to_hst[nid] = hst, timestamp
    # Can have multiple locators for one nid
    locs = nid_to_locs.get(nid)
    if locs == None:
        nid_to_locs[nid] = [(loc, timestamp)]
    else:
        loc_already_mapped = False
        for i in range(len(locs)):
            mapped_loc, _ = locs[i]
            if mapped_loc == loc:
                loc_already_mapped = True
                # update timestamp
                locs[i] = loc, timestamp
                break
        if not loc_already_mapped:
            locs.append((loc, timestamp))
        nid_to_locs[nid] = locs

    if log_file != None:
        util.write_log(log_file, "\n\t%s\n\t%s\n\t%s" % (
            "%s => %s" % (hst, hst_to_nid[hst]),
            "%s => %s" % (nid, nid_to_hst[nid]),
            "%s => %s" % (nid, nid_to_locs[nid])
        ))

    if solititation:
        return get_advertisement(recieved_interface)
    else:
        return None


def locator_update(nid, new_locs):
    timestamp = time.time()
    nid_to_locs[nid] = [(loc, timestamp) for loc in new_locs]
    if log_file != None:
        util.write_log(log_file, "\n\t%s" % (
            "%s => %s" % (nid, nid_to_locs[nid])
        ))


def startup(local_nid_param, locs_joined):
    config_section = util.config["discovery"]

    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("discovery")
        log_file = open(log_filepath, "a")
        util.write_log(log_file, "Started")
        for k in config_section:
            util.write_log(log_file, "\t%s = %s" % (k, config_section[k]))
    else:
        log_file = None

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
    
    global local_nid
    local_nid = local_nid_param

    hst_to_nid[local_hst] = local_nid
    # Can have multiple locators for one nid
    nid_to_locs[local_nid] = set(locs_joined)

    if log_file != None:
        util.write_log(log_file, "\n\t%s\n\t%s" % (
            "%s => %s" % (local_hst, hst_to_nid[local_hst]),
            "%s => %s" % (local_nid, nid_to_locs[local_nid])
        ))
    

    