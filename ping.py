import os, math, struct, socket, select
from timeit import default_timer as timer

# From RFC792
ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_MAX_RECV = 2048
ICMP_HEADER_FORMAT = "!BBHHH"

# Credit to https://github.com/kyan001/ping3
def ones_comp_sum16(num1: int, num2: int) -> int:
    """Calculates the 1's complement sum for 16-bit numbers.
    Args:
        num1: 16-bit number.
        num2: 16-bit number.
    Returns:
        The calculated result.
    """

    carry = 1 << 16
    result = num1 + num2
    return result if result < carry else result + 1 - carry

# Credit to https://github.com/kyan001/ping3
def internet_checksum(source):
    """Calculates the checksum of the input bytes.
    RFC1071: https://tools.ietf.org/html/rfc1071
    RFC792: https://tools.ietf.org/html/rfc792
    Args:
        source: The input to be calculated.
    Returns:
        Calculated checksum.
    """
    if len(source) % 2:  # if the total length is odd, padding with one octet of zeros for computing the checksum
        source += b'\x00'
    sum = 0
    for i in range(0, len(source), 2):
        sum = ones_comp_sum16(sum, (source[i + 1] << 8) + source[i])
    return ~sum & 0xffff



class Ping():
    """
    This class handles information related to the ping request
    It stores the destination of the ping as well as other relavent information
    """
    def __init__(self, destination, timeout=1000, packet_size=55, id=None):
        self.destination = destination
        self.timeout = timeout
        self.packet_size = packet_size
        self.id = id
        self.sequence_number = 0
        self.sent = 0
        self.received = 0
        self.min_time = math.inf
        self.max_time = 0
        self.total_time = 0

        if self.id is None:
            self.id = os.getpid() & 0xFFFF


    def run(self, max_count = 3):
        """
        Continually sends and receives ping messages until count or timeout is reached

        Args:
            max_count: integer - maximum number of pings to send
        Returns:
            Does not return, prints message to console
        """
        start_time = timer()
        count = 0
        while count < max_count and timer() - start_time < self.timeout:
            ping_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
            ping_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            ping_sent = self.send(ping_socket)
            self.sent += 1

            ping_received = self.receive(ping_socket, self.id, self.timeout)
            if ping_received is not None:
                self.received += 1
                round_trip_time = ping_received - ping_sent
                if round_trip_time > self.max_time:
                    self.max_time = round_trip_time
                if round_trip_time < self.min_time:
                    self.min_time = round_trip_time
            else:
                print("Failed to receive ping")
            count += 1
        if count < max_count:
            print("Process timed out")
        else:
            self.total_time = timer() - start_time
            print("Pings Sent:\t{}".format(self.sent))
            print("Ping Received:\t{}".format(self.received))
            print("Pings Dropped:\t{}".format(self.sent - self.received))
            print("Maximum Time:\t{}".format(self.max_time))
            print("Minimum Time:\t{}".format(self.min_time))
            print("Average Time:\t{}".format(self.total_time / self.received))




    def send(self, sock):
        """
        Sends a single ping

        Args:
            sock: socket - socket to use for connection
        Returns:
            time that the ping was sent
        """
        checksum = 0

        header = struct.pack(
            ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, checksum, self.id, self.sequence_number
        )
        padding = (56 - struct.calcsize("!d")) * "Q"
        payload = struct.pack("!d", timer()) + padding.encode()

        checksum = internet_checksum(header + payload)

        header = struct.pack(
            ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, socket.htons(checksum), self.id, self.sequence_number
        )

        packet = header + payload
        sent_time = timer()

        try:
            sock.sendto(packet, (self.destination, 1))
            self.sequence_number += 1
        except socket.error as e:
            print("Ping failed with error: {}".format(e))
            sock.close()
            return

        return sent_time


    def receive(self, sock, id, timeout):
        """
        Receives a single ping

        Args:
            sock: socket - socket to receive the ping with
            id: integer - id of the ping message we want the response to
            timeout: integer - amount of time to wait
        Returns:
            Current nothing, prints message to console.
            Eventually should return received time and/or other information to
            be used by the run function
        """
        start_receiving = timer()
        while timer() - start_receiving < timeout:
            receive_attempt = select.select([sock], [], [], timeout)
            if receive_attempt[0] == []:
                print("Recieve attempt timed out")
                return # Timed out

            received_time = timer()
            packet, addr = sock.recvfrom(ICMP_MAX_RECV)
            header = packet[20:28]
            type, code, checksum, packet_id, sequence_number = struct.unpack(
                "!BBHHH", header
            )

            if type != ICMP_ECHO_REQUEST and packet_id == id:
                return received_time

            return None



# Used for testing only
if __name__ == "__main__":
    current_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
    current_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    myPing = Ping("127.0.0.1")
    myPing.send(current_socket)
