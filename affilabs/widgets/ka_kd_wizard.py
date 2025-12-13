from copy import deepcopy
import csv
from functools import partial
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHeaderView, QDialog, QFileDialog

from settings import CH_LIST, DEV, GRAPH_COLORS
from pyqtgraph import mkPen, mkBrush
from ui.ui_ka_kd_wizard import Ui_KAKDWizardDialog
from affilabs.utils.logger import logger
from affilabs.utils.statistics import optimize_by_linear, optimize_assoc, optimize_rmax
from affilabs.utils.validator import NumericDelegate
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

        self.ui.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.ui.graph.getAxis('bottom').enableAutoSIPrefix(False)
        self.ui.graph.getAxis('left').enableAutoSIPrefix(False)
        self.ui.graph.plotItem.setTitle("Ks vs Concentration", color="w")
        self.ui.graph.setLabel(axis='bottom', text="Concentration")
        self.ui.graph.setLabel(axis='left', text="Ks")
        self.ui.graph.plotItem.showGrid(x=True, y=True, alpha=.3)
        if DEV:
            self.ui.graph.setMenuEnabled(True)
            self.ui.graph.setMouseEnabled(x=True, y=True)
        else:
            self.ui.graph.setMenuEnabled(False)
            self.ui.graph.setMouseEnabled(x=False, y=False)

        self._fitted_plot = self.ui.graph.plot(pen='r')
        self._conc_plot = self.ui.graph.plot(symbol='o')
        self._result = {ch: {} for ch in CH_LIST}       # Result
        self._cur_ch = 'a'
        self._assoc_shift_data = {ch: [round(s.assoc_shift[ch], 1) for s in self.seg_data] for ch in CH_LIST}
        self._dissoc_shift_data = {ch: [round(s.dissoc_shift[ch], 1) for s in self.seg_data] for ch in CH_LIST}
        self.conc_data = {ch: [s.conc[ch] for s in self.seg_data] for ch in CH_LIST}
        self.seg_names = {ch: [] for ch in CH_LIST}
        for ch in CH_LIST:
            getattr(self.ui, f"ch_{ch}").toggled.connect(partial(self._on_channel_changed, ch))
        self._load_channel_seg_data()
        self._on_btn_kd()

    def _on_btn_kd(self):
        try:
            ch = self._cur_ch
            self.conc_data[ch] = []
            no_data_flag = False
            for row, seg in enumerate(self.seg_data):
                seg.conc[ch] = float(self.ui.table.item(row, 1).text())
                self.conc_data[ch].append(float(self.ui.table.item(row, 1).text()))
                if np.all(seg.seg_y[ch] == 0) or np.all(seg.seg_y[ch] == np.nan):
                    no_data_flag = True
            c_list = np.array(self.conc_data[ch])
            if np.all(c_list == 0) or np.all(c_list == np.nan):
                show_message(msg="Please input concentration values!", msg_type="Warning")
            if no_data_flag:
                show_message(msg="No data on channel", msg_type="Warning")
            else:
                # Sort segments by concentration
                sorted_c_list = np.sort(c_list)
                sorted_segs = []
                for i in range(len(self.seg_data)):
                    for seg in self.seg_data:
                        if seg.conc[ch] == sorted_c_list[i]:
                            sorted_segs.append(deepcopy(seg))
                sorted_c_m = np.array(sorted_c_list * 1e-9)
                # Use dissociation data to determine initial kd
                kd_0 = []
                for seg in sorted_segs:
                    i = 0
                    while i < len(seg.d_seg_y[ch]):
                        if seg.d_seg_y[ch][i] <= 0:
                            break
                        i += 1
                    r_data = np.log(seg.d_seg_y[ch][0]/seg.d_seg_y[ch][0:i])
                    t_data = seg.d_seg_x[ch][0:i] - seg.d_seg_x[ch][0]
                    kd_0.append(float(optimize_by_linear(t_data, r_data)['a']))
                kd_0_pos = []
                for k in kd_0:
                    if k > 0:
                        kd_0_pos.append(k)
                for i in range(len(kd_0)):
                    kd_0_avg = np.nanmean(kd_0_pos)
                    if (kd_0[i] < 0) or (abs((kd_0[i] - kd_0_avg)/kd_0_avg) > 2):
                        kd_0[i] = np.nanmean(kd_0_pos)
                logger.debug(f"initial kd value: {kd_0}")
                # Use the association data to determine initial ka, Rmax
                ka_0 = []
                rmax_0 = []
                for i, seg in enumerate(sorted_segs):
                    dt_assoc = np.diff(seg.seg_y[ch])/np.diff(seg.seg_x[ch])
                    res = (optimize_by_linear(seg.seg_y[ch][1:], dt_assoc))
                    ks = -(float(res['a']))
                    b = float(res['b'])
                    ka_0.append(ks / sorted_c_m[i] + kd_0[i])
                    rmax_0.append(b / (sorted_c_m[i] * ka_0[i]))
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
                    res = optimize_assoc(seg.seg_x[ch], seg.seg_y[ch], sorted_c_m[i], kd_0[i], ka_0[i], rmax_0[i])
                    logger.debug(f"Seg {i}, refined ka, rmax{res}")
                    ka_0[i] = res['ka']
                    rmax_0[i] = res['rmax']
                # Use final local ks to find global ka, kd
                ks = []
                for i, seg in enumerate(sorted_segs):
                    ks.append((ka_0[i] * sorted_c_m[i]) + kd_0[i])
                logger.debug(f"local ks values {ks}")
                res = optimize_by_linear(sorted_c_m, ks)
                ka = res['a']
                kd = res['b']
                r_sq = res['r_sq']
                # Calculate the global Rmax using the equilibrium values
                req = []
                for seg in sorted_segs:
                    req.append(seg.seg_y[ch][-1])
                res = optimize_rmax(sorted_c_m, req, (kd/ka), rmax_0[-1])
                rmax = res['rmax']
                logger.debug(f"global Rmax: {rmax}")
                # Assign results to display
                self._result[ch]['kd'] = kd
                self._result[ch]['ka'] = ka
                self._result[ch]['KD'] = kd/ka
                self._result[ch]['Rmax'] = rmax
                self._result[ch]['r_sq'] = r_sq
                self._result[ch]['ks'] = ks
                self._result[ch]['c'] = sorted_c_m
                self._draw_plot()
                self.ui.btn_save.setEnabled(True)
        except Exception as e:
            logger.debug(f"Failed to calculate ka/kd: {e}")
            show_message(msg=f"Calculation Error", msg_type="Error")

    def _on_btn_save(self):
        try:
            export_file = QFileDialog.getSaveFileName(self, "Choose directory and filename for KD export", "")[0]
            if export_file:
                for ch in CH_LIST:
                    if self._result[ch]:
                        with open(file=f"{export_file}.txt", mode='w', newline='', encoding='utf-8') as txtfile:
                            fieldnames = ['Seg ID', f'Conc_{ch.upper()}',
                                          f'Assoc_Shift_{ch.upper()}', f'Dissoc_Shift_{ch.upper()}']
                            writer = csv.DictWriter(txtfile, dialect='excel-tab', fieldnames=fieldnames)
                            writer.writeheader()
                            for i, seg in enumerate(self.seg_data):
                                data = {'Seg ID': f'{seg.name}',
                                        f'Assoc_Shift_{ch.upper()}': seg.assoc_shift[ch],
                                        f'Dissoc_Shift_{ch.upper()}': seg.dissoc_shift[ch],
                                        f'Conc_{ch.upper()}': self.conc_data[ch][i]}
                                writer.writerow(data)
                            result_strings = [
                                f"KD: {self._result[ch]['KD']:.2e}",
                                f"Rmax: {self._result[ch]['Rmax']:.2f}",
                                f"R Squared: {self._result[ch]['r_sq']:.2f}",
                                f"ka: {self._result[ch]['ka']:.2e}",
                                f"kd: {self._result[ch]['kd']:.2e}",
                            ]
                            for r in result_strings:
                                txtfile.writelines(r + '\n')
                show_message(msg="Kinetic data exported")
        except Exception as e:
            logger.debug(f"Error during KD export: {e}")
            show_message(msg="KD export error", msg_type='Warning')

    def _draw_plot(self):
        ch = self._cur_ch
        if self._result[ch]:
            x_data = np.array(self._result[ch]['c'])
            y_data = np.array(self._result[ch]['ks'])
            self._conc_plot.setSymbolBrush(mkBrush(GRAPH_COLORS[self._cur_ch]))
            self._conc_plot.setData(x=x_data, y=y_data)
            fitted = [(self._result[ch]['ka']*x) + self._result[ch]['kd'] for x in x_data]
            self._fitted_plot.setPen(mkPen(GRAPH_COLORS[self._cur_ch], width=3))
            self._fitted_plot.setData(x=x_data, y=fitted)
            self.ui.graph.plotItem.vb.autoRange(padding=.1)
            for k in {'KD', 'ka', 'kd'}:
                getattr(self.ui, f"lb_{k}").setText(f"{self._result[ch][k]:.2e}")
            for k in {'Rmax', 'r_sq'}:
                getattr(self.ui, f"lb_{k}").setText(f"{self._result[ch][k]:.2f}")
        else:
            for k in {'KD', 'Rmax', 'r_sq', 'ka', 'kd'}:
                getattr(self.ui, f"lb_{k}").setText("")
            self._fitted_plot.setData([])
            self._conc_plot.setData([])

    def _on_channel_changed(self, ch, active):
        if active:
            self._cur_ch = ch
            self._load_channel_seg_data()
        else:  # Save current conc data
            self.conc_data[ch] = [float(self.ui.table.item(row, 2).text()) for row in range(len(self.seg_data))]

    def _load_channel_seg_data(self):
        table = self.ui.table
        table.horizontalHeaderItem(2).setText(f"Association\nShift ({self.units})")
        table.horizontalHeaderItem(3).setText(f"Dissociation\nShift ({self.units})")
        table.setRowCount(0)
        table.setRowCount(len(self.seg_data))

        for i, s in enumerate(self.seg_data):
            table.setItem(i, 0, CenteredQTableWidgetItem(f"{s.name}"))
            table.setItem(i, 2, CenteredQTableWidgetItem(str(self._assoc_shift_data[self._cur_ch][i])))
            table.setItem(i, 3, CenteredQTableWidgetItem(str(self._dissoc_shift_data[self._cur_ch][i])))
            item = CenteredQTableWidgetItem(str(self.conc_data[self._cur_ch][i]))
            item.setFlags(Qt.NoItemFlags)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)
            table.setItem(i, 1, item)
            for j in {0, 2, 3}:     # Disable edit except conc value
                table.item(i, j).setFlags(Qt.ItemIsEnabled)
        self._draw_plot()

    def closeEvent(self, arg__1):
        try:
            self.conc_data[self._cur_ch] = [float(self.ui.table.item(row, 1).text())
                                            for row in range(len(self.seg_data))]
            self.seg_names[self._cur_ch] = [(self.ui.table.item(row, 0).text()) for row in range(len(self.seg_data))]
        except Exception as e:
            logger.debug(f"Error while getting kinetic conc data: {e}")
        getattr(self, 'closed').emit()
