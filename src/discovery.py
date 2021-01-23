import struct

import util
from util import NetworkException

# hostnames   -> identifiers
hst_to_nid = {}
# identifiers -> locators
nid_to_locs = {}


def getaddrinfo(hostname, port):
    nid = hst_to_nid.get(hostname)
    if nid == None:
        raise NetworkException("No mapping for hostname: '%s'" % hostname)
    return (nid, port)


def get_locs(nid):
    locs = nid_to_locs.get(nid)
    if locs == None:
        raise NetworkException("No mapping for nid: '%s'" % nid)
    return list(locs)


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
    
    hst_to_nid[hst] = nid
    # Can have multiple locators for one nid
    nid_to_locs.setdefault(nid, set()).add(loc)

    if log_file != None:
        util.write_log(log_file, "\n\t%s\n\t%s" % (
            "%s => %s" % (hst, hst_to_nid[hst]),
            "%s => %s" % (nid, nid_to_locs[nid])
        ))

    if solititation:
        return get_advertisement(recieved_interface)
    else:
        return None


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

    global wait_time
    wait_time = config_section.getint("wait_time")

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
    

    