/* -*- c++ -*- */
/*
 * Copyright 2026 GNU Radio ZC TWR contributors.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include <gnuradio/ofdm_prs_ranging/prs_timed_burst_source.h>
#include <boost/test/unit_test.hpp>
#include <algorithm>

namespace gr {
namespace ofdm_prs_ranging {

BOOST_AUTO_TEST_CASE(test_prs_timed_burst_source_frame_geometry)
{
    auto src = prs_timed_burst_source::make();
    BOOST_CHECK_EQUAL(src->frame_len(), 23359);
    BOOST_CHECK_EQUAL(src->prs_start(), 1000 + 128 * 16 + 839 + 40);
    BOOST_CHECK_EQUAL(src->prs_len(), 16 * (1024 + 128));
}

BOOST_AUTO_TEST_CASE(test_prs_timed_burst_source_amplitude_limit)
{
    auto src = prs_timed_burst_source::make();
    const auto frame = src->frame_samples();
    const auto peak = std::max_element(frame.begin(), frame.end(), [](const auto& a, const auto& b) {
        return std::abs(a) < std::abs(b);
    });
    BOOST_REQUIRE(peak != frame.end());
    BOOST_CHECK_LE(std::abs(*peak), 0.800001f);
}

} /* namespace ofdm_prs_ranging */
} /* namespace gr */
