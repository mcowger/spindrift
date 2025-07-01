"""
XMODEM File Transfer Protocol Implementation

A blocking implementation of the XMODEM protocol adapted from the Carvera Controller
reference implementation. This module provides file upload and download functionality
that matches the exact behavior of the real Carvera machine.

The protocol uses:
- 8K blocks (xmodem8k mode) with CRC checking
- MD5 verification in the first block
- Mixed block sizes (128-byte and 8192-byte blocks)
- Blocking I/O operations during transfers
"""

import time
import hashlib
from typing import Optional, Callable, BinaryIO, Tuple

from .logging_config import setup_logging


# Protocol bytes
SOH = b"\x01"  # Start of Header (128-byte blocks)
STX = b"\x02"  # Start of Text (1024/8192-byte blocks)
EOT = b"\x04"  # End of Transmission
ACK = b"\x06"  # Acknowledge
DLE = b"\x10"  # Data Link Escape
NAK = b"\x15"  # Negative Acknowledge
CAN = b"\x16"  # Cancel
CRC = b"C"  # CRC mode request


class XMODEMProtocol:
    """
    XMODEM Protocol handler for file transfers.

    This implementation uses blocking I/O operations to match the behavior
    of the real Carvera machine, where file transfers block all other operations.
    """

    # CRC table from reference implementation
    crctable = [
        0x0000,
        0x1021,
        0x2042,
        0x3063,
        0x4084,
        0x50A5,
        0x60C6,
        0x70E7,
        0x8108,
        0x9129,
        0xA14A,
        0xB16B,
        0xC18C,
        0xD1AD,
        0xE1CE,
        0xF1EF,
        0x1231,
        0x0210,
        0x3273,
        0x2252,
        0x52B5,
        0x4294,
        0x72F7,
        0x62D6,
        0x9339,
        0x8318,
        0xB37B,
        0xA35A,
        0xD3BD,
        0xC39C,
        0xF3FF,
        0xE3DE,
        0x2462,
        0x3443,
        0x0420,
        0x1401,
        0x64E6,
        0x74C7,
        0x44A4,
        0x5485,
        0xA56A,
        0xB54B,
        0x8528,
        0x9509,
        0xE5EE,
        0xF5CF,
        0xC5AC,
        0xD58D,
        0x3653,
        0x2672,
        0x1611,
        0x0630,
        0x76D7,
        0x66F6,
        0x5695,
        0x46B4,
        0xB75B,
        0xA77A,
        0x9719,
        0x8738,
        0xF7DF,
        0xE7FE,
        0xD79D,
        0xC7BC,
        0x48C4,
        0x58E5,
        0x6886,
        0x78A7,
        0x0840,
        0x1861,
        0x2802,
        0x3823,
        0xC9CC,
        0xD9ED,
        0xE98E,
        0xF9AF,
        0x8948,
        0x9969,
        0xA90A,
        0xB92B,
        0x5AF5,
        0x4AD4,
        0x7AB7,
        0x6A96,
        0x1A71,
        0x0A50,
        0x3A33,
        0x2A12,
        0xDBFD,
        0xCBDC,
        0xFBBF,
        0xEB9E,
        0x9B79,
        0x8B58,
        0xBB3B,
        0xAB1A,
        0x6CA6,
        0x7C87,
        0x4CE4,
        0x5CC5,
        0x2C22,
        0x3C03,
        0x0C60,
        0x1C41,
        0xEDAE,
        0xFD8F,
        0xCDEC,
        0xDDCD,
        0xAD2A,
        0xBD0B,
        0x8D68,
        0x9D49,
        0x7E97,
        0x6EB6,
        0x5ED5,
        0x4EF4,
        0x3E13,
        0x2E32,
        0x1E51,
        0x0E70,
        0xFF9F,
        0xEFBE,
        0xDFDD,
        0xCFFC,
        0xBF1B,
        0xAF3A,
        0x9F59,
        0x8F78,
        0x9188,
        0x81A9,
        0xB1CA,
        0xA1EB,
        0xD10C,
        0xC12D,
        0xF14E,
        0xE16F,
        0x1080,
        0x00A1,
        0x30C2,
        0x20E3,
        0x5004,
        0x4025,
        0x7046,
        0x6067,
        0x83B9,
        0x9398,
        0xA3FB,
        0xB3DA,
        0xC33D,
        0xD31C,
        0xE37F,
        0xF35E,
        0x02B1,
        0x1290,
        0x22F3,
        0x32D2,
        0x4235,
        0x5214,
        0x6277,
        0x7256,
        0xB5EA,
        0xA5CB,
        0x95A8,
        0x8589,
        0xF56E,
        0xE54F,
        0xD52C,
        0xC50D,
        0x34E2,
        0x24C3,
        0x14A0,
        0x0481,
        0x7466,
        0x6447,
        0x5424,
        0x4405,
        0xA7DB,
        0xB7FA,
        0x8799,
        0x97B8,
        0xE75F,
        0xF77E,
        0xC71D,
        0xD73C,
        0x26D3,
        0x36F2,
        0x0691,
        0x16B0,
        0x6657,
        0x7676,
        0x4615,
        0x5634,
        0xD94C,
        0xC96D,
        0xF90E,
        0xE92F,
        0x99C8,
        0x89E9,
        0xB98A,
        0xA9AB,
        0x5844,
        0x4865,
        0x7806,
        0x6827,
        0x18C0,
        0x08E1,
        0x3882,
        0x28A3,
        0xCB7D,
        0xDB5C,
        0xEB3F,
        0xFB1E,
        0x8BF9,
        0x9BD8,
        0xABBB,
        0xBB9A,
        0x4A75,
        0x5A54,
        0x6A37,
        0x7A16,
        0x0AF1,
        0x1AD0,
        0x2AB3,
        0x3A92,
        0xFD2E,
        0xED0F,
        0xDD6C,
        0xCD4D,
        0xBDAA,
        0xAD8B,
        0x9DE8,
        0x8DC9,
        0x7C26,
        0x6C07,
        0x5C64,
        0x4C45,
        0x3CA2,
        0x2C83,
        0x1CE0,
        0x0CC1,
        0xEF1F,
        0xFF3E,
        0xCF5D,
        0xDF7C,
        0xAF9B,
        0xBFBA,
        0x8FD9,
        0x9FF8,
        0x6E17,
        0x7E36,
        0x4E55,
        0x5E74,
        0x2E93,
        0x3EB2,
        0x0ED1,
        0x1EF0,
    ]

    def __init__(
        self,
        getc: Callable[[int, float], Optional[bytes]],
        putc: Callable[[bytes, float], Optional[int]],
        mode: str = "xmodem8k",
        pad: bytes = b"\x1a",
    ):
        """
        Initialize XMODEM protocol handler.

        Args:
            getc: Function to read bytes from stream (size, timeout) -> bytes or None
            putc: Function to write bytes to stream (data, timeout) -> bytes_written or None
            mode: XMODEM mode ('xmodem' for 128-byte, 'xmodem8k' for 8192-byte blocks)
            pad: Padding character for incomplete blocks
        """
        self.getc = getc
        self.putc = putc
        self.mode = mode
        self.mode_set = False
        self.pad = pad
        self.log = setup_logging(logger_name="spindrift.xmodem")
        self.canceled = False

    def clear_mode_set(self):
        """Clear the mode set flag."""
        self.mode_set = False

    def abort(self, count: int = 2, timeout: float = 60):
        """
        Send an abort sequence using CAN bytes.

        Args:
            count: Number of abort characters to send
            timeout: Timeout in seconds
        """
        for _ in range(count):
            self.putc(CAN, timeout)

    def calc_checksum(self, data: bytes, checksum: int = 0) -> int:
        """
        Calculate simple checksum for data.

        Args:
            data: Data to calculate checksum for
            checksum: Initial checksum value

        Returns:
            Calculated checksum (0-255)
        """
        return (sum(data) + checksum) % 256

    def calc_crc(self, data: bytes, crc: int = 0) -> int:
        """
        Calculate CRC16 for data using the CRC table.

        Args:
            data: Data to calculate CRC for
            crc: Initial CRC value

        Returns:
            Calculated CRC16 value
        """
        for char in bytearray(data):
            crctbl_idx = ((crc >> 8) ^ char) & 0xFF
            crc = ((crc << 8) ^ self.crctable[crctbl_idx]) & 0xFFFF
        return crc & 0xFFFF

    def _make_send_header(self, packet_size: int, sequence: int) -> bytearray:
        """
        Create packet header for sending.

        Args:
            packet_size: Size of data packet (128 or 8192)
            sequence: Sequence number (0-255)

        Returns:
            Header bytes
        """
        assert packet_size in (128, 8192), packet_size
        _bytes = []
        if packet_size == 128:
            _bytes.append(ord(SOH))
        elif packet_size == 8192:
            _bytes.append(ord(STX))
        _bytes.extend([sequence, 0xFF - sequence])
        return bytearray(_bytes)

    def _make_send_checksum(self, crc_mode: bool, data: bytes) -> bytearray:
        """
        Create checksum for sending.

        Args:
            crc_mode: True for CRC16, False for simple checksum
            data: Data to calculate checksum for

        Returns:
            Checksum bytes
        """
        _bytes = []
        if crc_mode:
            crc = self.calc_crc(data)
            _bytes.extend([crc >> 8, crc & 0xFF])
        else:
            crc = self.calc_checksum(data)
            _bytes.append(crc)
        return bytearray(_bytes)

    def calculate_md5(self, data: bytes) -> str:
        """
        Calculate MD5 hash of data.

        Args:
            data: Data to hash

        Returns:
            MD5 hash as hex string
        """
        return hashlib.md5(data).hexdigest()

    def send_file(
        self,
        stream: BinaryIO,
        md5_hash: str,
        retry: int = 16,
        timeout: float = 5,
        callback: Optional[Callable[..., None]] = None,
    ) -> Optional[bool]:
        """
        Send a file via the XMODEM protocol (for download operations).

        Args:
            stream: File-like object to read data from
            md5_hash: MD5 hash of the file for verification
            retry: Maximum number of retries for failed packets
            timeout: Timeout in seconds for operations
            callback: Optional callback function for progress updates

        Returns:
            True on success, False on failure, None on cancellation
        """
        # Initialize protocol
        self.log.info(f"Starting XMODEM send: mode={self.mode}, MD5={md5_hash}")
        try:
            packet_size = dict(
                xmodem=128,
                xmodem8k=8192,
            )[self.mode]
        except KeyError:
            raise ValueError(f"Invalid mode specified: {self.mode!r}")

        is_stx = 1 if packet_size > 255 else 0
        self.log.debug(
            f"Protocol initialized: packet_size={packet_size}, is_stx={is_stx}, retry={retry}, timeout={timeout}"
        )
        self.log.debug("Begin start sequence, waiting for receiver handshake")

        error_count = 0
        crc_mode = 0
        cancel = 0

        # Wait for start sequence from receiver
        while True:
            self.log.debug(
                f"Waiting for handshake byte (attempt {error_count + 1}/{retry + 1})"
            )
            char = self.getc(1, timeout)
            if char:
                self.log.debug(f"Received handshake byte: {char!r} (0x{ord(char):02x})")
                if char == NAK:
                    self.log.debug("Standard checksum requested (NAK)")
                    self.log.info("Handshake complete: using simple checksum mode")
                    crc_mode = 0
                    break
                elif char == CRC:
                    self.log.debug("16-bit CRC requested (CRC)")
                    self.log.info("Handshake complete: using CRC16 mode")
                    crc_mode = 1
                    break
                elif char == CAN:
                    if cancel:
                        self.log.warning(
                            "Transmission canceled: received 2xCAN at start-sequence"
                        )
                        return None
                    else:
                        self.log.debug("First CAN received at start sequence")
                        cancel = 1
                elif char == EOT:
                    self.log.warning(
                        "Transmission canceled: received EOT at start-sequence"
                    )
                    return False
                else:
                    self.log.debug(
                        f"Unexpected handshake byte: {char!r} (0x{ord(char):02x})"
                    )
            else:
                self.log.debug("Handshake timeout, no data received")

            error_count += 1
            if error_count > retry:
                self.log.error(
                    f"Handshake failed: error_count reached {retry}, aborting"
                )
                self.abort(timeout=timeout)
                return False

        # Send data
        self.log.debug(f"Starting data transmission phase: crc_mode={crc_mode}")
        error_count = 0
        success_count = 0
        total_packets = 0
        sequence = 0
        md5_sent = False

        while True:
            if self.canceled:
                self.log.warning("User cancellation requested, sending CAN sequence")
                self.putc(CAN, timeout)
                self.putc(CAN, timeout)
                self.putc(CAN, timeout)
                while self.getc(1, timeout):
                    pass
                self.log.info("Transmission canceled by user")
                self.canceled = False
                return None

            data = []
            if not md5_sent and sequence == 0:
                # Send MD5 hash in first block
                data = md5_hash.encode()
                md5_sent = True
                self.log.debug(
                    f"Preparing MD5 block: sequence={sequence}, md5={md5_hash}"
                )
            else:
                # Read file data
                data = stream.read(packet_size)
                total_packets += 1
                self.log.debug(
                    f"Read {len(data)} bytes from stream for sequence {sequence}"
                )

            if not data:
                # End of stream
                self.log.debug("Reached end of stream, preparing to send EOT")
                self.log.info(
                    f"Data transmission complete: {total_packets} data packets, {success_count} successful"
                )
                break

            header = self._make_send_header(packet_size, sequence)
            original_data_len = len(data)

            if is_stx == 0:
                # 128-byte blocks: single byte length prefix
                data = b"".join(
                    [bytes([len(data) & 0xFF]), data.ljust(packet_size, self.pad)]
                )
                self.log.debug(
                    f"Constructed 128-byte block: seq={sequence}, data_len={original_data_len}, padded_len={len(data)}"
                )
            else:
                # 8K blocks: two-byte length prefix
                data = b"".join(
                    [
                        bytes([len(data) >> 8, len(data) & 0xFF]),
                        data.ljust(packet_size, self.pad),
                    ]
                )
                self.log.debug(
                    f"Constructed 8K block: seq={sequence}, data_len={original_data_len}, padded_len={len(data)}"
                )

            checksum = self._make_send_checksum(bool(crc_mode), data)
            checksum_type = "CRC16" if crc_mode else "checksum"
            checksum_value = (
                (checksum[0] << 8 | checksum[1]) if crc_mode else checksum[0]
            )
            self.log.debug(
                f"Calculated {checksum_type}: 0x{checksum_value:04x if crc_mode else checksum_value:02x}"
            )

            # Send packet with retry logic
            packet_retry_count = 0
            while True:
                packet_retry_count += 1
                total_packet_size = len(header) + len(data) + len(checksum)
                self.log.debug(
                    f"Sending block {sequence} (attempt {packet_retry_count}): {total_packet_size} bytes total"
                )

                self.putc(header + data + checksum, timeout)
                char = self.getc(1, timeout)

                if char == ACK:
                    success_count += 1
                    self.log.debug(
                        f"Block {sequence} ACKed successfully (attempt {packet_retry_count})"
                    )
                    if callable(callback):
                        callback(packet_size, total_packets, success_count, error_count)
                    error_count = 0
                    break
                elif char == CAN:
                    if cancel:
                        self.log.warning(
                            "Transmission canceled: received 2xCAN during transmission"
                        )
                        return False
                    else:
                        self.log.debug("First CAN received during transmission")
                        cancel = 1
                elif char == NAK:
                    self.log.debug(
                        f"Block {sequence} NAKed, will retry (attempt {packet_retry_count})"
                    )
                elif char is None:
                    self.log.debug(f"Timeout waiting for response to block {sequence}")
                else:
                    self.log.debug(
                        f"Unexpected response to block {sequence}: {char!r} (0x{ord(char):02x})"
                    )

                error_count += 1
                if callable(callback):
                    callback(packet_size, total_packets, success_count, error_count)

                if error_count > retry:
                    self.log.error(
                        f"Block {sequence} failed after {retry} retries, aborting transmission"
                    )
                    self.abort(timeout=timeout)
                    return False

            # Increment sequence
            sequence = (sequence + 1) % 0x100
            self.log.debug(
                f"Block {sequence - 1} complete, advancing to sequence {sequence}"
            )

        # Send EOT and wait for ACK
        eot_retry_count = 0
        while True:
            eot_retry_count += 1
            self.log.debug(
                f"Sending EOT (attempt {eot_retry_count}), awaiting final ACK"
            )
            self.putc(EOT, timeout)
            char = self.getc(1, timeout)
            if char == ACK:
                self.log.debug("EOT acknowledged successfully")
                break
            else:
                self.log.debug(f"EOT response: {char!r} (expected ACK)")
                error_count += 1
                if error_count > retry:
                    self.log.error(
                        f"EOT not acknowledged after {retry} attempts, aborting transfer"
                    )
                    self.abort(timeout=timeout)
                    return False

        self.log.info(
            f"XMODEM send completed successfully: {success_count} blocks transmitted"
        )
        return True

    def receive_file(
        self,
        stream: BinaryIO,
        md5_hash: str = "",
        crc_mode: int = 1,
        retry: int = 16,
        timeout: float = 1,
        delay: float = 0.1,
        callback: Optional[Callable[..., None]] = None,
    ) -> Optional[int]:
        """
        Receive a file via the XMODEM protocol (for upload operations).

        Args:
            stream: File-like object to write data to
            md5_hash: Expected MD5 hash for verification
            crc_mode: XMODEM CRC mode (1 for CRC16, 0 for checksum)
            retry: Maximum number of retries for failed packets
            timeout: Timeout in seconds for operations
            delay: Delay between resend attempts
            callback: Optional callback function for progress updates

        Returns:
            Number of bytes received on success, None on failure, -1 on cancellation, 0 on MD5 match
        """
        # Initiate protocol
        self.log.info(
            f"Starting XMODEM receive: expected_md5={md5_hash}, crc_mode={crc_mode}"
        )
        self.log.debug(
            f"Receive parameters: retry={retry}, timeout={timeout}, delay={delay}"
        )

        success_count = 0
        error_count = 0
        char = 0
        cancel = 0

        while True:
            # First try CRC mode, if this fails, fall back to checksum mode
            if error_count >= retry:
                self.log.error(
                    f"Handshake failed: error_count reached {retry}, aborting"
                )
                self.abort(timeout=timeout)
                return None
            elif crc_mode and error_count < (retry // 2):
                self.log.debug(f"Sending CRC request (attempt {error_count + 1})")
                if not self.putc(CRC, timeout):
                    self.log.debug("Failed to send CRC request, sleeping")
                    time.sleep(0.1)
                    error_count += 1
            else:
                if crc_mode:
                    self.log.debug("Falling back to simple checksum mode")
                    crc_mode = 0
                self.log.debug(f"Sending NAK request (attempt {error_count + 1})")
                if not self.putc(NAK, timeout):
                    self.log.debug("Failed to send NAK request, sleeping")
                    time.sleep(0.1)
                    error_count += 1

            char = self.getc(1, timeout)
            if char is None:
                self.log.debug("Handshake timeout, no response from sender")
                error_count += 1
                continue
            elif char == SOH:
                if not self.mode_set:
                    self.mode = "xmodem"
                    self.mode_set = True
                self.log.debug("Received SOH - 128-byte block mode")
                self.log.info("Handshake complete: using 128-byte blocks")
                break
            elif char == STX:
                if not self.mode_set:
                    self.mode = "xmodem8k"
                    self.mode_set = True
                self.log.debug("Received STX - 8K block mode")
                self.log.info("Handshake complete: using 8K blocks")
                break
            elif char == CAN:
                if cancel:
                    self.log.warning(
                        "Transmission canceled: received 2xCAN at start-sequence"
                    )
                    return None
                else:
                    self.log.debug("First CAN received at start sequence")
                    cancel = 1
            else:
                self.log.debug(
                    f"Unexpected handshake response: {char!r} (0x{ord(char):02x})"
                )
                error_count += 1

        # Read data
        self.log.debug(
            f"Starting data reception phase: mode={self.mode}, crc_mode={crc_mode}"
        )
        error_count = 0
        income_size = 0

        # Initialize protocol packet size
        try:
            packet_size = dict(
                xmodem=128,
                xmodem8k=8192,
            )[self.mode]
        except KeyError:
            raise ValueError(f"Invalid mode specified: {self.mode!r}")

        is_stx = 1 if packet_size > 255 else 0
        sequence = 0
        cancel = 0
        retrans = retry + 1
        md5_received = False

        self.log.debug(
            f"Reception initialized: packet_size={packet_size}, is_stx={is_stx}, sequence=0"
        )

        while True:
            if self.canceled:
                self.log.warning("User cancellation requested, sending CAN sequence")
                self.putc(CAN, timeout)
                self.putc(CAN, timeout)
                self.putc(CAN, timeout)
                while self.getc(1, timeout):
                    pass
                self.log.info("Transmission canceled by user")
                self.canceled = False
                return -1

            while True:
                if char == SOH or char == STX:
                    self.log.debug(
                        f"Received block header: {char!r} for sequence {sequence}"
                    )
                    break
                elif char == EOT:
                    # We received an EOT, so send an ACK and return the received data length
                    self.log.debug("Received EOT, sending final ACK")
                    self.putc(ACK, timeout)
                    self.log.info(
                        f"XMODEM receive completed successfully: {income_size} bytes received"
                    )
                    return income_size
                elif char == CAN:
                    # Cancel at two consecutive cancels
                    if cancel:
                        self.log.warning(
                            f"Transmission canceled: received 2xCAN at block {sequence}"
                        )
                        return None
                    else:
                        self.log.debug(f"First CAN received at block {sequence}")
                        cancel = 1
                elif char == None:
                    # No data available
                    error_count += 1
                    if error_count > retry:
                        self.log.error("Error_count reached %d, aborting.", retry)
                        self.abort()
                        return None
                    # Get next start-of-header byte
                    char = self.getc(1, 0.5)
                    continue
                else:
                    err_msg = f"Recv error: expected SOH, EOT; got {char!r}"
                    self.log.warning(err_msg)
                    error_count += 1
                    if error_count > retry:
                        self.abort()
                        return None
                    else:
                        while True:
                            if self.getc(1, timeout) == None:
                                break
                        self.putc(NAK, timeout)
                        char = self.getc(1, timeout)
                        continue

            # Read sequence
            error_count = 0
            cancel = 0
            self.log.debug(f"Processing block {sequence}")

            seq1 = self.getc(1, timeout)
            if seq1 is None:
                self.log.debug("Failed to read first sequence byte")
                seq2 = None
            else:
                seq1 = ord(seq1)
                seq2 = self.getc(1, timeout)
                if seq2 is None:
                    self.log.debug("Failed to read second sequence byte")
                else:
                    # Second byte is the same as first as 1's complement
                    seq2 = 0xFF - ord(seq2)
                    self.log.debug(
                        f"Sequence bytes: seq1={seq1}, seq2={seq2}, expected={sequence}"
                    )

            if not (seq1 == seq2 == sequence):
                # Consume data anyway... even though we will discard it
                self.log.warning(
                    f"Sequence mismatch: expected {sequence}, got seq1={seq1}, seq2={seq2} - discarding block"
                )
                self.getc(2 + packet_size + 1 + crc_mode, timeout)
            else:
                # Sequence is ok, read packet
                expected_data_size = 1 + is_stx + packet_size + 1 + crc_mode
                self.log.debug(f"Reading {expected_data_size} bytes of packet data")
                data = self.getc(expected_data_size, timeout)
                if data is None:
                    self.log.debug("Failed to read packet data")
                    valid = None
                else:
                    self.log.debug(f"Received {len(data)} bytes, verifying checksum")
                    valid, data = self._verify_recv_checksum(bool(crc_mode), data)
                    if valid:
                        self.log.debug("Checksum verification passed")
                    else:
                        self.log.debug("Checksum verification failed")

                # Valid data, append chunk
                if valid and data is not None:
                    retrans = retry + 1
                    if sequence == 0 and not md5_received:
                        md5_received = True
                        received_md5 = data[1 + is_stx : 33 + is_stx].decode()
                        self.log.debug(f"Received MD5 in block 0: {received_md5}")
                        if md5_hash.encode() == data[1 + is_stx : 33 + is_stx]:
                            self.log.info(
                                f"MD5 match detected: {received_md5} - canceling transfer"
                            )
                            self.putc(CAN, timeout)
                            self.putc(CAN, timeout)
                            self.putc(CAN, timeout)
                            while self.getc(1, timeout):
                                pass
                            return 0
                        else:
                            self.log.debug(
                                f"MD5 mismatch: expected {md5_hash}, got {received_md5}"
                            )
                    else:
                        data_len = data[0] << 8 | data[1] if is_stx else data[0]
                        actual_data = data[1 + is_stx : (data_len + 1 + is_stx)]
                        income_size += len(actual_data)
                        stream.write(actual_data)
                        success_count = success_count + 1
                        self.log.debug(
                            f"Block {sequence} processed: {len(actual_data)} bytes written, total: {income_size}"
                        )
                        if callable(callback):
                            callback(packet_size, success_count, error_count)

                    self.log.debug(f"Sending ACK for block {sequence}")
                    self.putc(ACK, timeout)
                    sequence = (sequence + 1) % 0x100
                    self.log.debug(f"Advancing to sequence {sequence}")
                    # Get next start-of-header byte
                    char = self.getc(1, timeout)
                    continue

            # Something went wrong, request retransmission
            self.log.warning("Recv error: purge, requesting retransmission (NAK)")
            while True:
                if self.getc(1, timeout) == None:
                    break
            retrans = retrans - 1
            if retrans <= 0:
                self.log.error("Download error: too many retry error!")
                self.abort()
                return None
            # Get next start-of-header byte
            self.putc(NAK, timeout)
            char = self.getc(1, timeout)
            continue

    def _verify_recv_checksum(self, crc_mode: bool, data: bytes) -> Tuple[bool, bytes]:
        """
        Verify checksum of received data.

        Args:
            crc_mode: True for CRC16, False for simple checksum
            data: Data including checksum

        Returns:
            Tuple of (valid, data_without_checksum)
        """
        if crc_mode:
            _checksum = bytearray(data[-2:])
            their_sum = (_checksum[0] << 8) + _checksum[1]
            data = data[:-2]
            our_sum = self.calc_crc(data)
            valid = bool(their_sum == our_sum)
            self.log.debug(
                f"CRC16 verification: received=0x{their_sum:04x}, calculated=0x{our_sum:04x}, valid={valid}"
            )
            if not valid:
                self.log.warning(
                    f"CRC16 checksum mismatch: received=0x{their_sum:04x}, calculated=0x{our_sum:04x}"
                )
        else:
            _checksum = bytearray([data[-1]])
            their_sum = _checksum[0]
            data = data[:-1]
            our_sum = self.calc_checksum(data)
            valid = their_sum == our_sum
            self.log.debug(
                f"Simple checksum verification: received=0x{their_sum:02x}, calculated=0x{our_sum:02x}, valid={valid}"
            )
            if not valid:
                self.log.warning(
                    f"Simple checksum mismatch: received=0x{their_sum:02x}, calculated=0x{our_sum:02x}"
                )
        return valid, data
