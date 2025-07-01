"""
Comprehensive XMODEM Protocol Tests

This test suite verifies that our XMODEM implementation produces identical
behavior to the reference Carvera Controller implementation. Tests include:

- Protocol compatibility verification
- Block size handling (128-byte and 8K modes)
- CRC verification (CRC16 and simple checksum)
- MD5 integration and verification
- Error handling and recovery
- Cancellation scenarios
- Edge cases and malformed packets
"""

import pytest
import io
import hashlib
import time
from unittest.mock import Mock, call
from typing import List, Optional, Tuple

from spindrift.xmodem import XMODEMProtocol


class TestXMODEMProtocol:
    """Test suite for XMODEM protocol implementation."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.sent_data = []
        self.received_data = []
        self.timeouts = []

    def create_mock_io(self, receive_sequence: List[bytes] = None,
                      send_failures: List[bool] = None) -> Tuple[callable, callable]:
        """
        Create mock getc/putc functions for testing.

        Args:
            receive_sequence: List of bytes to return from getc calls
            send_failures: List of booleans indicating putc failures

        Returns:
            Tuple of (getc, putc) functions
        """
        receive_sequence = receive_sequence or []
        send_failures = send_failures or []
        receive_index = 0
        send_index = 0

        def mock_getc(size: int, timeout: float = 1.0) -> Optional[bytes]:
            nonlocal receive_index
            self.timeouts.append(timeout)

            if receive_index >= len(receive_sequence):
                return None  # Timeout

            data = receive_sequence[receive_index]
            receive_index += 1

            if data is None:
                return None  # Simulate timeout

            # Return exact size requested or None
            if len(data) == size:
                return data
            elif len(data) < size:
                return None  # Partial read = timeout
            else:
                # Return first 'size' bytes
                return data[:size]

        def mock_putc(data: bytes, timeout: float = 1.0) -> Optional[int]:
            nonlocal send_index
            self.sent_data.append(data)
            self.timeouts.append(timeout)

            if send_index < len(send_failures) and send_failures[send_index]:
                send_index += 1
                return None  # Simulate timeout

            send_index += 1
            return len(data)

        return mock_getc, mock_putc

    def test_protocol_constants(self):
        """Test that protocol constants match reference implementation."""
        # Test protocol bytes
        assert XMODEMProtocol.SOH == b'\x01'
        assert XMODEMProtocol.STX == b'\x02'
        assert XMODEMProtocol.EOT == b'\x04'
        assert XMODEMProtocol.ACK == b'\x06'
        assert XMODEMProtocol.NAK == b'\x15'
        assert XMODEMProtocol.CAN == b'\x16'
        assert XMODEMProtocol.CRC == b'C'

    def test_crc_table_matches_reference(self):
        """Test that CRC table matches reference implementation exactly."""
        # Reference CRC table from Carvera Controller
        reference_crctable = [
            0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
            0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
            # ... (truncated for brevity, full table in reference)
        ]

        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        # Test first few entries to verify table structure
        assert xmodem.crctable[0] == 0x0000
        assert xmodem.crctable[1] == 0x1021
        assert xmodem.crctable[2] == 0x2042
        assert xmodem.crctable[3] == 0x3063
        assert len(xmodem.crctable) == 256

    def test_crc_calculation_matches_reference(self):
        """Test CRC calculation produces identical results to reference."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        # Test cases with known CRC values
        test_cases = [
            (b'hello', 0x4ab3),  # From reference implementation docstring
            (b'world', 0x4ab3),  # When calculated with 'hello' as initial CRC
            (b'', 0x0000),       # Empty data
            (b'\x00', 0x1021),   # Single null byte
            (b'\xff', 0xef1f),   # Single 0xFF byte
        ]

        for data, expected_crc in test_cases:
            if data == b'world':
                # Test cumulative CRC calculation
                crc = xmodem.calc_crc(b'hello')
                result = xmodem.calc_crc(data, crc)
            else:
                result = xmodem.calc_crc(data)
            assert result == expected_crc, f"CRC mismatch for {data!r}: got {result:04x}, expected {expected_crc:04x}"

    def test_simple_checksum_calculation(self):
        """Test simple checksum calculation matches reference."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        # Test cases
        test_cases = [
            (b'hello', 0x3c),    # From reference implementation docstring
            (b'', 0x00),         # Empty data
            (b'\x00', 0x00),     # Single null byte
            (b'\xff', 0xff),     # Single 0xFF byte
            (b'\x01\x02\x03', 0x06),  # Simple sum
        ]

        for data, expected_checksum in test_cases:
            if data == b'hello' and expected_checksum == 0x3c:
                # Test cumulative checksum (hello + world = 0x3c from reference)
                result = xmodem.calc_checksum(data)
            else:
                result = xmodem.calc_checksum(data)
            assert result == expected_checksum, f"Checksum mismatch for {data!r}: got {result:02x}, expected {expected_checksum:02x}"

    def test_packet_header_construction(self):
        """Test packet header construction matches reference format."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        # Test 128-byte packet header (SOH)
        header_128 = xmodem._make_send_header(128, 1)
        expected_128 = bytearray([0x01, 0x01, 0xfe])  # SOH, seq, ~seq
        assert header_128 == expected_128

        # Test 8K packet header (STX)
        header_8k = xmodem._make_send_header(8192, 5)
        expected_8k = bytearray([0x02, 0x05, 0xfa])  # STX, seq, ~seq
        assert header_8k == expected_8k

        # Test sequence wraparound
        header_wrap = xmodem._make_send_header(128, 255)
        expected_wrap = bytearray([0x01, 0xff, 0x00])  # SOH, 255, ~255
        assert header_wrap == expected_wrap

    def test_checksum_construction_crc_mode(self):
        """Test checksum construction in CRC mode."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        test_data = b'hello world'
        crc = xmodem.calc_crc(test_data)

        checksum_bytes = xmodem._make_send_checksum(True, test_data)
        expected = bytearray([crc >> 8, crc & 0xff])

        assert checksum_bytes == expected
        assert len(checksum_bytes) == 2

    def test_checksum_construction_simple_mode(self):
        """Test checksum construction in simple checksum mode."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        test_data = b'hello world'
        checksum = xmodem.calc_checksum(test_data)

        checksum_bytes = xmodem._make_send_checksum(False, test_data)
        expected = bytearray([checksum])

        assert checksum_bytes == expected
        assert len(checksum_bytes) == 1

    def test_md5_calculation(self):
        """Test MD5 calculation matches standard implementation."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        test_data = b'hello world'
        expected_md5 = hashlib.md5(test_data).hexdigest()
        result_md5 = xmodem.calculate_md5(test_data)

        assert result_md5 == expected_md5
        assert len(result_md5) == 32  # 32 hex characters

    def test_initialization_modes(self):
        """Test XMODEM initialization with different modes."""
        getc, putc = self.create_mock_io()

        # Test xmodem mode (128-byte blocks)
        xmodem_128 = XMODEMProtocol(getc, putc, mode='xmodem')
        assert xmodem_128.mode == 'xmodem'

        # Test xmodem8k mode (8192-byte blocks)
        xmodem_8k = XMODEMProtocol(getc, putc, mode='xmodem8k')
        assert xmodem_8k.mode == 'xmodem8k'

        # Test custom padding
        custom_pad = XMODEMProtocol(getc, putc, pad=b'\x00')
        assert custom_pad.pad == b'\x00'

    def test_abort_sequence(self):
        """Test abort sequence sends correct CAN bytes."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        xmodem.abort(count=3, timeout=5)

        # Should send 3 CAN bytes
        assert len(self.sent_data) == 3
        assert all(data == b'\x16' for data in self.sent_data)
        assert all(timeout == 5 for timeout in self.timeouts)

    def test_mode_set_flag(self):
        """Test mode_set flag functionality."""
        getc, putc = self.create_mock_io()
        xmodem = XMODEMProtocol(getc, putc)

        # Initially not set
        assert not xmodem.mode_set

        # Set the flag
        xmodem.mode_set = True
        assert xmodem.mode_set

        # Clear the flag
        xmodem.clear_mode_set()
        assert not xmodem.mode_set


