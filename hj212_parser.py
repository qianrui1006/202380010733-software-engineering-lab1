"""Parser for single-frame HJ 212-2017 text messages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

HEADER: Final = "##"
TERMINATOR: Final = "\r\n"
MAX_DATA_LENGTH: Final = 1024
CRC_POLYNOMIAL: Final = 0xA001
CRC_INITIAL_VALUE: Final = 0xFFFF
MONITORING_ITEM_RE: Final = re.compile(
    r"^(?P<factor>[A-Za-z]\d{5})-(?P<kind>[A-Za-z][A-Za-z0-9]*)=(?P<value>.*)$"
)


@dataclass(frozen=True)
class _Frame:
    data_segment: str
    crc_text: str


class HJ212Parser:
    """Validate and parse one complete HJ 212-2017 frame.

    The parser handles one already-framed ASCII message at a time. It does not
    perform TCP stream reassembly, decryption, or split-packet aggregation.
    """

    @staticmethod
    def crc16(data_segment: str) -> int:
        """Return the HJ 212-2017 Appendix A CRC16 value for an ASCII segment."""
        try:
            payload = data_segment.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("HJ 212 data segments must be ASCII") from exc

        crc = CRC_INITIAL_VALUE
        for byte in payload:
            # HJ 212-2017 Appendix A enters each byte into the high byte.
            crc = (crc >> 8) ^ byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ CRC_POLYNOMIAL
                else:
                    crc >>= 1
        return crc & 0xFFFF

    @staticmethod
    def _split_frame(message: str) -> _Frame:
        if not isinstance(message, str):
            raise ValueError("message must be a string")
        if not message.startswith(HEADER):
            raise ValueError("message must start with ##")
        if not message.endswith(TERMINATOR):
            raise ValueError("message must end with CRLF")
        if len(message) < 12:
            raise ValueError("message is shorter than the minimum frame")

        length_text = message[2:6]
        if not re.fullmatch(r"[0-9]{4}", length_text):
            raise ValueError("data length must be four decimal digits")
        data_length = int(length_text)
        if not 0 <= data_length <= MAX_DATA_LENGTH:
            raise ValueError("data length must be between 0 and 1024")

        expected_total = 2 + 4 + data_length + 4 + 2
        if len(message) != expected_total:
            raise ValueError("declared data length does not match frame size")

        data_start = 6
        data_end = data_start + data_length
        data_segment = message[data_start:data_end]
        crc_text = message[data_end:data_end + 4]
        if not re.fullmatch(r"[0-9A-Fa-f]{4}", crc_text):
            raise ValueError("CRC field must be four hexadecimal digits")
        try:
            data_segment.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("HJ 212 data segments must be ASCII") from exc
        return _Frame(data_segment=data_segment, crc_text=crc_text.upper())

    @classmethod
    def is_valid_message(cls, message: str) -> bool:
        """Return whether a complete frame has valid structure and CRC."""
        try:
            frame = cls._split_frame(message)
        except ValueError:
            return False
        return cls.validate_crc(message)

    @classmethod
    def validate_crc(cls, message: str) -> bool:
        """Compare the CRC field with a fresh calculation over the data segment."""
        try:
            frame = cls._split_frame(message)
        except ValueError:
            return False
        return f"{cls.crc16(frame.data_segment):04X}" == frame.crc_text

    @classmethod
    def parse_data_segment(cls, message: str) -> dict[str, str]:
        """Parse the frame's data segment into a key/value mapping.

        CP=&&...&& is kept intact, including its internal semicolons. Duplicate
        keys and malformed fields raise ValueError rather than being discarded.
        """
        frame = cls._split_frame(message)
        segment = frame.data_segment
        cp_match = re.search(r"(?:^|;)CP=&&", segment)
        fields: list[str] = []
        cp_value: str | None = None

        if cp_match is None:
            fields.extend(part for part in segment.split(";") if part)
        else:
            cp_start = cp_match.start()
            # The leading semicolon belongs to the separator, not to CP.
            if segment[cp_start:cp_start + 1] == ";":
                prefix = segment[:cp_start]
            else:
                prefix = ""
            cp_body_start = cp_match.end()
            cp_end = segment.find("&&", cp_body_start)
            if cp_end < 0:
                raise ValueError("CP field is missing its closing &&")
            cp_value = "&&" + segment[cp_body_start:cp_end] + "&&"
            suffix = segment[cp_end + 2:]
            fields.extend(part for part in prefix.split(";") if part)
            fields.extend(part for part in suffix.split(";") if part)

        result: dict[str, str] = {}
        for field in fields:
            key, separator, value = field.partition("=")
            if not separator or not key:
                raise ValueError(f"malformed data field: {field!r}")
            if key in result or key == "CP":
                raise ValueError(f"duplicate data field: {key}")
            result[key] = value
        if cp_value is not None:
            if "CP" in result:
                raise ValueError("duplicate data field: CP")
            result["CP"] = cp_value
        return result

    @classmethod
    def extract_monitoring_data(cls, message: str) -> list[dict[str, str]]:
        """Extract factor/type/value triples from the CP data area."""
        fields = cls.parse_data_segment(message)
        cp_value = fields.get("CP")
        if cp_value is None:
            return []
        if not (cp_value.startswith("&&") and cp_value.endswith("&&")):
            raise ValueError("CP field must use && delimiters")

        data_area = cp_value[2:-2]
        readings: list[dict[str, str]] = []
        # Semicolons separate projects; commas separate categories for one item.
        for item in re.split(r"[;,]", data_area):
            item = item.strip()
            if not item:
                continue
            match = MONITORING_ITEM_RE.fullmatch(item)
            if match:
                readings.append(
                    {
                        "factor_code": match.group("factor"),
                        "data_type": match.group("kind"),
                        "value": match.group("value"),
                    }
                )
        return readings

    @classmethod
    def build_message(cls, data_segment: str) -> str:
        """Build a complete frame, useful for local data generation and examples."""
        try:
            data_segment.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("HJ 212 data segments must be ASCII") from exc
        if len(data_segment) > MAX_DATA_LENGTH:
            raise ValueError("data segment exceeds 1024 characters")
        crc_text = f"{cls.crc16(data_segment):04X}"
        return f"##{len(data_segment):04d}{data_segment}{crc_text}{TERMINATOR}"

