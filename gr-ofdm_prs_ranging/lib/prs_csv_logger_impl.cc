/* -*- c++ -*- */
/*
 * Copyright 2026 GNU Radio ZC TWR contributors.
 *
 * SPDX-License-Identifier: GPL-3.0-or-later
 */

#include "prs_csv_logger_impl.h"
#include <gnuradio/io_signature.h>

namespace gr {
namespace ofdm_prs_ranging {

prs_csv_logger::sptr prs_csv_logger::make(const std::string& path, bool append)
{
    return gnuradio::make_block_sptr<prs_csv_logger_impl>(path, append);
}

prs_csv_logger_impl::prs_csv_logger_impl(const std::string& path, bool append)
    : gr::block("prs_csv_logger",
                gr::io_signature::make(0, 0, 0),
                gr::io_signature::make(0, 0, 0)),
      d_file(path, append ? std::ios::app : std::ios::trunc)
{
    if (!append || d_file.tellp() == 0) {
        d_file << "frame_id,coarse_delay,fine_delay,cfo,snr,phase_residual,peak_metric,quality\n";
    }
    message_port_register_in(pmt::mp("measurement_in"));
    set_msg_handler(pmt::mp("measurement_in"),
                    [this](pmt::pmt_t msg) { handle_measurement(msg); });
}

prs_csv_logger_impl::~prs_csv_logger_impl()
{
    if (d_file.is_open()) {
        d_file.flush();
    }
}

void prs_csv_logger_impl::handle_measurement(pmt::pmt_t msg)
{
    if (!pmt::is_pair(msg) || !d_file.is_open()) {
        return;
    }
    const auto meta = pmt::car(msg);
    d_file << dict_ref_uint64(meta, "frame_id", 0) << ','
           << dict_ref_double(meta, "coarse_delay", 0.0) << ','
           << dict_ref_double(meta, "fine_delay", 0.0) << ','
           << dict_ref_double(meta, "cfo", 0.0) << ','
           << dict_ref_double(meta, "snr", 0.0) << ','
           << dict_ref_double(meta, "phase_residual", 0.0) << ','
           << dict_ref_double(meta, "peak_metric", 0.0) << ','
           << dict_ref_double(meta, "quality", 0.0) << '\n';
    d_file.flush();
}

} // namespace ofdm_prs_ranging
} // namespace gr
