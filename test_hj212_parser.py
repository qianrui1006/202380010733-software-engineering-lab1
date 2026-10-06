"""Regression tests for the HJ 212-2017 parser."""

import unittest

from hj212_parser import HJ212Parser


OFFICIAL_SAMPLE = (
    "##0101QN=20160801085857223;ST=32;CN=1062;PW=100000;"
    "MN=010000A8900016F000169DC0;Flag=5;"
    "CP=&&RtdInterval=30&&1C80\r\n"
)

MONITORING_SEGMENT = (
    "QN=20160801085857223;ST=32;CN=2061;PW=123456;"
    "MN=010000A8900016F000169DC0;Flag=5;"
    "CP=&&DataTime=20160801080000;"
    "w01001-Avg=7.5,w01001-Min=7.1;w01018-Avg=40.1&&"
)


class HJ212ParserTests(unittest.TestCase):
    def test_official_annex_a_crc_vector(self):
        self.assertEqual(HJ212Parser.crc16(OFFICIAL_SAMPLE[6:107]), 0x1C80)
        self.assertTrue(HJ212Parser.is_valid_message(OFFICIAL_SAMPLE))
        self.assertTrue(HJ212Parser.validate_crc(OFFICIAL_SAMPLE))

    def test_build_and_validate_round_trip(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        self.assertTrue(HJ212Parser.is_valid_message(message))
        self.assertTrue(HJ212Parser.validate_crc(message))
        self.assertEqual(int(message[2:6]), len(MONITORING_SEGMENT))

    def test_declared_length_mismatch_is_rejected(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        mutated = "##0001" + message[6:]
        self.assertFalse(HJ212Parser.is_valid_message(mutated))
        self.assertFalse(HJ212Parser.validate_crc(mutated))

    def test_bad_header_terminator_and_crc_are_rejected(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        self.assertFalse(HJ212Parser.is_valid_message("!!" + message[2:]))
        self.assertFalse(HJ212Parser.is_valid_message(message[:-2]))
        wrong_crc = message[:6] + message[6:-6] + "0000\r\n"
        self.assertFalse(HJ212Parser.validate_crc(wrong_crc))

    def test_malformed_length_and_crc_fields_are_rejected(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        self.assertFalse(HJ212Parser.is_valid_message("##0A01" + message[6:]))
        invalid_crc = message[:-6] + "ZZZZ\r\n"
        self.assertFalse(HJ212Parser.is_valid_message(invalid_crc))

    def test_crc_invalid_frame_cannot_be_parsed(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        wrong_crc = message[:-6] + "0000\\r\\n"
        with self.assertRaises(ValueError):
            HJ212Parser.parse_data_segment(wrong_crc)
    def test_cp_is_kept_intact_and_outer_fields_are_parsed(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        fields = HJ212Parser.parse_data_segment(message)
        self.assertEqual(fields["ST"], "32")
        self.assertEqual(fields["CN"], "2061")
        self.assertEqual(
            fields["CP"],
            "&&DataTime=20160801080000;"
            "w01001-Avg=7.5,w01001-Min=7.1;w01018-Avg=40.1&&",
        )

    def test_monitoring_items_include_comma_and_semicolon_groups(self):
        message = HJ212Parser.build_message(MONITORING_SEGMENT)
        self.assertEqual(
            HJ212Parser.extract_monitoring_data(message),
            [
                {"factor_code": "w01001", "data_type": "Avg", "value": "7.5"},
                {"factor_code": "w01001", "data_type": "Min", "value": "7.1"},
                {"factor_code": "w01018", "data_type": "Avg", "value": "40.1"},
            ],
        )

    def test_missing_cp_returns_no_monitoring_items(self):
        segment = "QN=20160801085857223;ST=32;CN=1062;Flag=5"
        self.assertEqual(HJ212Parser.extract_monitoring_data(HJ212Parser.build_message(segment)), [])

    def test_non_ascii_and_oversize_inputs_are_rejected(self):
        with self.assertRaises(ValueError):
            HJ212Parser.build_message("ST=32;Note=环境")
        with self.assertRaises(ValueError):
            HJ212Parser.build_message("X" * 1025)

    def test_malformed_and_duplicate_data_fields_raise(self):
        malformed = HJ212Parser.build_message("ST=32;BROKEN")
        with self.assertRaises(ValueError):
            HJ212Parser.parse_data_segment(malformed)
        duplicate = HJ212Parser.build_message("ST=32;ST=91")
        with self.assertRaises(ValueError):
            HJ212Parser.parse_data_segment(duplicate)


if __name__ == "__main__":
    unittest.main(verbosity=2)

