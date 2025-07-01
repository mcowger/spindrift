"""
XMODEM Integration Tests with Mock Server

This test suite verifies the integration between the XMODEM protocol
and the mock CNC server, ensuring that upload/download commands work
correctly through the server interface.
"""

import pytest
import asyncio
import io
import hashlib
import time
from unittest.mock import Mock, AsyncMock, patch

from spindrift.mock_server import MockCNCServer
from spindrift.xmodem import XMODEMProtocol


class TestXMODEMIntegration:
    """Integration tests for XMODEM with mock server."""

    def setup_method(self):
        """Set up test fixtures for each test method."""
        self.server = MockCNCServer(port=0)  # Use port 0 for testing
        self.test_files = {}

    def create_test_file(self, filename: str, content: bytes) -> str:
        """Create a test file in the virtual filesystem."""
        md5_hash = hashlib.md5(content).hexdigest()
        self.server.virtual_files[filename] = {
            'path': filename,
            'size': len(content),
            'contents': content.decode('utf-8', errors='replace'),
            'md5': md5_hash
        }
        return md5_hash

    @pytest.mark.asyncio
    async def test_upload_command_parsing(self):
        """Test that upload commands are parsed correctly."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Test upload command
        result = await self.server._handle_xmodem_command(
            "upload /test/file.txt", "upload", reader, writer, "127.0.0.1"
        )
        
        # Should not error on command parsing
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_download_command_parsing(self):
        """Test that download commands are parsed correctly."""
        # Create test file
        test_content = b"test file content"
        self.create_test_file("/test/file.txt", test_content)
        
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Test download command
        result = await self.server._handle_xmodem_command(
            "download /test/file.txt", "download", reader, writer, "127.0.0.1"
        )
        
        # Should not error on command parsing
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_download_nonexistent_file(self):
        """Test download of non-existent file returns error."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Test download of non-existent file
        result = await self.server._handle_xmodem_command(
            "download /nonexistent/file.txt", "download", reader, writer, "127.0.0.1"
        )
        
        # Should return error message
        assert "ERROR" in result
        assert "File not found" in result

    @pytest.mark.asyncio
    async def test_upload_invalid_command(self):
        """Test upload command without filename returns error."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Test upload without filename
        result = await self.server._handle_xmodem_command(
            "upload", "upload", reader, writer, "127.0.0.1"
        )
        
        # Should return error message
        assert "ERROR" in result
        assert "requires a filename" in result

    def test_virtual_file_addition(self):
        """Test adding files to virtual filesystem."""
        test_data = b"test file content for virtual filesystem"
        md5_hash = hashlib.md5(test_data).hexdigest()
        
        # Add file to virtual filesystem
        self.server._add_virtual_file("/test/new_file.txt", test_data, md5_hash)
        
        # Verify file was added
        assert "/test/new_file.txt" in self.server.virtual_files
        file_info = self.server.virtual_files["/test/new_file.txt"]
        assert file_info['size'] == len(test_data)
        assert file_info['md5'] == md5_hash

    def test_virtual_file_binary_handling(self):
        """Test handling of binary files in virtual filesystem."""
        # Create binary data that can't be decoded as UTF-8
        binary_data = bytes(range(256))  # All byte values 0-255
        md5_hash = hashlib.md5(binary_data).hexdigest()
        
        # Add binary file to virtual filesystem
        self.server._add_virtual_file("/test/binary_file.bin", binary_data, md5_hash)
        
        # Verify file was added with .b64 extension for binary
        binary_filename = "/test/binary_file.bin.b64"
        assert binary_filename in self.server.virtual_files
        file_info = self.server.virtual_files[binary_filename]
        assert file_info['size'] == len(binary_data)
        assert file_info['md5'] == md5_hash

    def test_path_normalization(self):
        """Test path normalization for different client addresses."""
        # Test various path formats
        test_cases = [
            ("/absolute/path.txt", "/absolute/path.txt"),
            ("relative/path.txt", "/relative/path.txt"),
            ("./current/path.txt", "/current/path.txt"),
            ("../parent/path.txt", "/parent/path.txt"),
        ]
        
        for input_path, expected_output in test_cases:
            result = self.server._normalize_path(input_path, "127.0.0.1")
            assert result == expected_output

    @pytest.mark.asyncio
    async def test_blocking_io_adapters(self):
        """Test that blocking I/O adapters work correctly."""
        # Create mock asyncio reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Configure reader to return test data
        test_data = b"test data"
        reader.read.return_value = test_data
        
        # Configure writer drain to succeed
        writer.drain = AsyncMock()
        
        # Create XMODEM command handler
        result = await self.server._handle_xmodem_command(
            "upload /test/file.txt", "upload", reader, writer, "127.0.0.1"
        )
        
        # Verify the adapters were created and used
        # (This test mainly ensures no exceptions are thrown)
        assert isinstance(result, str)

    def test_commands_json_integration(self):
        """Test that upload/download commands are properly defined."""
        # Load commands from the server
        commands = self.server.commands
        
        # Verify upload command exists
        assert "upload" in commands["console_commands"]
        upload_cmd = commands["console_commands"]["upload"]
        assert upload_cmd["name"] == "Upload File"
        assert "filename" in upload_cmd["parameters"]
        
        # Verify download command exists
        assert "download" in commands["console_commands"]
        download_cmd = commands["console_commands"]["download"]
        assert download_cmd["name"] == "Download File"
        assert "filename" in download_cmd["parameters"]

    @pytest.mark.asyncio
    async def test_xmodem_protocol_creation(self):
        """Test XMODEM protocol instance creation in server."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Mock the XMODEM protocol methods to avoid actual transfer
        with patch('spindrift.mock_server.XMODEMProtocol') as mock_xmodem_class:
            mock_xmodem = Mock()
            mock_xmodem.receive_file.return_value = 100  # Simulate successful upload
            mock_xmodem_class.return_value = mock_xmodem
            
            result = await self.server._handle_xmodem_command(
                "upload /test/file.txt", "upload", reader, writer, "127.0.0.1"
            )
            
            # Verify XMODEM protocol was created with correct mode
            mock_xmodem_class.assert_called_once()
            args, kwargs = mock_xmodem_class.call_args
            assert kwargs.get('mode') == 'xmodem8k'

    @pytest.mark.asyncio
    async def test_upload_success_simulation(self):
        """Test successful upload simulation."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Mock successful XMODEM receive
        with patch('spindrift.mock_server.XMODEMProtocol') as mock_xmodem_class:
            mock_xmodem = Mock()
            mock_xmodem.receive_file.return_value = 100  # 100 bytes received
            mock_xmodem_class.return_value = mock_xmodem
            
            # Mock the file stream to return test data
            test_data = b"uploaded file content"
            with patch('io.BytesIO') as mock_bytesio:
                mock_stream = Mock()
                mock_stream.getvalue.return_value = test_data
                mock_bytesio.return_value = mock_stream
                
                result = await self.server._handle_upload(
                    mock_xmodem, "/test/uploaded.txt", "127.0.0.1"
                )
                
                # Should return empty string for success
                assert result == ""
                
                # Verify file was added to virtual filesystem
                assert "/test/uploaded.txt" in self.server.virtual_files

    @pytest.mark.asyncio
    async def test_download_success_simulation(self):
        """Test successful download simulation."""
        # Create test file
        test_content = b"file to download"
        md5_hash = self.create_test_file("/test/download.txt", test_content)
        
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Mock successful XMODEM send
        with patch('spindrift.mock_server.XMODEMProtocol') as mock_xmodem_class:
            mock_xmodem = Mock()
            mock_xmodem.send_file.return_value = True  # Successful send
            mock_xmodem_class.return_value = mock_xmodem
            
            result = await self.server._handle_download(
                mock_xmodem, "/test/download.txt", "127.0.0.1"
            )
            
            # Should return empty string for success
            assert result == ""
            
            # Verify send_file was called with correct parameters
            mock_xmodem.send_file.assert_called_once()
            args, kwargs = mock_xmodem.send_file.call_args
            stream, sent_md5_hash = args[0], args[1]
            assert sent_md5_hash == md5_hash

    @pytest.mark.asyncio
    async def test_error_handling_in_xmodem_commands(self):
        """Test error handling in XMODEM command processing."""
        # Mock reader/writer
        reader = AsyncMock()
        writer = AsyncMock()
        
        # Mock XMODEM protocol to raise exception
        with patch('spindrift.mock_server.XMODEMProtocol') as mock_xmodem_class:
            mock_xmodem_class.side_effect = Exception("Test exception")
            
            result = await self.server._handle_xmodem_command(
                "upload /test/file.txt", "upload", reader, writer, "127.0.0.1"
            )
            
            # Should return error message
            assert "ERROR" in result
            assert "failed" in result
