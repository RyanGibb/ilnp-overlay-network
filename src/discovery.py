import struct

import util
from util import NetworkException

# out of band locator for discovery
# TODO make discovery in band
OOB_LOC = "ff:0:0:0"

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


def get_solititation():
    message = struct.pack("!8s?",
        # implicit advertisement
        util.hex_to_bytes(local_nid, 8),
        # solititation
        True,
    )
    # null terminated string
    message += local_hst
    return message


def get_advertisement():
    message = struct.pack("!8s?",
        util.hex_to_bytes(local_nid, 8),
        # not solititation
        False,
    )
    message += local_hst
    return message


def process_message(message, recived_loc):
    # 9 bytes of struct
    message_struct = message[:9]
    (
        nid_bytes,
        solititation,
    ) = struct.unpack("!8s?", message_struct)
    nid = util.bytes_to_hex(nid_bytes)
    hst = message[9:].decode('utf-8')
    
    hst_to_nid[hst] = nid
    # Can have multiple locators for one nid
    nid_to_locs.setdefault(nid, set()).add(recived_loc)

    if log_file != None:
        util.write_log(log_file, "%s\t%s" % (
            "%s => %s" % (hst, nid),
            "%s +> %s" % (nid, recived_loc)
        ))

    if solititation:
        return get_advertisement()
    else:
        return None


def startup(local_nid_param, locs_joined):
    config_section = util.config["discovery"]

    # local hostname
    global local_hst
    local_hst = config_section["hostname"].encode('utf-8')

    global wait_time
    wait_time = config_section.getint("wait_time")

    global local_nid
    local_nid = local_nid_param

    hst_to_nid[local_hst] = local_nid
    # Can have multiple locators for one nid
    nid_to_locs[local_nid] = set(locs_joined)

    global log_file
    if "log" in config_section and config_section.getboolean("log"):
        log_filepath = util.get_log_file_path("discovery")
        log_file = open(log_filepath, "a")
        util.write_log(log_file, "Started")
        for k in config_section:
            util.write_log(log_file, "\t%s = %s" % (k, config_section[k]))
    else:
        log_file = None
