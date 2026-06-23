"""Smoke: OpenSeeFace UDP packet parse."""
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from openseeface_packet import (
    OSF_UDP_PACKET_SIZE,
    OSF_UDP_VALUE_COUNT,
    build_test_openseeface_udp_packet,
    parse_openseeface_udp_packet,
)


def test_packet_size() -> None:
    packet = build_test_openseeface_udp_packet()
    assert len(packet) == OSF_UDP_PACKET_SIZE
    assert OSF_UDP_VALUE_COUNT == 446


def test_parse_test_packet() -> None:
    frame = parse_openseeface_udp_packet(build_test_openseeface_udp_packet())
    assert frame is not None
    assert frame.left_eye_open == 1.0
    assert frame.right_eye_open == 1.0
    assert frame.mouth_open == 0.25


if __name__ == "__main__":
    test_packet_size()
    test_parse_test_packet()
    print("smoke_openseeface_packet_ok")