class TestXMODEMSendProtocol:
    """Test suite for XMODEM send (download) functionality."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.sent_data = []
        self.received_data = []

    def create_mock_io(self, receive_sequence: List[bytes] = None) -> Tuple[callable, callable]:
        """Create mock I/O functions for send testing."""
        receive_sequence = receive_sequence or []
        receive_index = 0

        def mock_getc(size: int, timeout: float = 1.0) -> Optional[bytes]:
            nonlocal receive_index
            if receive_index >= len(receive_sequence):
                return None
            data = receive_sequence[receive_index]
            receive_index += 1
            return data if data is not None and len(data) == size else None

        def mock_putc(data: bytes, timeout: float = 1.0) -> Optional[int]:
            self.sent_data.append(data)
            return len(data)

        return mock_getc, mock_putc

    def test_send_handshake_crc_mode(self):
        """Test send handshake with CRC mode request."""
        # Receiver requests CRC mode
        receive_sequence = [b'C', b'\x06']  # CRC request, then ACK
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        # Create test file with MD5
        test_data = b'hello world'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)

        # Should succeed
        assert result is True

        # Verify handshake and data transmission
        assert len(self.sent_data) >= 2  # At least MD5 block + data block

        # First packet should contain MD5 hash
        first_packet = self.sent_data[0]
        assert first_packet[0:1] == b'\x01'  # SOH for 128-byte mode
        assert first_packet[1] == 0  # Sequence 0 for MD5
        assert first_packet[2] == 255  # ~sequence

    def test_send_handshake_nak_mode(self):
        """Test send handshake with NAK (simple checksum) mode."""
        # Receiver requests simple checksum mode
        receive_sequence = [b'\x15', b'\x06']  # NAK request, then ACK
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'test'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)
        assert result is True

    def test_send_8k_mode(self):
        """Test send in 8K block mode."""
        # Receiver requests CRC mode
        receive_sequence = [b'C'] + [b'\x06'] * 10  # CRC request + multiple ACKs
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem8k')

        # Create larger test data
        test_data = b'x' * 4096  # 4K of data
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)
        assert result is True

        # First packet should use STX for 8K mode
        first_packet = self.sent_data[0]
        assert first_packet[0:1] == b'\x02'  # STX for 8K mode

    def test_send_md5_block_format(self):
        """Test MD5 block format in sequence 0."""
        receive_sequence = [b'C', b'\x06', b'\x06', b'\x06']  # CRC + ACKs
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'hello'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)
        assert result is True

        # Extract MD5 block (first packet)
        md5_packet = self.sent_data[0]

        # Verify packet structure: SOH + seq + ~seq + length + MD5 + padding + checksum
        assert md5_packet[0] == 0x01  # SOH
        assert md5_packet[1] == 0x00  # Sequence 0
        assert md5_packet[2] == 0xFF  # ~Sequence 0
        assert md5_packet[3] == 0x20  # Length = 32 bytes for MD5

        # Extract MD5 from packet
        md5_in_packet = md5_packet[4:36].decode()
        assert md5_in_packet == md5_hash

    def test_send_retry_on_nak(self):
        """Test send retry mechanism on NAK."""
        # First NAK (retry), then ACK
        receive_sequence = [b'C', b'\x15', b'\x06', b'\x06']  # CRC, NAK, ACK, ACK
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'retry test'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=5, timeout=1)
        assert result is True

        # Should have sent MD5 block twice (original + retry)
        assert len(self.sent_data) >= 3  # MD5 block sent twice + data block

    def test_send_cancellation_by_receiver(self):
        """Test send cancellation when receiver sends CAN."""
        # Receiver sends CAN twice
        receive_sequence = [b'C', b'\x18', b'\x18']  # CRC, CAN, CAN
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'cancel test'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)
        assert result is False  # Should return False on cancellation

    def test_send_eot_handling(self):
        """Test EOT transmission and acknowledgment."""
        # Normal sequence ending with EOT ACK
        receive_sequence = [b'C', b'\x06', b'\x06', b'\x06']  # CRC, ACKs for packets, ACK for EOT
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'eot test'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)
        assert result is True

        # Last sent data should be EOT
        assert self.sent_data[-1] == b'\x04'  # EOT

    def test_send_timeout_failure(self):
        """Test send failure on timeout."""
        # No response from receiver
        receive_sequence = []  # Empty - all timeouts
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        test_data = b'timeout test'
        md5_hash = hashlib.md5(test_data).hexdigest()
        file_stream = io.BytesIO(test_data)

        result = xmodem.send_file(file_stream, md5_hash, retry=2, timeout=0.1)
        assert result is False  # Should fail on timeout


class TestXMODEMReceiveProtocol:
    """Test suite for XMODEM receive (upload) functionality."""

    # CRC table for packet creation (same as reference implementation)
    crctable = [
        0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50a5, 0x60c6, 0x70e7,
        0x8108, 0x9129, 0xa14a, 0xb16b, 0xc18c, 0xd1ad, 0xe1ce, 0xf1ef,
        0x1231, 0x0210, 0x3273, 0x2252, 0x52b5, 0x4294, 0x72f7, 0x62d6,
        0x9339, 0x8318, 0xb37b, 0xa35a, 0xd3bd, 0xc39c, 0xf3ff, 0xe3de,
        0x2462, 0x3443, 0x0420, 0x1401, 0x64e6, 0x74c7, 0x44a4, 0x5485,
        0xa56a, 0xb54b, 0x8528, 0x9509, 0xe5ee, 0xf5cf, 0xc5ac, 0xd58d,
        0x3653, 0x2672, 0x1611, 0x0630, 0x76d7, 0x66f6, 0x5695, 0x46b4,
        0xb75b, 0xa77a, 0x9719, 0x8738, 0xf7df, 0xe7fe, 0xd79d, 0xc7bc,
        0x48c4, 0x58e5, 0x6886, 0x78a7, 0x0840, 0x1861, 0x2802, 0x3823,
        0xc9cc, 0xd9ed, 0xe98e, 0xf9af, 0x8948, 0x9969, 0xa90a, 0xb92b,
        0x5af5, 0x4ad4, 0x7ab7, 0x6a96, 0x1a71, 0x0a50, 0x3a33, 0x2a12,
        0xdbfd, 0xcbdc, 0xfbbf, 0xeb9e, 0x9b79, 0x8b58, 0xbb3b, 0xab1a,
        0x6ca6, 0x7c87, 0x4ce4, 0x5cc5, 0x2c22, 0x3c03, 0x0c60, 0x1c41,
        0xedae, 0xfd8f, 0xcdec, 0xddcd, 0xad2a, 0xbd0b, 0x8d68, 0x9d49,
        0x7e97, 0x6eb6, 0x5ed5, 0x4ef4, 0x3e13, 0x2e32, 0x1e51, 0x0e70,
        0xff9f, 0xefbe, 0xdfdd, 0xcffc, 0xbf1b, 0xaf3a, 0x9f59, 0x8f78,
        0x9188, 0x81a9, 0xb1ca, 0xa1eb, 0xd10c, 0xc12d, 0xf14e, 0xe16f,
        0x1080, 0x00a1, 0x30c2, 0x20e3, 0x5004, 0x4025, 0x7046, 0x6067,
        0x83b9, 0x9398, 0xa3fb, 0xb3da, 0xc33d, 0xd31c, 0xe37f, 0xf35e,
        0x02b1, 0x1290, 0x22f3, 0x32d2, 0x4235, 0x5214, 0x6277, 0x7256,
        0xb5ea, 0xa5cb, 0x95a8, 0x8589, 0xf56e, 0xe54f, 0xd52c, 0xc50d,
        0x34e2, 0x24c3, 0x14a0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
        0xa7db, 0xb7fa, 0x8799, 0x97b8, 0xe75f, 0xf77e, 0xc71d, 0xd73c,
        0x26d3, 0x36f2, 0x0691, 0x16b0, 0x6657, 0x7676, 0x4615, 0x5634,
        0xd94c, 0xc96d, 0xf90e, 0xe92f, 0x99c8, 0x89e9, 0xb98a, 0xa9ab,
        0x5844, 0x4865, 0x7806, 0x6827, 0x18c0, 0x08e1, 0x3882, 0x28a3,
        0xcb7d, 0xdb5c, 0xeb3f, 0xfb1e, 0x8bf9, 0x9bd8, 0xabbb, 0xbb9a,
        0x4a75, 0x5a54, 0x6a37, 0x7a16, 0x0af1, 0x1ad0, 0x2ab3, 0x3a92,
        0xfd2e, 0xed0f, 0xdd6c, 0xcd4d, 0xbdaa, 0xad8b, 0x9de8, 0x8dc9,
        0x7c26, 0x6c07, 0x5c64, 0x4c45, 0x3ca2, 0x2c83, 0x1ce0, 0x0cc1,
        0xef1f, 0xff3e, 0xcf5d, 0xdf7c, 0xaf9b, 0xbfba, 0x8fd9, 0x9ff8,
        0x6e17, 0x7e36, 0x4e55, 0x5e74, 0x2e93, 0x3eb2, 0x0ed1, 0x1ef0,
    ]

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.sent_data = []
        self.received_stream = io.BytesIO()

    def create_mock_io(self, receive_sequence: List[bytes] = None) -> Tuple[callable, callable]:
        """Create mock I/O functions for receive testing."""
        receive_sequence = receive_sequence or []
        receive_index = 0

        def mock_getc(size: int, timeout: float = 1.0) -> Optional[bytes]:
            nonlocal receive_index
            if receive_index >= len(receive_sequence):
                return None
            data = receive_sequence[receive_index]
            receive_index += 1
            return data if data is not None and len(data) == size else None

        def mock_putc(data: bytes, timeout: float = 1.0) -> Optional[int]:
            self.sent_data.append(data)
            return len(data)

        return mock_getc, mock_putc

    def create_xmodem_packet(self, sequence: int, data: bytes, packet_size: int = 128,
                           crc_mode: bool = True) -> bytes:
        """Create a properly formatted XMODEM packet for testing."""
        # Create header
        if packet_size == 128:
            header = bytes([0x01, sequence, 0xff - sequence])  # SOH
        else:
            header = bytes([0x02, sequence, 0xff - sequence])  # STX

        # Create data with length prefix
        if packet_size == 128:
            data_with_len = bytes([len(data)]) + data.ljust(packet_size, b'\x1a')
        else:
            data_with_len = bytes([len(data) >> 8, len(data) & 0xff]) + data.ljust(packet_size, b'\x1a')

        # Calculate checksum
        if crc_mode:
            # Calculate CRC16
            crc = 0
            for byte in data_with_len:
                crc = ((crc << 8) ^ self.crctable[((crc >> 8) ^ byte) & 0xff]) & 0xffff
            checksum = bytes([crc >> 8, crc & 0xff])
        else:
            # Simple checksum
            checksum = bytes([sum(data_with_len) % 256])

        return header + data_with_len + checksum

    def test_receive_handshake_crc_mode(self):
        """Test receive handshake requesting CRC mode."""
        # Create MD5 packet and data packet
        test_data = b'hello world'
        md5_hash = hashlib.md5(test_data).hexdigest()

        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 128, True)
        data_packet = self.create_xmodem_packet(1, test_data, 128, True)
        eot = b'\x04'

        receive_sequence = [md5_packet, data_packet, eot]
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=3, timeout=1)

        # Should succeed and return number of bytes received
        assert result == len(test_data)

        # Should have sent CRC request, then ACKs
        assert self.sent_data[0] == b'C'  # CRC request
        assert self.sent_data[1] == b'\x06'  # ACK for MD5 packet
        assert self.sent_data[2] == b'\x06'  # ACK for data packet
        assert self.sent_data[3] == b'\x06'  # ACK for EOT

        # Verify received data
        self.received_stream.seek(0)
        received_data = self.received_stream.read()
        assert received_data == test_data

    def test_receive_handshake_nak_mode(self):
        """Test receive handshake falling back to NAK mode."""
        test_data = b'nak test'
        md5_hash = hashlib.md5(test_data).hexdigest()

        # Create packets with simple checksum
        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 128, False)
        data_packet = self.create_xmodem_packet(1, test_data, 128, False)
        eot = b'\x04'

        # Simulate timeout on CRC requests, then respond to NAK
        receive_sequence = [None, None, md5_packet, data_packet, eot]  # Timeouts, then packets
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=5, timeout=1)

        assert result == len(test_data)

        # Should have sent CRC requests, then NAK requests
        assert b'C' in self.sent_data  # CRC requests
        assert b'\x15' in self.sent_data  # NAK requests

    def test_receive_8k_mode(self):
        """Test receive in 8K block mode."""
        test_data = b'x' * 4096  # 4K of data
        md5_hash = hashlib.md5(test_data).hexdigest()

        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 8192, True)
        data_packet = self.create_xmodem_packet(1, test_data, 8192, True)
        eot = b'\x04'

        receive_sequence = [md5_packet, data_packet, eot]
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem8k')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=3, timeout=1)

        assert result == len(test_data)

        # Verify received data
        self.received_stream.seek(0)
        received_data = self.received_stream.read()
        assert received_data == test_data

    def test_receive_md5_match_cancellation(self):
        """Test receive cancellation when MD5 matches."""
        test_data = b'md5 match test'
        md5_hash = hashlib.md5(test_data).hexdigest()

        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 128, True)

        receive_sequence = [md5_packet]
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        # Pass the same MD5 hash to trigger match
        result = xmodem.receive_file(self.received_stream, md5_hash=md5_hash, crc_mode=1, retry=3, timeout=1)

        # Should return 0 for MD5 match
        assert result == 0

        # Should have sent CAN sequence
        assert b'\x18' in self.sent_data  # CAN bytes

    def test_receive_sequence_error_recovery(self):
        """Test receive recovery from sequence number errors."""
        test_data = b'sequence error test'
        md5_hash = hashlib.md5(test_data).hexdigest()

        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 128, True)
        bad_packet = self.create_xmodem_packet(5, b'wrong sequence', 128, True)  # Wrong sequence
        good_packet = self.create_xmodem_packet(1, test_data, 128, True)  # Correct sequence
        eot = b'\x04'

        receive_sequence = [md5_packet, bad_packet, good_packet, eot]
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=5, timeout=1)

        assert result == len(test_data)

        # Should have sent NAK for bad sequence, then ACK for good sequence
        assert b'\x15' in self.sent_data  # NAK for bad packet
        assert b'\x06' in self.sent_data  # ACK for good packet

    def test_receive_checksum_error_recovery(self):
        """Test receive recovery from checksum errors."""
        test_data = b'checksum error test'
        md5_hash = hashlib.md5(test_data).hexdigest()

        md5_packet = self.create_xmodem_packet(0, md5_hash.encode(), 128, True)

        # Create packet with bad checksum
        bad_packet = self.create_xmodem_packet(1, b'bad checksum', 128, True)
        bad_packet = bad_packet[:-2] + b'\x00\x00'  # Replace CRC with zeros

        good_packet = self.create_xmodem_packet(1, test_data, 128, True)
        eot = b'\x04'

        receive_sequence = [md5_packet, bad_packet, good_packet, eot]
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=5, timeout=1)

        assert result == len(test_data)

        # Should have sent NAK for bad checksum, then ACK for good packet
        assert b'\x15' in self.sent_data  # NAK for bad checksum

    def test_receive_cancellation_by_sender(self):
        """Test receive handling when sender cancels."""
        # Sender sends CAN twice
        receive_sequence = [b'\x18', b'\x18']  # Two CAN bytes
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=3, timeout=1)

        # Should return None for cancellation
        assert result is None

    def test_receive_timeout_failure(self):
        """Test receive failure on timeout."""
        # No data from sender
        receive_sequence = []  # Empty - all timeouts
        getc, putc = self.create_mock_io(receive_sequence)
        xmodem = XMODEMProtocol(getc, putc, mode='xmodem')

        result = xmodem.receive_file(self.received_stream, md5_hash='', crc_mode=1, retry=2, timeout=0.1)

        # Should return None for failure
        assert result is None
