/* -*- c++ -*- */
/*
 * Copyright 2026 GNU Radio ZC TWR contributors.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#ifndef INCLUDED_OFDM_PRS_RANGING_PRS_PAYLOAD_CODEC_H
#define INCLUDED_OFDM_PRS_RANGING_PRS_PAYLOAD_CODEC_H

#include <gnuradio/gr_complex.h>
#include <cstdint>
#include <vector>

namespace gr {
namespace ofdm_prs_ranging {

constexpr int prs_frame_id_ref_symbols = 16;
constexpr int prs_frame_id_bits = 32;
constexpr int prs_frame_id_crc_bits = 16;
constexpr int prs_frame_id_repeat = 5;
constexpr int prs_frame_id_data_bits = prs_frame_id_bits + prs_frame_id_crc_bits;
constexpr int prs_frame_id_data_symbols = prs_frame_id_data_bits * prs_frame_id_repeat;
constexpr int prs_frame_id_payload_symbols =
    prs_frame_id_ref_symbols + prs_frame_id_data_symbols;

void encode_frame_id_payload(uint64_t frame_id,
                             float amplitude,
                             std::vector<gr_complex>::iterator out);
bool decode_frame_id_payload(const gr_complex* payload,
                             int payload_len,
                             uint64_t& frame_id,
                             float& metric);

} // namespace ofdm_prs_ranging
} // namespace gr

#endif /* INCLUDED_OFDM_PRS_RANGING_PRS_PAYLOAD_CODEC_H */
