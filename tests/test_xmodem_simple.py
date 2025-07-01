"""
Simple XMODEM Tests (without pytest-asyncio dependency)

Basic functionality tests for XMODEM protocol implementation
to verify compatibility with reference implementation.
"""

import io
import hashlib
from spindrift.xmodem import XMODEMProtocol, SOH, STX, EOT, ACK, NAK, CAN, CRC


def test_crc_calculation():
    """Test CRC calculation matches expected values."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    # Test known CRC values
    assert xmodem.calc_crc(b'') == 0x0000
    assert xmodem.calc_crc(b'\x00') == 0x0000  # Null byte CRC
    assert xmodem.calc_crc(b'hello') == 0xc362

    print("✅ CRC calculation tests passed")


def test_checksum_calculation():
    """Test simple checksum calculation."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    # Test known checksum values
    assert xmodem.calc_checksum(b'') == 0x00
    assert xmodem.calc_checksum(b'\x00') == 0x00
    assert xmodem.calc_checksum(b'hello') == 0x14  # (0x68+0x65+0x6c+0x6c+0x6f) % 256

    print("✅ Checksum calculation tests passed")


def test_packet_header_construction():
    """Test packet header construction."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    # Test 128-byte packet header
    header_128 = xmodem._make_send_header(128, 1)
    expected_128 = bytearray([0x01, 0x01, 0xfe])  # SOH, seq, ~seq
    assert header_128 == expected_128

    # Test 8K packet header
    header_8k = xmodem._make_send_header(8192, 5)
    expected_8k = bytearray([0x02, 0x05, 0xfa])  # STX, seq, ~seq
    assert header_8k == expected_8k

    print("✅ Packet header construction tests passed")


def test_checksum_construction():
    """Test checksum construction for packets."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    test_data = b'hello world'

    # Test CRC mode
    crc_checksum = xmodem._make_send_checksum(True, test_data)
    assert len(crc_checksum) == 2  # CRC16 is 2 bytes

    # Test simple checksum mode
    simple_checksum = xmodem._make_send_checksum(False, test_data)
    assert len(simple_checksum) == 1  # Simple checksum is 1 byte

    print("✅ Checksum construction tests passed")


def test_md5_calculation():
    """Test MD5 calculation."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    test_data = b'hello world'
    expected_md5 = hashlib.md5(test_data).hexdigest()
    result_md5 = xmodem.calculate_md5(test_data)

    assert result_md5 == expected_md5
    assert len(result_md5) == 32  # 32 hex characters

    print("✅ MD5 calculation tests passed")


def test_send_handshake_simulation():
    """Test send handshake simulation."""
    sent_data = []
    receive_sequence = [b'C', b'\x06', b'\x06', b'\x06']  # CRC request, ACKs for MD5, data, EOT
    receive_index = 0

    def mock_getc(size, timeout=1.0):
        nonlocal receive_index
        if receive_index >= len(receive_sequence):
            return None
        data = receive_sequence[receive_index]
        receive_index += 1
        return data if len(data) == size else None

    def mock_putc(data, timeout=1.0):
        sent_data.append(data)
        return len(data)

    xmodem = XMODEMProtocol(mock_getc, mock_putc, mode='xmodem')

    # Create test file
    test_data = b'hello'
    md5_hash = hashlib.md5(test_data).hexdigest()
    file_stream = io.BytesIO(test_data)

    result = xmodem.send_file(file_stream, md5_hash, retry=3, timeout=1)

    # Should succeed
    assert result is True

    # Should have sent packets
    assert len(sent_data) >= 2  # At least MD5 block + data block + EOT

    # Last sent should be EOT
    assert sent_data[-1] == b'\x04'

    print("✅ Send handshake simulation tests passed")


def test_receive_checksum_verification():
    """Test receive checksum verification."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    # Test data with known CRC
    test_data = b'hello world'
    crc = xmodem.calc_crc(test_data)

    # Create data with CRC appended
    data_with_crc = test_data + bytes([crc >> 8, crc & 0xff])

    # Verify CRC mode
    valid, extracted_data = xmodem._verify_recv_checksum(True, data_with_crc)
    assert valid is True
    assert extracted_data == test_data

    # Test simple checksum
    checksum = xmodem.calc_checksum(test_data)
    data_with_checksum = test_data + bytes([checksum])

    valid, extracted_data = xmodem._verify_recv_checksum(False, data_with_checksum)
    assert valid is True
    assert extracted_data == test_data

    print("✅ Receive checksum verification tests passed")


def test_protocol_constants():
    """Test protocol constants match expected values."""
    # Test that constants are defined correctly
    assert SOH == b'\x01'
    assert STX == b'\x02'
    assert EOT == b'\x04'
    assert ACK == b'\x06'
    assert NAK == b'\x15'
    assert CAN == b'\x16'
    assert CRC == b'C'

    print("✅ Protocol constants tests passed")


def test_crc_table_structure():
    """Test CRC table has correct structure."""
    def dummy_getc(size, timeout=1.0):
        return b'test'[:size] if size <= 4 else None

    def dummy_putc(data, timeout=1.0):
        return len(data)

    xmodem = XMODEMProtocol(dummy_getc, dummy_putc)

    # Test CRC table structure
    assert len(xmodem.crctable) == 256
    assert xmodem.crctable[0] == 0x0000
    assert xmodem.crctable[1] == 0x1021

    print("✅ CRC table structure tests passed")


def run_all_tests():
    """Run all simple tests."""
    print("Running XMODEM simple tests...")
    print()

    test_protocol_constants()
    test_crc_table_structure()
    test_crc_calculation()
    test_checksum_calculation()
    test_md5_calculation()
    test_packet_header_construction()
    test_checksum_construction()
    test_receive_checksum_verification()
    test_send_handshake_simulation()

    print()
    print("🎉 All XMODEM simple tests passed!")


if __name__ == "__main__":
    run_all_tests()
