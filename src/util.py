import sys
import os
import socket
import configparser
from pathlib import Path
from datetime import datetime

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "config.ini")

CONFIG_LINK_SECTION      = "link"
CONFIG_NETWORK_SECTION   = "network"
CONFIG_TRANSPORT_SECTION = "transport"


class NetworkException(Exception):
    def __init__(self, message):
        self.message = message


def int_to_bytes(integer, number_of_bytes):
    return integer.to_bytes(number_of_bytes, byteorder="big", signed=False)

def hex_to_bytes(hexadecimal, number_of_bytes):
    hexadecimal_joined = "".join([x.zfill(4) for x in hexadecimal.split(":")])
    integer = int(hexadecimal_joined, 16)
    return int_to_bytes(integer, number_of_bytes)

def bytes_to_int(binary):
    return int.from_bytes(binary, byteorder="big", signed=False)

def bytes_to_hex(binary):
    # integer = bytes_to_int(binary)
    # hexadecimal = format(integer, "x")
    return ":".join([
        format(
            int.from_bytes(
                binary[2*i:2*i+2],
                byteorder="big"
            ),
            "x"
        ) for i in range(int(len(binary)/2))
    ])


def get_log_file_path(log_type):
    path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "logs",
        "%s_%s.log" % (log_type, config["discovery"]["hostname"])
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    return path


def write_log(log_file, message):
    log_file.write("%s %s\n" % (datetime.now(), message))
    log_file.flush()


def startup():
    global config
    # If passed additional argument, take it as the configuration filepath
    filepath = CONFIG_FILE if len(sys.argv) < 2 else sys.argv[1]
    config = configparser.ConfigParser()
    config.read(filepath)

startup()
