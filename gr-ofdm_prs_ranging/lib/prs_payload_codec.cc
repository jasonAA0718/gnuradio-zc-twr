/* -*- c++ -*- */
/*
 * Copyright 2026 GNU Radio ZC TWR contributors.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "prs_payload_codec.h"
#include <algorithm>
#include <cmath>

namespace gr {
namespace ofdm_prs_ranging {

namespace {
gr_complex qpsk_symbol(bool bit0, bool bit1, float amplitude)
{
    const float scale = amplitude * static_cast<float>(1.0 / std::sqrt(2.0));
    return gr_complex(bit0 ? scale : -scale, bit1 ? scale : -scale);
}

gr_complex unit_ref_symbol(int index)
{
    const bool bit0 = (index & 0x1) != 0;
    const bool bit1 = (index & 0x2) != 0;
    return qpsk_symbol(bit0, bit1, 1.0f);
}
} // namespace

void encode_frame_id_payload(uint64_t frame_id,
                             float amplitude,
                             std::vector<gr_complex>::iterator out)
{
    for (int i = 0; i < prs_frame_id_ref_symbols; ++i) {
        *(out++) = unit_ref_symbol(i) * amplitude;
    }

    for (int i = 0; i < prs_frame_id_data_symbols; ++i) {
        const bool bit0 = ((frame_id >> (2 * i)) & 0x1U) != 0;
        const bool bit1 = ((frame_id >> (2 * i + 1)) & 0x1U) != 0;
        *(out++) = qpsk_symbol(bit0, bit1, amplitude);
    }
}

bool decode_frame_id_payload(const gr_complex* payload,
                             int payload_len,
                             uint64_t& frame_id,
                             float& metric)
{
    frame_id = 0;
    metric = 0.0f;
    if (payload == nullptr || payload_len < prs_frame_id_payload_symbols) {
        return false;
    }

    gr_complex ref_corr(0.0f, 0.0f);
    double ref_power = 0.0;
    for (int i = 0; i < prs_frame_id_ref_symbols; ++i) {
        const auto expected = unit_ref_symbol(i);
        ref_corr += payload[i] * std::conj(expected);
        ref_power += std::norm(payload[i]);
    }

    const float ref_mag = std::abs(ref_corr);
    if (ref_mag <= 0.0f || ref_power <= 0.0) {
        return false;
    }

    const gr_complex correction = std::conj(ref_corr) / ref_mag;
    metric = static_cast<float>(
        std::min(1.0, ref_mag / std::sqrt(ref_power * prs_frame_id_ref_symbols)));

    for (int i = 0; i < prs_frame_id_data_symbols; ++i) {
        const gr_complex corrected = payload[prs_frame_id_ref_symbols + i] * correction;
        if (corrected.real() >= 0.0f) {
            frame_id |= (uint64_t{ 1 } << (2 * i));
        }
        if (corrected.imag() >= 0.0f) {
            frame_id |= (uint64_t{ 1 } << (2 * i + 1));
        }
    }

    return true;
}

} // namespace ofdm_prs_ranging
} // namespace gr
