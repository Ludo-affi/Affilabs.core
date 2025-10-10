import csv
from copy import deepcopy
from functools import partial

import numpy as np
from pyqtgraph import mkBrush, mkPen
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFileDialog, QHeaderView

from settings import CH_LIST, DEV, GRAPH_COLORS
from ui.ui_kd_wizard import Ui_KDWizardDialog
from utils.logger import logger
from utils.statistics import func_affinity_fit, optimize_by_affinity, optimize_by_linear
from utils.validator import NumericDelegate
from widgets.message import show_message
from widgets.table_item import CenteredQTableWidgetItem


class KDWizardDialog(QDialog):
    closed = Signal()

    def __init__(self, parent, seg_data, units):
        super().__init__(parent)
        self.ui = Ui_KDWizardDialog()
        self.ui.setupUi(self)
        self.seg_data = seg_data
        self.units = units
        self.ui.btn_kd.released.connect(self._on_btn_kd)
        self.ui.btn_save.released.connect(self._on_btn_save)
        self.ui.chk_fitting_curve.stateChanged.connect(self._fit_check)
        self.ui.fit_affinity.clicked.connect(self._on_fit_check_changed)
        self.ui.fit_linear.clicked.connect(self._on_fit_check_changed)
        self.ui.add_shifts.toggled.connect(self._set_cumulative)
        delegate = NumericDelegate(self.ui.table)
        self.ui.table.setItemDelegate(delegate)
        self.ui.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self.ui.graph.getAxis("bottom").enableAutoSIPrefix(False)
        self.ui.graph.getAxis("left").enableAutoSIPrefix(False)
        self.ui.graph.plotItem.setTitle("Shift vs Concentration", color="w")
        self.ui.graph.setLabel(axis="bottom", text="Concentration")
        self.ui.graph.setLabel(axis="left", text="Shift", units="RU")
        self.ui.graph.plotItem.showGrid(x=True, y=True, alpha=0.3)
        if DEV:
            self.ui.p_val.setVisible(True)
        else:
            self.ui.p_val.setVisible(False)
        self.ui.graph.setMenuEnabled(True)
        self.ui.graph.setMouseEnabled(x=True, y=True)
        self._fitted_plot = self.ui.graph.plot(pen="r")
        self._conc_plot = self.ui.graph.plot(pen=None, symbol="o")
        self._result = {
            "affinity": {ch: {} for ch in CH_LIST},
            "linear": {ch: {} for ch in CH_LIST},
        }  # Result
        self.fitted_graph_data = {"affinity": {}, "linear": {}}  # Fitted graph data
        self._cur_ch = "a"
        self._shift_data = {ch: [] for ch in CH_LIST}
        self.conc_data = {ch: [] for ch in CH_LIST}
        self.seg_names = {ch: [] for ch in CH_LIST}
        self._load_seg_data()
        self._fitted_values = {"affinity": {}, "linear": {}}
        self._sd_values = {"affinity": {}, "linear": {}}
        self._model = {ch: [] for ch in CH_LIST}
        for ch in CH_LIST:
            getattr(self.ui, f"ch_{ch}").toggled.connect(
                partial(self._on_channel_changed, ch)
            )
        self._load_channel_seg_data()
        self._on_btn_kd()

    def _on_btn_kd(self):
        try:
            self.conc_data[self._cur_ch] = [
                float(self.ui.table.item(row, 1).text())
                for row in range(len(self.seg_data))
            ]
            c_list = np.array(self.conc_data[self._cur_ch])
            s_list = self._shift_data[self._cur_ch]
            if np.all(c_list == 0):
                show_message(
                    msg="Please input concentration values!", msg_type="Warning"
                )
                return
            if np.all(s_list == 0) or np.all(s_list == np.nan):
                show_message(msg="No data on channel!", msg_type="Warning")
                return
            # Sort X & Y axis data by X
            values = {c: s_list[i] for i, c in enumerate(c_list)}
            c_list = np.sort(c_list)
            s_list = [values[c] for c in sorted(c_list)]

            # Affinity Result
            ar = optimize_by_affinity(c_list=c_list, s_list=s_list)
            x_values = np.arange(
                max(0, (min(c_list) - (0.05 * (max(c_list) - min(c_list))))),
                max(c_list) + (0.05 * (max(c_list) - min(c_list))),
                (max(c_list) - min(c_list)) / 100,
            )
            y_values = func_affinity_fit(
                c_list=x_values, f=[ar["Rmax"], ar["KD"], ar["offset"]]
            )
            x_values_m = x_values * 1e-9
            self.fitted_graph_data["affinity"][self._cur_ch] = dict(
                x=x_values_m, y=y_values
            )
            self._result["affinity"][self._cur_ch] = deepcopy(ar)
            self._result["affinity"][self._cur_ch]["KD"] = (
                self._result["affinity"][self._cur_ch]["KD"] * 1e-9
            )
            self._fitted_values["affinity"][self._cur_ch] = ar["fitted"]
            self._sd_values["affinity"][self._cur_ch] = ar["sd"]

            # Linear Result
            lr = optimize_by_linear(xdata=c_list, ydata=s_list)
            self._result["linear"][self._cur_ch] = deepcopy(lr)
            self._fitted_values["linear"][self._cur_ch] = lr["fitted"]
            self._sd_values["linear"][self._cur_ch] = lr["sd"]
            self.fitted_graph_data["linear"][self._cur_ch] = dict(
                x=x_values_m, y=[lr["a"] * x + lr["b"] for x in x_values]
            )
            if self.ui.fit_affinity.isChecked():
                self._model[self._cur_ch] = "affinity"
            else:
                self._model[self._cur_ch] = "linear"
            self._draw_plot()
            self._fit_check()
            self.ui.btn_save.setEnabled(True)
        except Exception as e:
            logger.debug(f"Failed to calculate KD: {e}")
            show_message(msg="Calculation Error", msg_type="Error")

    def _on_btn_save(self):
        try:
            export_file = QFileDialog.getSaveFileName(
                self, "Choose directory and filename for KD export", ""
            )[0]
            if export_file:
                for ch in CH_LIST:
                    if self._fitted_values["affinity"].get(ch):
                        k = self._model[ch]
                        with open(
                            file=f"{export_file}.txt",
                            mode="w",
                            newline="",
                            encoding="utf-8",
                        ) as txtfile:
                            fieldnames = [
                                "Seg ID",
                                f"Conc_{ch.upper()}",
                                f"Shift_{ch.upper()}",
                                f"Fit_{ch.upper()}",
                                f"SD_{ch.upper()}",
                            ]
                            writer = csv.DictWriter(
                                txtfile, dialect="excel-tab", fieldnames=fieldnames
                            )
                            writer.writeheader()
                            for i, seg in enumerate(self.seg_data):
                                data = {
                                    "Seg ID": f"{seg.name}",
                                    f"Shift_{ch.upper()}": seg.assoc_shift[ch],
                                    f"Conc_{ch.upper()}": self.conc_data[ch][i],
                                }
                                if self._fitted_values[k].get(ch):
                                    data[f"Fit_{ch.upper()}"] = self._fitted_values[k][
                                        ch
                                    ][i]
                                else:
                                    data[f"Fit_{ch.upper()}"] = "N/A"
                                if self._sd_values[k].get(ch):
                                    data[f"SD_{ch.upper()}"] = self._sd_values[k][ch][i]
                                else:
                                    data[f"SD_{ch.upper()}"] = "N/A"
                                writer.writerow(data)
                            if k == "affinity":
                                result_strings = [
                                    "Fitting Model: Affinity",
                                    f"KD: {self._result['affinity'][ch]['KD']:.3f}",
                                    f"Rmax: {self._result['affinity'][ch]['Rmax']:.3f}",
                                    f"Chi Squared: {self._result['affinity'][ch]['chi_sq']:.3f}",
                                ]
                            else:
                                result_strings = [
                                    "Fitting Model: Linear",
                                    f"Equation: {self._result['linear'][ch]['a']:.3f} X + "
                                    f"{self._result['linear'][ch]['b']:.3f}",
                                    f"R Squared: {self._result['linear'][ch]['r_sq']:.3f}",
                                ]
                            for r in result_strings:
                                txtfile.writelines(r + "\n")
                show_message(msg="Fitting data exported")
        except Exception as e:
            logger.debug(f"Error during KD export: {e}")
            show_message(msg="Export Error", msg_type="Warning")

    def _draw_plot(self):
        if self.fitted_graph_data["affinity"].get(self._cur_ch):
            c_list = np.array(self.conc_data[self._cur_ch])
            s_list = self._shift_data[self._cur_ch]
            # Sort X & Y axis data by X
            values = {c: s_list[i] for i, c in enumerate(c_list)}
            c_list = np.sort(c_list)
            s_list = [values[c] for c in sorted(c_list)]
            c_list = c_list * 1e-9
            self._conc_plot.setSymbolBrush(mkBrush(GRAPH_COLORS[self._cur_ch]))
            self._conc_plot.setData(x=c_list, y=s_list)
            try:
                self.ui.kd_val.setText(
                    f"{self._result['affinity'][self._cur_ch]['KD']:.2e}"
                )
                self.ui.rmax_val.setText(
                    f"{self._result['affinity'][self._cur_ch]['Rmax']:.2f}"
                )
                self.ui.chi_sq_val.setText(
                    f"{self._result['affinity'][self._cur_ch]['chi_sq']:.2f}"
                )
                self.ui.lin_eqn.setText(
                    f"{self._result['linear'][self._cur_ch]['a']:.2e} X + "
                    f"{self._result['linear'][self._cur_ch]['b']:.2e}"
                )
                self.ui.r_sq_val.setText(
                    f"{self._result['linear'][self._cur_ch]['r_sq']:.2f}"
                )
                if DEV:
                    self.ui.p_val.setText(
                        f"p: {self._result['affinity'][self._cur_ch]['p_val']:.2f}"
                    )
            except Exception as e:
                logger.debug(f"current ch: {self._cur_ch}, result: {self._result}")
                logger.debug(f"Error updating results display: {e}")
        else:
            self._clear_results()

    def _clear_results(self):
        self.ui.kd_val.setText("")
        self.ui.rmax_val.setText("")
        self.ui.chi_sq_val.setText("")
        self.ui.lin_eqn.setText("")
        self.ui.r_sq_val.setText("")

    def _clear_plot(self):
        self._fitted_plot.setData([])
        self._conc_plot.setData([])

    def _load_seg_data(self):
        for ch in CH_LIST:
            self._shift_data[ch] = [round(s.assoc_shift[ch], 3) for s in self.seg_data]
            self.conc_data[ch] = [s.conc[ch] for s in self.seg_data]

    def _set_cumulative(self):
        ch_list = []
        for ch in CH_LIST:
            if not (
                np.all(self._shift_data[ch] == np.nan)
                or np.all(self._shift_data[ch] == 0)
            ):
                ch_list.append(ch)
        for ch in ch_list:
            if self.ui.add_shifts.isChecked():
                for i in range(1, len(self._shift_data[ch])):
                    self._shift_data[ch][i] += self._shift_data[ch][i - 1]
                    self._shift_data[ch][i] = round(self._shift_data[ch][i], 1)
            else:
                self._shift_data[ch] = [
                    round(s.assoc_shift[ch], 1) for s in self.seg_data
                ]
        for i, _s in enumerate(self.seg_data):
            self.ui.table.setItem(
                i, 2, CenteredQTableWidgetItem(str(self._shift_data[self._cur_ch][i]))
            )

    def _on_channel_changed(self, ch, active):
        if active:
            self._cur_ch = ch
            if self._model.get(ch):
                if self._model[ch] == "affinity":
                    self.ui.fit_affinity.setChecked(True)
                elif self._model[ch] == "linear":
                    self.ui.fit_linear.setChecked(True)
            self._load_channel_seg_data()
            self._draw_plot()
        else:  # Save current conc data
            self.conc_data[ch] = [
                float(self.ui.table.item(row, 1).text())
                for row in range(len(self.seg_data))
            ]

    def _load_channel_seg_data(self):
        self._clear_plot()
        table = self.ui.table
        table.horizontalHeaderItem(2).setText(
            f"Shift {self._cur_ch.upper()} ({self.units})"
        )
        table.horizontalHeaderItem(3).setText(f"Residual ({self.units})")
        table.setRowCount(0)
        table.setRowCount(len(self.seg_data))

        for i, s in enumerate(self.seg_data):
            table.setItem(i, 0, CenteredQTableWidgetItem(f"{s.name}"))
            table.setItem(
                i, 2, CenteredQTableWidgetItem(str(self._shift_data[self._cur_ch][i]))
            )
            item = CenteredQTableWidgetItem(str(self.conc_data[self._cur_ch][i]))
            item.setFlags(Qt.NoItemFlags)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            table.setItem(i, 1, item)
            self.ui.table.setItem(i, 3, CenteredQTableWidgetItem(""))
            for j in (0, 2, 3):  # Disable edit except conc value
                table.item(i, j).setFlags(Qt.ItemIsEnabled)
        self._fit_check()

    def _fit_check(self):
        if self.ui.fit_affinity.isChecked():
            k = "affinity"
            self.ui.affinity_result.setVisible(True)
            self.ui.linear_result.setVisible(False)
        else:
            k = "linear"
            self.ui.affinity_result.setVisible(False)
            self.ui.linear_result.setVisible(True)
        if self.ui.chk_fitting_curve.isChecked():
            self._fitted_plot.setPen(mkPen(GRAPH_COLORS[self._cur_ch], width=3))
            self._fitted_plot.setData(self.fitted_graph_data[k].get(self._cur_ch, []))
        else:
            self._fitted_plot.setData([])
        self.ui.graph.plotItem.vb.autoRange(padding=0.1)
        for i, sd in enumerate(self._sd_values.get(k, {}).get(self._cur_ch, [])):
            self.ui.table.item(i, 3).setText(str(round(sd, 3)))

    def _on_fit_check_changed(self):
        self._fit_check()
        if self._model.get(self._cur_ch):
            if self.ui.fit_affinity.isChecked():
                self._model[self._cur_ch] = "affinity"
            else:
                self._model[self._cur_ch] = "linear"

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
            logger.debug(f"Error while getting fitting conc data: {e}")
        self.closed.emit()
