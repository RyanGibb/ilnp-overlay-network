
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
