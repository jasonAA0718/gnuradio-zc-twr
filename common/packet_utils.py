import pmt


PAYLOAD_SYNC = 0xA5C3
PAYLOAD_SYNC_BITS = 16
RESPONDER_ID_BITS = 8
T2_MINUS_T3_BITS = 24
MEASUREMENT_NUMBER_BITS = 12
CRC_BITS = 8
RESPONSE_BODY_BITS = (
    RESPONDER_ID_BITS
    + T2_MINUS_T3_BITS
    + MEASUREMENT_NUMBER_BITS
)
RESPONSE_PACKET_BITS = PAYLOAD_SYNC_BITS + RESPONSE_BODY_BITS + CRC_BITS


def pmt_time_to_ticks(self, time_pmt):
    """
    Convert GNU Radio/UHD rx_time PMT tuple into integer sample ticks.

    rx_time format is usually:
        (full_seconds, fractional_seconds)

    tick unit:
        1 tick = 1 sample period
    """
    full_sec = int(pmt.to_uint64(pmt.tuple_ref(time_pmt, 0)))
    frac_sec = float(pmt.to_double(pmt.tuple_ref(time_pmt, 1)))

    sr = int(round(self.samp_rate))

    return full_sec * sr + int(round(frac_sec * sr))


def ticks_to_pmt_time(self, ticks):
    """
    Convert integer sample ticks back to UHD tx_time PMT tuple.
    """
    sr = int(round(self.samp_rate))

    full_sec = int(ticks // sr)
    frac_ticks = int(ticks % sr)
    frac_sec = frac_ticks / float(sr)

    return pmt.make_tuple(
        pmt.from_uint64(full_sec),
        pmt.from_double(frac_sec)
    )


def int_to_bits(value, width):
    value = int(value) & ((1 << width) - 1)
    return [(value >> i) & 1 for i in reversed(range(width))]


def bits_to_int(bits):
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return value


def bits_to_signed_int(bits):
    value = bits_to_int(bits)
    sign_bit = 1 << (len(bits) - 1)
    if value & sign_bit:
        value -= 1 << len(bits)
    return value


def crc8(bits, poly=0x07, init=0x00):
    """CRC-8 over MSB-first input bits, polynomial x^8 + x^2 + x + 1."""
    crc = init & 0xFF

    for bit in bits:
        feedback = ((crc >> 7) & 1) ^ int(bit)
        crc = (crc << 1) & 0xFF
        if feedback:
            crc ^= poly

    return crc & 0xFF


def find_payload_sync(bits, payload_sync=PAYLOAD_SYNC):
    sync_bits = int_to_bits(payload_sync, PAYLOAD_SYNC_BITS)
    limit = len(bits) - RESPONSE_PACKET_BITS + 1
    for start in range(max(0, limit)):
        if list(bits[start:start + PAYLOAD_SYNC_BITS]) == sync_bits:
            return start
    return -1


def build_response_packet(
    responder_id,
    t2_minus_t3,
    measurement_number,
    payload_sync=PAYLOAD_SYNC,
):
    """
    Response packet:
        Payload Sync          16 bit
        Responder ID           8 bit
        T2-T3                 24 bit
        Measurement Number    12 bit
        CRC8                   8 bit

    Return:
        list[int] bits, MSB first
    """
    sync_bits = int_to_bits(payload_sync, PAYLOAD_SYNC_BITS)

    body_bits = []
    body_bits += int_to_bits(responder_id, RESPONDER_ID_BITS)
    body_bits += int_to_bits(t2_minus_t3, T2_MINUS_T3_BITS)
    body_bits += int_to_bits(measurement_number, MEASUREMENT_NUMBER_BITS)

    crc_value = crc8(body_bits)
    crc_bits = int_to_bits(crc_value, CRC_BITS)

    return sync_bits + body_bits + crc_bits


def decode_response_packet(packet_bits, payload_sync=PAYLOAD_SYNC):
    """
    Decode and validate a response packet.

    Return:
        responder_id, t2_minus_t3, measurement_number
    """
    packet_bits = [int(b) for b in packet_bits]
    sync_start = find_payload_sync(packet_bits, payload_sync)
    if sync_start < 0:
        raise ValueError("payload sync not found")

    packet_end = sync_start + RESPONSE_PACKET_BITS
    if len(packet_bits) < packet_end:
        raise ValueError("incomplete response packet")

    body_start = sync_start + PAYLOAD_SYNC_BITS
    body_end = body_start + RESPONSE_BODY_BITS
    body_bits = packet_bits[body_start:body_end]

    expected_crc = crc8(body_bits)
    received_crc = bits_to_int(packet_bits[body_end:packet_end])
    if received_crc != expected_crc:
        raise ValueError(
            f"CRC mismatch: received=0x{received_crc:02X}, expected=0x{expected_crc:02X}"
        )

    responder_id = bits_to_int(body_bits[0:RESPONDER_ID_BITS])
    t2_minus_t3_start = RESPONDER_ID_BITS
    measurement_start = t2_minus_t3_start + T2_MINUS_T3_BITS
    t2_minus_t3 = bits_to_signed_int(body_bits[t2_minus_t3_start:measurement_start])
    measurement_number = bits_to_int(body_bits[measurement_start:RESPONSE_BODY_BITS])

    return responder_id, t2_minus_t3, measurement_number
