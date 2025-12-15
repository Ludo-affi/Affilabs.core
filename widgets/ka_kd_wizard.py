import csv
from copy import deepcopy
from functools import partial

import numpy as np
from pyqtgraph import mkBrush, mkPen
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QHeaderView

from settings import CH_LIST, DEV, GRAPH_COLORS
from ui.ui_ka_kd_wizard import Ui_KAKDWizardDialog
from utils.logger import logger
from utils.statistics import optimize_assoc, optimize_by_linear, optimize_rmax
from utils.validator import NumericDelegate
from widgets.message import show_message
from widgets.table_item import CenteredQTableWidgetItem


class KAKDWizardDialog(QDialog):
    closed = Signal()

    def __init__(self, parent, seg_data, units):
        super().__init__(parent)
        self.ui = Ui_KAKDWizardDialog()
        self.ui.setupUi(self)
        self.seg_data = seg_data
        self.units = units

        self.ui.btn_kd.released.connect(self._on_btn_kd)
        self.ui.btn_save.released.connect(self._on_btn_save)

        delegate = NumericDelegate(self.ui.table)
        self.ui.table.setItemDelegate(delegate)

        self.ui.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents,
        )
        self.ui.graph.getAxis("bottom").enableAutoSIPrefix(False)
        self.ui.graph.getAxis("left").enableAutoSIPrefix(False)
        self.ui.graph.plotItem.setTitle("Ks vs Concentration", color="w")
        self.ui.graph.setLabel(axis="bottom", text="Concentration")
        self.ui.graph.setLabel(axis="left", text="Ks")
        self.ui.graph.plotItem.showGrid(x=True, y=True, alpha=0.3)
        if DEV:
            self.ui.graph.setMenuEnabled(True)
            self.ui.graph.setMouseEnabled(x=True, y=True)
        else:
            self.ui.graph.setMenuEnabled(False)
            self.ui.graph.setMouseEnabled(x=False, y=False)

        self._fitted_plot = self.ui.graph.plot(pen="r")
        self._conc_plot = self.ui.graph.plot(symbol="o")
        self._result = {ch: {} for ch in CH_LIST}  # Result
        self._cur_ch = "a"
        self._assoc_shift_data = {
            ch: [round(s.assoc_shift[ch], 1) for s in self.seg_data] for ch in CH_LIST
        }
        self._dissoc_shift_data = {
            ch: [round(s.dissoc_shift[ch], 1) for s in self.seg_data] for ch in CH_LIST
        }
        self.conc_data = {ch: [s.conc[ch] for s in self.seg_data] for ch in CH_LIST}
        self.seg_names = {ch: [] for ch in CH_LIST}
        for ch in CH_LIST:
            getattr(self.ui, f"ch_{ch}").toggled.connect(
                partial(self._on_channel_changed, ch),
            )
        self._load_channel_seg_data()
        self._on_btn_kd()

    def _detect_kinetic_model(self, seg_data, conc_data):
        """Detect whether data is suitable for single-cycle or multi-cycle analysis.

        Args:
            seg_data: List of segment data
            conc_data: Concentration data for current channel

        Returns:
            str: 'single-cycle' or 'multi-cycle'

        """
        # Count unique non-zero concentrations
        unique_concs = [c for c in conc_data if c > 0]
        unique_conc_count = len(set(unique_concs))

        # Check for concentration series (multi-cycle indicator)
        if unique_conc_count >= 3:  # Need at least 3 points for good multi-cycle fit
            logger.debug(
                f"Multi-cycle detected: {unique_conc_count} unique concentrations",
            )
            return "multi-cycle"

        # Check if we have a single high-quality curve (single-cycle indicator)
        if unique_conc_count == 1 and len(seg_data) == 1:
            seg = seg_data[0]
            ch = self._cur_ch

            # Check data quality for single-cycle analysis
            if (
                len(seg.seg_y[ch]) > 50  # Sufficient data points
                and np.max(seg.seg_y[ch]) > 10  # Sufficient signal
                and len(seg.d_seg_y[ch]) > 20
            ):  # Sufficient dissociation data
                logger.debug("Single-cycle detected: Single high-quality binding curve")
                return "single-cycle"

        # Default to multi-cycle for marginal cases
        logger.debug(
            f"Defaulting to multi-cycle: {unique_conc_count} concentrations, {len(seg_data)} segments",
        )
        return "multi-cycle"

    def _analyze_single_cycle(self, seg, concentration):
        """Perform single-cycle kinetic analysis on a single binding curve.

        Args:
            seg: Single segment data
            concentration: Analyte concentration in M

        Returns:
            dict: Kinetic parameters (ka, kd, KD, Rmax, r_sq)

        """
        ch = self._cur_ch

        try:
            # Step 1: Analyze dissociation phase for kd
            logger.debug("Single-cycle: Analyzing dissociation phase")

            # Find dissociation data (should be decreasing)
            d_data = seg.d_seg_y[ch]
            d_time = seg.d_seg_x[ch] - seg.d_seg_x[ch][0]

            # Remove points where signal <= 0
            valid_indices = d_data > 0
            if not np.any(valid_indices):
                raise ValueError("No valid dissociation data")

            d_data_valid = d_data[valid_indices]
            d_time_valid = d_time[valid_indices]

            # Exponential decay fitting: R(t) = R0 * exp(-kd*t)
            # Linearize: ln(R(t)) = ln(R0) - kd*t
            ln_d_data = np.log(d_data_valid)
            res = optimize_by_linear(d_time_valid, ln_d_data)
            kd = -float(res["a"])  # Slope is -kd
            r_sq_dissoc = res["r_sq"]

            if kd <= 0:
                raise ValueError("Invalid kd from dissociation analysis")

            logger.debug(f"Single-cycle kd: {kd:.2e}, R²: {r_sq_dissoc:.3f}")

            # Step 2: Analyze association phase for ka and Rmax
            logger.debug("Single-cycle: Analyzing association phase")

            a_data = seg.seg_y[ch]
            a_time = seg.seg_x[ch] - seg.seg_x[ch][0]

            # Estimate Req from association plateau
            req_est = np.mean(a_data[-10:])

            # Initial estimates for fitting
            ka_init = 1e6  # Default initial guess (M⁻¹s⁻¹)
            rmax_init = req_est * 1.2  # Slightly higher than equilibrium

            # Use non-linear optimization for association phase
            res = optimize_assoc(a_time, a_data, concentration, kd, ka_init, rmax_init)
            ka = res["ka"]
            rmax = res["rmax"]

            if ka <= 0 or rmax <= 0:
                raise ValueError("Invalid ka or Rmax from association analysis")

            logger.debug(f"Single-cycle ka: {ka:.2e}, Rmax: {rmax:.2f}")

            # Step 3: Calculate final parameters
            KD = kd / ka

            # Calculate goodness of fit for association
            predicted_assoc = [
                (ka * concentration * rmax)
                * (1 - np.exp(-((ka * concentration) + kd) * t))
                / ((ka * concentration) + kd)
                for t in a_time
            ]

            # R-squared for association fit
            ss_res = np.sum((a_data - predicted_assoc) ** 2)
            ss_tot = np.sum((a_data - np.mean(a_data)) ** 2)
            r_sq_assoc = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            # Average R-squared
            r_sq = (r_sq_dissoc + r_sq_assoc) / 2

            results = {
                "ka": ka,
                "kd": kd,
                "KD": KD,
                "Rmax": rmax,
                "r_sq": r_sq,
                "model": "single-cycle",
                "concentration": concentration,
            }

            logger.debug(
                f"Single-cycle results: KD={KD:.2e}, Rmax={rmax:.2f}, R²={r_sq:.3f}",
            )
            return results

        except Exception as e:
            logger.error(f"Single-cycle analysis failed: {e}")
            raise

    def _analyze_multi_cycle(self, sorted_segs, sorted_c_m):
        """Perform multi-cycle kinetic analysis (original method).

        Args:
            sorted_segs: List of segment data sorted by concentration
            sorted_c_m: Concentrations in M

        Returns:
            dict: Kinetic parameters (ka, kd, KD, Rmax, r_sq)

        """
        ch = self._cur_ch
        logger.debug("Multi-cycle: Performing concentration series analysis")

        # Use dissociation data to determine initial kd
        kd_0 = []
        for seg in sorted_segs:
            i = 0
            while i < len(seg.d_seg_y[ch]):
                if seg.d_seg_y[ch][i] <= 0:
                    break
                i += 1
            # Correct dissociation analysis: ln(R(t)) vs time
            r_data = np.log(seg.d_seg_y[ch][0:i])
            t_data = seg.d_seg_x[ch][0:i] - seg.d_seg_x[ch][0]
            # Slope is -kd, so negate to get kd
            kd_0.append(-float(optimize_by_linear(t_data, r_data)["a"]))
        kd_0_pos = []
        for k in kd_0:
            if k > 0:
                kd_0_pos.append(k)
        for i in range(len(kd_0)):
            kd_0_avg = np.nanmean(kd_0_pos)
            if (kd_0[i] < 0) or (abs((kd_0[i] - kd_0_avg) / kd_0_avg) > 2):
                kd_0[i] = np.nanmean(kd_0_pos)
        logger.debug(f"initial kd value: {kd_0}")

        # Use the association data to determine initial ka, Rmax
        # Improved method: Use proper association kinetics fitting
        ka_0 = []
        rmax_0 = []
        for i, seg in enumerate(sorted_segs):
            ka_est, rmax_est = self._estimate_association_parameters(
                seg,
                sorted_c_m[i],
                kd_0[i],
            )
            ka_0.append(ka_est)
            rmax_0.append(rmax_est)
        ka_0_pos = []
        for k in ka_0:
            if k > 0:
                ka_0_pos.append(k)
        for i in range(len(ka_0)):
            ka_0_avg = np.nanmean(ka_0_pos)
            if (ka_0[i] < 0) or (abs((ka_0[i] - ka_0_avg) / ka_0_avg) > 2):
                ka_0[i] = np.nanmean(ka_0_pos)
        logger.debug(f"initial ka values: {ka_0}")
        rmax_0_pos = []
        for k in rmax_0:
            if k > 0:
                rmax_0_pos.append(k)
        for i in range(len(rmax_0)):
            rmax_0_avg = np.nanmean(rmax_0_pos)
            if (rmax_0[i] < 0) or (abs((rmax_0[i] - rmax_0_avg) / rmax_0_avg) > 2):
                rmax_0[i] = np.nanmean(rmax_0_pos)
        logger.debug(f"initial Rmax values: {rmax_0}")

        # Refine local ka, Rmax through non-linear optimization
        for i, seg in enumerate(sorted_segs):
            res = optimize_assoc(
                seg.seg_x[ch],
                seg.seg_y[ch],
                sorted_c_m[i],
                kd_0[i],
                ka_0[i],
                rmax_0[i],
            )
            logger.debug(f"Seg {i}, refined ka, rmax{res}")
            ka_0[i] = res["ka"]
            rmax_0[i] = res["rmax"]

        # Use final local ks to find global ka, kd
        ks = []
        for i, seg in enumerate(sorted_segs):
            ks.append((ka_0[i] * sorted_c_m[i]) + kd_0[i])
        logger.debug(f"local ks values {ks}")
        res = optimize_by_linear(sorted_c_m, ks)
        ka = res["a"]
        kd = res["b"]
        r_sq = res["r_sq"]

        # Calculate the global Rmax using the equilibrium values
        req = []
        for seg in sorted_segs:
            req.append(seg.seg_y[ch][-1])
        res = optimize_rmax(sorted_c_m, req, (kd / ka), rmax_0[-1])
        rmax = res["rmax"]
        logger.debug(f"global Rmax: {rmax}")

        results = {
            "ka": ka,
            "kd": kd,
            "KD": kd / ka,
            "Rmax": rmax,
            "r_sq": r_sq,
            "model": "multi-cycle",
            "ks": ks,
            "c": sorted_c_m,
        }

        return results

    def _estimate_association_parameters(self, seg, concentration, kd_est):
        """Estimate initial ka and Rmax from association data using proper kinetics.

        Args:
            seg: Segment data containing association response
            concentration: Concentration in M
            kd_est: Estimated dissociation rate constant

        Returns:
            tuple: (ka_estimate, rmax_estimate)

        """
        ch = self._cur_ch

        # Get association data
        t_data = seg.seg_x[ch] - seg.seg_x[ch][0]  # Time from start
        r_data = seg.seg_y[ch]  # Response data

        # Estimate Req from final plateau value
        req_est = np.mean(r_data[-10:])  # Average last 10 points

        try:
            # Use association kinetics: R(t) = Req * (1 - exp(-kobs*t))
            # Rearrange: ln(1 - R(t)/Req) = -kobs*t
            r_norm = r_data / max(req_est, 1e-6)
            r_norm = np.clip(r_norm, 0, 0.99)  # Ensure 0 < r_norm < 1
            ln_data = np.log(1 - r_norm)

            # Linear fit to get kobs
            res = optimize_by_linear(t_data[1:], ln_data[1:])
            kobs_est = -float(res["a"])  # Slope is -kobs

            # Ensure positive kobs
            if kobs_est <= 0:
                kobs_est = 0.1  # Default fallback

            # Calculate ka: kobs = ka*C + kd, so ka = (kobs - kd)/C
            ka_est = max(0, (kobs_est - kd_est) / concentration)

            # Calculate Rmax: Req = (ka*C*Rmax)/(ka*C + kd)
            if ka_est > 0:
                rmax_est = (
                    req_est
                    * (ka_est * concentration + kd_est)
                    / (ka_est * concentration)
                )
            else:
                rmax_est = req_est * 2  # Fallback estimate

        except (ValueError, ZeroDivisionError, RuntimeWarning):
            # Fallback to simple estimates if fitting fails
            ka_est = 1e6  # Default ka estimate (M⁻¹s⁻¹)
            rmax_est = req_est * 2  # Simple Rmax estimate

        return ka_est, abs(rmax_est)  # Ensure positive Rmax

    def _on_btn_kd(self):
        try:
            ch = self._cur_ch
            self.conc_data[ch] = []
            no_data_flag = False
            for row, seg in enumerate(self.seg_data):
                seg.conc[ch] = float(self.ui.table.item(row, 1).text())
                self.conc_data[ch].append(float(self.ui.table.item(row, 1).text()))
                if np.all(seg.seg_y[ch] == 0) or np.all(np.isnan(seg.seg_y[ch])):
                    no_data_flag = True
            c_list = np.array(self.conc_data[ch])
            if np.all(c_list == 0) or np.all(np.isnan(c_list)):
                show_message(
                    msg="Please input concentration values!",
                    msg_type="Warning",
                )
            if no_data_flag:
                show_message(msg="No data on channel", msg_type="Warning")
            else:
                # Automatic model selection
                kinetic_model = self._detect_kinetic_model(
                    self.seg_data,
                    self.conc_data[ch],
                )
                logger.info(f"Selected kinetic model: {kinetic_model}")

                if kinetic_model == "single-cycle":
                    # Single-cycle analysis
                    if len(self.seg_data) == 1:
                        concentration = self.conc_data[ch][0] * 1e-9  # Convert to M
                        result = self._analyze_single_cycle(
                            self.seg_data[0],
                            concentration,
                        )

                        # Store results
                        self._result[ch] = result

                        # Update UI
                        self.ui.graph.plotItem.setTitle(
                            "Single-Cycle Kinetic Analysis",
                            color="w",
                        )
                        logger.info(
                            f"Single-cycle results: KD={result['KD']:.2e}, ka={result['ka']:.2e}, kd={result['kd']:.2e}",
                        )
                    else:
                        show_message(
                            msg="Single-cycle requires exactly one segment",
                            msg_type="Warning",
                        )
                        return

                else:
                    # Multi-cycle analysis (original method)
                    # Sort segments by concentration
                    sorted_c_list = np.sort(c_list)
                    sorted_segs = []
                    for i in range(len(self.seg_data)):
                        for seg in self.seg_data:
                            if seg.conc[ch] == sorted_c_list[i]:
                                sorted_segs.append(deepcopy(seg))
                    sorted_c_m = np.array(sorted_c_list * 1e-9)

                    result = self._analyze_multi_cycle(sorted_segs, sorted_c_m)

                    # Store results
                    self._result[ch] = result

                    # Update UI
                    self.ui.graph.plotItem.setTitle(
                        "Multi-Cycle Kinetic Analysis",
                        color="w",
                    )
                    logger.info(
                        f"Multi-cycle results: KD={result['KD']:.2e}, ka={result['ka']:.2e}, kd={result['kd']:.2e}",
                    )

                # Draw plot and enable save button
                self._draw_plot()
                self.ui.btn_save.setEnabled(True)

        except Exception as e:
            logger.debug(f"Failed to calculate ka/kd: {e}")
            show_message(msg="Calculation Error", msg_type="Error")

    def _on_btn_save(self):
        try:
            export_file = QFileDialog.getSaveFileName(
                self,
                "Choose directory and filename for KD export",
                "",
            )[0]
            if export_file:
                for ch in CH_LIST:
                    if self._result[ch]:
                        with open(
                            file=f"{export_file}.txt",
                            mode="w",
                            newline="",
                            encoding="utf-8",
                        ) as txtfile:
                            fieldnames = [
                                "Seg ID",
                                f"Conc_{ch.upper()}",
                                f"Assoc_Shift_{ch.upper()}",
                                f"Dissoc_Shift_{ch.upper()}",
                            ]
                            writer = csv.DictWriter(
                                txtfile,
                                dialect="excel-tab",
                                fieldnames=fieldnames,
                            )
                            writer.writeheader()
                            for i, seg in enumerate(self.seg_data):
                                data = {
                                    "Seg ID": f"{seg.name}",
                                    f"Assoc_Shift_{ch.upper()}": seg.assoc_shift[ch],
                                    f"Dissoc_Shift_{ch.upper()}": seg.dissoc_shift[ch],
                                    f"Conc_{ch.upper()}": self.conc_data[ch][i],
                                }
                                writer.writerow(data)
                            result_strings = [
                                f"KD: {self._result[ch]['KD']:.2e}",
                                f"Rmax: {self._result[ch]['Rmax']:.2f}",
                                f"R Squared: {self._result[ch]['r_sq']:.2f}",
                                f"ka: {self._result[ch]['ka']:.2e}",
                                f"kd: {self._result[ch]['kd']:.2e}",
                            ]
                            for r in result_strings:
                                txtfile.writelines(r + "\n")
                show_message(msg="Kinetic data exported")
        except Exception as e:
            logger.debug(f"Error during KD export: {e}")
            show_message(msg="KD export error", msg_type="Warning")

    def _draw_plot(self):
        ch = self._cur_ch
        if self._result[ch]:
            model_type = self._result[ch].get("model", "multi-cycle")

            if model_type == "single-cycle":
                # For single-cycle, show a simple point with no fitted line
                concentration = self._result[ch].get("concentration", 0)
                # Calculate observed rate constant for display
                kobs = (self._result[ch]["ka"] * concentration) + self._result[ch]["kd"]

                # Plot single point
                self._conc_plot.setSymbolBrush(mkBrush(GRAPH_COLORS[self._cur_ch]))
                self._conc_plot.setData(x=[concentration], y=[kobs])

                # No fitted line for single point
                self._fitted_plot.setData([], [])

                # Update graph labels for single-cycle
                self.ui.graph.setLabel(axis="bottom", text="Concentration (M)")
                self.ui.graph.setLabel(axis="left", text="kobs (s⁻¹)")

            # Multi-cycle plotting (original method)
            elif "c" in self._result[ch] and "ks" in self._result[ch]:
                x_data = np.array(self._result[ch]["c"])
                y_data = np.array(self._result[ch]["ks"])

                self._conc_plot.setSymbolBrush(mkBrush(GRAPH_COLORS[self._cur_ch]))
                self._conc_plot.setData(x=x_data, y=y_data)

                # Fitted line: kobs = ka*C + kd
                fitted = [
                    (self._result[ch]["ka"] * x) + self._result[ch]["kd"]
                    for x in x_data
                ]
                self._fitted_plot.setPen(mkPen(GRAPH_COLORS[self._cur_ch], width=3))
                self._fitted_plot.setData(x=x_data, y=fitted)

                # Update graph labels for multi-cycle
                self.ui.graph.setLabel(axis="bottom", text="Concentration (M)")
                self.ui.graph.setLabel(axis="left", text="kobs (s⁻¹)")
            else:
                # Clear plot if no data
                self._fitted_plot.setData([], [])
                self._conc_plot.setData([], [])

            # Auto-range the plot
            self.ui.graph.plotItem.vb.autoRange(padding=0.1)

            # Update result labels
            for k in ("KD", "ka", "kd"):
                getattr(self.ui, f"lb_{k}").setText(f"{self._result[ch][k]:.2e}")
            for k in ("Rmax", "r_sq"):
                getattr(self.ui, f"lb_{k}").setText(f"{self._result[ch][k]:.2f}")
        else:
            # Clear everything if no results
            for k in ("KD", "Rmax", "r_sq", "ka", "kd"):
                getattr(self.ui, f"lb_{k}").setText("")
            self._fitted_plot.setData([])
            self._conc_plot.setData([])

    def _on_channel_changed(self, ch, active):
        if active:
            self._cur_ch = ch
            self._load_channel_seg_data()
        else:  # Save current conc data
            self.conc_data[ch] = [
                float(self.ui.table.item(row, 2).text())
                for row in range(len(self.seg_data))
            ]

    def _load_channel_seg_data(self):
        table = self.ui.table
        table.horizontalHeaderItem(2).setText(f"Association\nShift ({self.units})")
        table.horizontalHeaderItem(3).setText(f"Dissociation\nShift ({self.units})")
        table.setRowCount(0)
        table.setRowCount(len(self.seg_data))

        for i, s in enumerate(self.seg_data):
            table.setItem(i, 0, CenteredQTableWidgetItem(f"{s.name}"))
            table.setItem(
                i,
                2,
                CenteredQTableWidgetItem(str(self._assoc_shift_data[self._cur_ch][i])),
            )
            table.setItem(
                i,
                3,
                CenteredQTableWidgetItem(str(self._dissoc_shift_data[self._cur_ch][i])),
            )
            item = CenteredQTableWidgetItem(str(self.conc_data[self._cur_ch][i]))
            item.setFlags(Qt.NoItemFlags)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            table.setItem(i, 1, item)
            for j in (0, 2, 3):  # Disable edit except conc value
                table.item(i, j).setFlags(Qt.ItemIsEnabled)
        self._draw_plot()

    def closeEvent(self, arg__1):
        try:
            self.conc_data[self._cur_ch] = [
                float(self.ui.table.item(row, 1).text())
                for row in range(len(self.seg_data))
            ]
            self.seg_names[self._cur_ch] = [
                (self.ui.table.item(row, 0).text()) for row in range(len(self.seg_data))
            ]
        except Exception as e:
            logger.debug(f"Error while getting kinetic conc data: {e}")
        self.closed.emit()
