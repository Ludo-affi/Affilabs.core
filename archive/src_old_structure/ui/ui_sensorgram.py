# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sensorgram.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
    QGraphicsView, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget)
from . import ai_rc
from .styles import apply_channel_checkbox_style, get_groupbox_title_font

class Ui_Sensorgram(object):
    def setupUi(self, Sensorgram):
        if not Sensorgram.objectName():
            Sensorgram.setObjectName(u"Sensorgram")
        Sensorgram.resize(978, 696)
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        font.setPointSize(9)
        Sensorgram.setFont(font)
        Sensorgram.setMouseTracking(True)
        Sensorgram.setFocusPolicy(Qt.StrongFocus)
        self.horizontalLayout = QHBoxLayout(Sensorgram)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.displays = QVBoxLayout()
        self.displays.setSpacing(0)
        self.displays.setObjectName(u"displays")
        self.displays.setContentsMargins(11, 11, 11, 11)
        # Display groupBox moved to Graphic Control sidebar tab
        # Channel checkboxes A, B, C, D are now in sidebar
        from ui.styles import get_groupbox_style, get_groupbox_title_font, Colors
        self.groupBox = QGroupBox(Sensorgram)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setMinimumHeight(55)
        self.groupBox.setMaximumHeight(55)
        # Ensure it stays embedded in layout
        self.groupBox.setWindowFlags(Qt.Widget)  # Not a separate window
        self.groupBox.setStyleSheet(get_groupbox_style(Colors.SURFACE))
        self.groupBox.setTitle("Display")
        font_groupbox = get_groupbox_title_font()
        self.groupBox.setFont(font_groupbox)
        self.horizontalLayout_12 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.segment_A = QCheckBox(self.groupBox)
        self.segment_A.setObjectName(u"segment_A")
        apply_channel_checkbox_style(self.segment_A, 'A')
        self.segment_A.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_A)

        self.segment_B = QCheckBox(self.groupBox)
        self.segment_B.setObjectName(u"segment_B")
        apply_channel_checkbox_style(self.segment_B, 'B')
        self.segment_B.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_B)

        self.segment_C = QCheckBox(self.groupBox)
        self.segment_C.setObjectName(u"segment_C")
        apply_channel_checkbox_style(self.segment_C, 'C')
        self.segment_C.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_C)

        self.segment_D = QCheckBox(self.groupBox)
        self.segment_D.setObjectName(u"segment_D")
        apply_channel_checkbox_style(self.segment_D, 'D')
        self.segment_D.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_D)

        # groupBox NOT added to displays layout - will be moved to sidebar
        # self.displays.addWidget(self.groupBox)

        # shift_display_box removed - status messages now in Flow tab sidebar

        self.horizontalLayout_sensor_header = QHBoxLayout()
        self.horizontalLayout_sensor_header.setSpacing(8)
        self.horizontalLayout_sensor_header.setObjectName(u"horizontalLayout_sensor_header")
        self.horizontalLayout_sensor_header.setContentsMargins(0, 0, 0, 0)
        self.shift_display_box = QLabel(Sensorgram)
        self.shift_display_box.setObjectName(u"shift_display_box")
        self.shift_display_box.setMinimumSize(QSize(200, 40))
        self.shift_display_box.setMaximumSize(QSize(400, 40))
        self.shift_display_box.setStyleSheet(u"QLabel {\n"
"	background-color: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 4px;\n"
"	padding: 5px;\n"
"	font-family: Segoe UI;\n"
"	font-size: 9pt;\n"
"}")
        self.shift_display_box.setAlignment(Qt.AlignVCenter|Qt.AlignLeft)

        self.horizontalLayout_sensor_header.addWidget(self.shift_display_box)

        self.clear_graph_btn = QPushButton(Sensorgram)
        self.clear_graph_btn.setObjectName(u"clear_graph_btn")
        self.clear_graph_btn.setMinimumSize(QSize(20, 40))
        self.clear_graph_btn.setMaximumSize(QSize(20, 40))
        self.clear_graph_btn.setVisible(False)  # Hidden - now in sidebar

        self.horizontalLayout_sensor_header.addWidget(self.clear_graph_btn)

        self.adjust_margins_btn = QPushButton(Sensorgram)
        self.adjust_margins_btn.setObjectName(u"adjust_margins_btn")
        self.adjust_margins_btn.setMinimumSize(QSize(100, 40))
        self.adjust_margins_btn.setMaximumSize(QSize(120, 40))
        self.adjust_margins_btn.setStyleSheet(u"QPushButton {\n"
"    background-color: rgb(240, 240, 240);\n"
"    border: 1px solid rgb(171, 171, 171);\n"
"    border-radius: 3px;\n"
"    font-size: 8pt;\n"
"}\n"
"QPushButton:hover {\n"
"    background-color: rgb(253, 253, 253);\n"
"    border: 1px solid rgb(46, 48, 227);\n"
"}")
        self.adjust_margins_btn.setText(u"Adjust Margins")

        self.horizontalLayout_sensor_header.addWidget(self.adjust_margins_btn)

        self.horizontalSpacer_header = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_sensor_header.addItem(self.horizontalSpacer_header)

        self.horizontalLayout_sensor_header.setStretch(0, 1)

        self.displays.addLayout(self.horizontalLayout_sensor_header)

        self.full_segment = QFrame(Sensorgram)
        self.full_segment.setObjectName(u"full_segment")
        self.full_segment.setMinimumSize(QSize(180, 225))
        self.full_segment.setMaximumSize(QSize(10000, 10000))
        self.full_segment.setMouseTracking(True)
        self.full_segment.setFrameShape(QFrame.StyledPanel)
        self.full_segment.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.full_segment)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_4)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.horizontalLayout_3.addItem(self.verticalSpacer)


        self.displays.addWidget(self.full_segment)

        self.SOI = QFrame(Sensorgram)
        self.SOI.setObjectName(u"SOI")
        self.SOI.setMinimumSize(QSize(180, 225))
        self.SOI.setMaximumSize(QSize(10000, 10000))
        self.SOI.setFrameShape(QFrame.StyledPanel)
        self.SOI.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.SOI)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_5)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.horizontalLayout_4.addItem(self.verticalSpacer_2)


        self.displays.addWidget(self.SOI)


        self.horizontalLayout.addLayout(self.displays)

        self.controls_container = QWidget(Sensorgram)
        self.controls_container.setObjectName(u"controls_container")
        self.controls = QVBoxLayout(self.controls_container)
        self.controls.setObjectName(u"controls")
        # Standard font for groupbox titles
        font_groupbox = get_groupbox_title_font()
        self.groupBox_display_right = QGroupBox(self.controls_container)
        self.groupBox_display_right.setObjectName(u"groupBox_display_right")
        self.groupBox_display_right.setFont(font_groupbox)
        self.groupBox_display_right.setStyleSheet(get_groupbox_style(Colors.SURFACE))
        self.verticalLayout_display = QVBoxLayout(self.groupBox_display_right)
        self.verticalLayout_display.setObjectName(u"verticalLayout_display")
        self.segment_A_right = QCheckBox(self.groupBox_display_right)
        self.segment_A_right.setObjectName(u"segment_A_right")
        apply_channel_checkbox_style(self.segment_A_right, 'A')
        self.segment_A_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_A_right)

        self.segment_B_right = QCheckBox(self.groupBox_display_right)
        self.segment_B_right.setObjectName(u"segment_B_right")
        apply_channel_checkbox_style(self.segment_B_right, 'B')
        self.segment_B_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_B_right)

        self.segment_C_right = QCheckBox(self.groupBox_display_right)
        self.segment_C_right.setObjectName(u"segment_C_right")
        apply_channel_checkbox_style(self.segment_C_right, 'C')
        self.segment_C_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_C_right)

        self.segment_D_right = QCheckBox(self.groupBox_display_right)
        self.segment_D_right.setObjectName(u"segment_D_right")
        apply_channel_checkbox_style(self.segment_D_right, 'D')
        self.segment_D_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_D_right)


        self.controls.addWidget(self.groupBox_display_right)

        # Hidden cursor controls (still needed by code but not displayed)
        self.left_cursor_time = QLineEdit(self.controls_container)
        self.left_cursor_time.setObjectName(u"left_cursor_time")
        self.left_cursor_time.setVisible(False)

        self.right_cursor_time = QLineEdit(self.controls_container)
        self.right_cursor_time.setObjectName(u"right_cursor_time")
        self.right_cursor_time.setVisible(False)

        self.live_btn = QCheckBox(self.controls_container)
        self.live_btn.setObjectName(u"live_btn")
        self.live_btn.setVisible(False)
        self.live_btn.setChecked(True)

        # Now verticalLayout is directly in controls

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")

        # Loop Diagram Container (styled like Hardware Status)
        self.loop_container = QFrame(self.controls_container)
        self.loop_container.setObjectName(u"loop_container")
        self.loop_container.setStyleSheet(u"QFrame#loop_container {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(180, 180, 180);\n"
            "    border-radius: 8px;\n"
            "}")
        self.loop_container.setFrameShape(QFrame.StyledPanel)
        self.loop_container.setFrameShadow(QFrame.Raised)

        self.loop_container_layout = QVBoxLayout(self.loop_container)
        self.loop_container_layout.setSpacing(8)
        self.loop_container_layout.setContentsMargins(12, 12, 12, 12)

        # Loop Diagram Title
        self.loop_title = QLabel(self.loop_container)
        self.loop_title.setObjectName(u"loop_title")
        loop_title_font = QFont()
        loop_title_font.setPointSize(10)
        loop_title_font.setBold(True)
        self.loop_title.setFont(loop_title_font)
        self.loop_title.setText("Loop Diagram")
        self.loop_title.setStyleSheet(u"color: rgb(80, 80, 80); padding-bottom: 4px;")
        self.loop_container_layout.addWidget(self.loop_title)

        # Loop diagram with responsive container
        self.loop_diagram_container = QFrame(self.loop_container)
        self.loop_diagram_container.setObjectName(u"loop_diagram_container")
        self.loop_diagram_container.setStyleSheet(u"QFrame#loop_diagram_container {\n"
            "    background-color: transparent;\n"
            "    border: none;\n"
            "}")
        self.loop_diagram_container_layout = QVBoxLayout(self.loop_diagram_container)
        self.loop_diagram_container_layout.setContentsMargins(0, 0, 0, 0)
        self.loop_diagram_container_layout.setSpacing(4)

        self.loop_diagram = QGraphicsView(self.loop_diagram_container)
        self.loop_diagram.setObjectName(u"loop_diagram")
        self.loop_diagram.setMinimumSize(QSize(200, 100))
        self.loop_diagram.setMaximumSize(QSize(16777215, 150))
        sizePolicy_diagram = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy_diagram.setHorizontalStretch(0)
        sizePolicy_diagram.setVerticalStretch(0)
        self.loop_diagram.setSizePolicy(sizePolicy_diagram)
        self.loop_diagram.setStyleSheet(u"background:transparent; border: none;")
        self.loop_diagram.setFrameShape(QFrame.NoFrame)
        self.loop_diagram.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.loop_diagram.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.loop_diagram.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.loop_diagram_container_layout.addWidget(self.loop_diagram, 0, Qt.AlignTop)

        # Progress bar for injection timing
        self.progress_bar = QProgressBar(self.loop_diagram_container)
        self.progress_bar.setObjectName(u"progress_bar")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(u"QProgressBar {\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 3px;\n"
            "    background-color: rgb(240, 240, 240);\n"
            "}\n"
            "QProgressBar::chunk {\n"
            "    background-color: rgb(46, 48, 227);\n"
            "    border-radius: 2px;\n"
            "}")
        self.loop_diagram_container_layout.addWidget(self.progress_bar, 0, Qt.AlignTop)

        self.loop_container_layout.addWidget(self.loop_diagram_container, 0, Qt.AlignTop)

        # Old flow_rate_section removed - replaced by pump_flowrate_frame below

        # Pump Flowrate Section
        self.pump_flowrate_frame = QFrame(self.loop_container)
        self.pump_flowrate_frame.setObjectName(u"pump_flowrate_frame")
        self.pump_flowrate_frame.setStyleSheet(u"QFrame#pump_flowrate_frame {\n"
            "    background-color: rgb(250, 250, 250);\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 6px;\n"
            "    margin-top: 8px;\n"
            "}")
        self.pump_flowrate_layout = QVBoxLayout(self.pump_flowrate_frame)
        self.pump_flowrate_layout.setContentsMargins(8, 8, 8, 8)
        self.pump_flowrate_layout.setSpacing(4)

        # Pump Flowrate Title
        self.pump_flowrate_title = QLabel(self.pump_flowrate_frame)
        self.pump_flowrate_title.setObjectName(u"pump_flowrate_title")
        pump_title_font = QFont()
        pump_title_font.setPointSize(9)
        pump_title_font.setBold(True)
        self.pump_flowrate_title.setFont(pump_title_font)
        self.pump_flowrate_title.setText("Pump Flowrate")
        self.pump_flowrate_title.setStyleSheet(u"color: rgb(80, 80, 80); background: transparent; border: none;")
        self.pump_flowrate_layout.addWidget(self.pump_flowrate_title)

        # Current flowrate display
        self.pump_current_layout = QHBoxLayout()
        self.pump_current_layout.setSpacing(6)

        self.pump_current_label = QLabel(self.pump_flowrate_frame)
        self.pump_current_label.setObjectName(u"pump_current_label")
        self.pump_current_label.setText("Current:")
        self.pump_current_label.setMinimumWidth(50)
        self.pump_current_label.setStyleSheet(u"color: rgb(80, 80, 80); font-weight: normal;")
        self.pump_current_layout.addWidget(self.pump_current_label)

        self.pump_current_value = QLabel(self.pump_flowrate_frame)
        self.pump_current_value.setObjectName(u"pump_current_value")
        self.pump_current_value.setText("0.0")
        self.pump_current_value.setMinimumWidth(60)
        sizePolicy_pump = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy_pump.setHorizontalStretch(0)
        sizePolicy_pump.setVerticalStretch(0)
        self.pump_current_value.setSizePolicy(sizePolicy_pump)
        self.pump_current_value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.pump_current_value.setStyleSheet(u"QLabel {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 3px;\n"
            "    padding: 4px 8px;\n"
            "    color: rgb(46, 48, 227);\n"
            "    font-weight: 600;\n"
            "}")
        self.pump_current_layout.addWidget(self.pump_current_value)

        self.pump_current_unit = QLabel(self.pump_flowrate_frame)
        self.pump_current_unit.setObjectName(u"pump_current_unit")
        self.pump_current_unit.setText("μL/min")
        self.pump_current_unit.setMinimumWidth(45)
        self.pump_current_unit.setStyleSheet(u"color: rgb(80, 80, 80); font-weight: normal;")
        self.pump_current_layout.addWidget(self.pump_current_unit)

        self.pump_flowrate_layout.addLayout(self.pump_current_layout)

        # Set flowrate
        self.pump_set_layout = QHBoxLayout()
        self.pump_set_layout.setSpacing(6)

        self.pump_set_label = QLabel(self.pump_flowrate_frame)
        self.pump_set_label.setObjectName(u"pump_set_label")
        self.pump_set_label.setText("Set:")
        self.pump_set_label.setMinimumWidth(50)
        self.pump_set_label.setStyleSheet(u"color: rgb(80, 80, 80); font-weight: normal;")
        self.pump_set_layout.addWidget(self.pump_set_label)

        self.pump_set_value = QLineEdit(self.pump_flowrate_frame)
        self.pump_set_value.setObjectName(u"pump_set_value")
        self.pump_set_value.setMinimumWidth(60)
        sizePolicy_pump_input = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy_pump_input.setHorizontalStretch(0)
        sizePolicy_pump_input.setVerticalStretch(0)
        self.pump_set_value.setSizePolicy(sizePolicy_pump_input)
        self.pump_set_value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.pump_set_value.setText("100")
        self.pump_set_value.setStyleSheet(u"QLineEdit {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 3px;\n"
            "    padding: 4px 8px;\n"
            "}\n"
            "QLineEdit:focus {\n"
            "    border: 2px solid rgb(46, 48, 227);\n"
            "}")
        self.pump_set_layout.addWidget(self.pump_set_value)

        self.pump_set_unit = QLabel(self.pump_flowrate_frame)
        self.pump_set_unit.setObjectName(u"pump_set_unit")
        self.pump_set_unit.setText("μL/min")
        self.pump_set_unit.setMinimumWidth(45)
        self.pump_set_unit.setStyleSheet(u"color: rgb(80, 80, 80); font-weight: normal;")
        self.pump_set_layout.addWidget(self.pump_set_unit)

        self.pump_flowrate_layout.addLayout(self.pump_set_layout)

        # Cycle progress
        self.pump_cycle_layout = QHBoxLayout()
        self.pump_cycle_layout.setSpacing(6)

        self.pump_cycle_label = QLabel(self.pump_flowrate_frame)
        self.pump_cycle_label.setObjectName(u"pump_cycle_label")
        self.pump_cycle_label.setText("Cycles:")
        self.pump_cycle_label.setMinimumWidth(50)
        self.pump_cycle_label.setStyleSheet(u"color: rgb(80, 80, 80); font-weight: normal;")
        self.pump_cycle_layout.addWidget(self.pump_cycle_label)

        self.pump_cycle_progress = QLabel(self.pump_flowrate_frame)
        self.pump_cycle_progress.setObjectName(u"pump_cycle_progress")
        self.pump_cycle_progress.setText("0 / 0")
        self.pump_cycle_progress.setMinimumWidth(60)
        sizePolicy_cycle = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy_cycle.setHorizontalStretch(0)
        sizePolicy_cycle.setVerticalStretch(0)
        self.pump_cycle_progress.setSizePolicy(sizePolicy_cycle)
        self.pump_cycle_progress.setAlignment(Qt.AlignCenter)
        self.pump_cycle_progress.setStyleSheet(u"QLabel {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 3px;\n"
            "    padding: 4px 8px;\n"
            "    color: rgb(60, 60, 60);\n"
            "    font-weight: 600;\n"
            "}")
        self.pump_cycle_layout.addWidget(self.pump_cycle_progress)

        self.pump_cycle_set = QLineEdit(self.pump_flowrate_frame)
        self.pump_cycle_set.setObjectName(u"pump_cycle_set")
        self.pump_cycle_set.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.pump_cycle_set.setText("1")
        self.pump_cycle_set.setMaximumWidth(50)
        self.pump_cycle_set.setStyleSheet(u"QLineEdit {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 3px;\n"
            "    padding: 4px 8px;\n"
            "}\n"
            "QLineEdit:focus {\n"
            "    border: 2px solid rgb(46, 48, 227);\n"
            "}")
        self.pump_cycle_layout.addWidget(self.pump_cycle_set)

        self.pump_flowrate_layout.addLayout(self.pump_cycle_layout)

        # Pump control buttons
        self.pump_buttons_layout = QHBoxLayout()
        self.pump_buttons_layout.setSpacing(6)

        # Compact button style
        compact_button_style = u"QPushButton {\n"\
            "    background-color: rgb(240, 240, 240);\n"\
            "    color: rgb(60, 60, 60);\n"\
            "    border: 1px solid rgb(200, 200, 200);\n"\
            "    border-radius: 4px;\n"\
            "    font-weight: 600;\n"\
            "    padding: 4px 8px;\n"\
            "}\n"\
            "QPushButton:hover {\n"\
            "    background-color: rgb(230, 230, 230);\n"\
            "    border: 1px solid rgb(180, 180, 180);\n"\
            "}\n"\
            "QPushButton:pressed {\n"\
            "    background-color: rgb(210, 210, 210);\n"\
            "}\n"\
            "QPushButton:disabled {\n"\
            "    background-color: rgb(245, 245, 245);\n"\
            "    color: rgb(180, 180, 180);\n"\
            "    border: 1px solid rgb(220, 220, 220);\n"\
            "}"

        self.pump_stop_button = QPushButton(self.pump_flowrate_frame)
        self.pump_stop_button.setObjectName(u"pump_stop_button")
        self.pump_stop_button.setText("Stop")
        self.pump_stop_button.setMinimumHeight(28)
        self.pump_stop_button.setMinimumWidth(50)
        sizePolicy_btn = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        sizePolicy_btn.setHorizontalStretch(0)
        sizePolicy_btn.setVerticalStretch(0)
        self.pump_stop_button.setSizePolicy(sizePolicy_btn)
        self.pump_stop_button.setStyleSheet(compact_button_style)
        self.pump_buttons_layout.addWidget(self.pump_stop_button)

        self.pump_refill_button = QPushButton(self.pump_flowrate_frame)
        self.pump_refill_button.setObjectName(u"pump_refill_button")
        self.pump_refill_button.setText("Refill")
        self.pump_refill_button.setMinimumHeight(28)
        self.pump_refill_button.setMinimumWidth(50)
        self.pump_refill_button.setSizePolicy(sizePolicy_btn)
        self.pump_refill_button.setStyleSheet(compact_button_style)
        self.pump_buttons_layout.addWidget(self.pump_refill_button)

        self.pump_flowrate_layout.addLayout(self.pump_buttons_layout)

        self.loop_container_layout.addWidget(self.pump_flowrate_frame)

        # Preset Functions Section with light gray buttons
        self.preset_functions_frame = QFrame(self.loop_container)
        self.preset_functions_frame.setObjectName(u"preset_functions_frame")
        self.preset_functions_frame.setStyleSheet(u"QFrame#preset_functions_frame {\n"
            "    background-color: rgb(250, 250, 250);\n"
            "    border: 1px solid rgb(200, 200, 200);\n"
            "    border-radius: 6px;\n"
            "    margin-top: 8px;\n"
            "}")
        self.preset_functions_layout = QVBoxLayout(self.preset_functions_frame)
        self.preset_functions_layout.setContentsMargins(8, 8, 8, 8)
        self.preset_functions_layout.setSpacing(6)

        # Preset Functions Title
        self.preset_title = QLabel(self.preset_functions_frame)
        self.preset_title.setObjectName(u"preset_title")
        preset_title_font = QFont()
        preset_title_font.setPointSize(9)
        preset_title_font.setBold(True)
        self.preset_title.setFont(preset_title_font)
        self.preset_title.setText("Preset Functions")
        self.preset_title.setStyleSheet(u"color: rgb(80, 80, 80); background: transparent; border: none;")
        self.preset_functions_layout.addWidget(self.preset_title)

        # Single row with all preset buttons
        self.preset_buttons_layout = QHBoxLayout()
        self.preset_buttons_layout.setSpacing(6)

        # Light gray button style
        light_gray_style = u"QPushButton {\n"\
            "    background-color: rgb(240, 240, 240);\n"\
            "    color: rgb(60, 60, 60);\n"\
            "    border: 1px solid rgb(200, 200, 200);\n"\
            "    border-radius: 4px;\n"\
            "    font-weight: 600;\n"\
            "    padding: 6px 12px;\n"\
            "}\n"\
            "QPushButton:hover {\n"\
            "    background-color: rgb(230, 230, 230);\n"\
            "    border: 1px solid rgb(180, 180, 180);\n"\
            "}\n"\
            "QPushButton:pressed {\n"\
            "    background-color: rgb(210, 210, 210);\n"\
            "}\n"\
            "QPushButton:disabled {\n"\
            "    background-color: rgb(245, 245, 245);\n"\
            "    color: rgb(180, 180, 180);\n"\
            "    border: 1px solid rgb(220, 220, 220);\n"\
            "}"

        # Inject button (renamed for wiring)
        self.inject_button = QPushButton(self.preset_functions_frame)
        self.inject_button.setObjectName(u"inject_button")
        self.inject_button.setText("Inject")
        self.inject_button.setMinimumHeight(28)
        self.inject_button.setStyleSheet(light_gray_style)
        self.preset_buttons_layout.addWidget(self.inject_button)

        # Regen button (renamed for wiring)
        self.regen_button = QPushButton(self.preset_functions_frame)
        self.regen_button.setObjectName(u"regen_button")
        self.regen_button.setText("Regen")
        self.regen_button.setMinimumHeight(28)
        self.regen_button.setStyleSheet(light_gray_style)
        self.preset_buttons_layout.addWidget(self.regen_button)

        # Flush button (renamed for wiring)
        self.flush_button = QPushButton(self.preset_functions_frame)
        self.flush_button.setObjectName(u"flush_button")
        self.flush_button.setText("Flush")
        self.flush_button.setMinimumHeight(28)
        self.flush_button.setStyleSheet(light_gray_style)
        self.preset_buttons_layout.addWidget(self.flush_button)

        # Prime button (renamed for wiring)
        self.prime_button = QPushButton(self.preset_functions_frame)
        self.prime_button.setObjectName(u"prime_button")
        self.prime_button.setText("Prime")
        self.prime_button.setMinimumHeight(28)
        self.prime_button.setStyleSheet(light_gray_style)
        self.preset_buttons_layout.addWidget(self.prime_button)

        self.preset_functions_layout.addLayout(self.preset_buttons_layout)

        self.loop_container_layout.addWidget(self.preset_functions_frame)

        self.verticalLayout.addWidget(self.loop_container)

        self.verticalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)

        # Hidden widgets still needed by code
        self.flow_rate = QLineEdit(self.controls_container)
        self.flow_rate.setObjectName(u"flow_rate")
        self.flow_rate.setVisible(False)

        self.flow_rate_now = QLabel(self.controls_container)
        self.flow_rate_now.setObjectName(u"flow_rate_now")
        self.flow_rate_now.setVisible(False)

        # Cycle Settings Container (styled like Hardware Status)
        self.groupBox_4 = QFrame(self.controls_container)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.groupBox_4.setStyleSheet(u"QFrame#groupBox_4 {\n"
            "    background-color: white;\n"
            "    border: 1px solid rgb(180, 180, 180);\n"
            "    border-radius: 8px;\n"
            "}")
        self.groupBox_4.setFrameShape(QFrame.StyledPanel)
        self.groupBox_4.setFrameShadow(QFrame.Raised)

        self.verticalLayout_3 = QVBoxLayout(self.groupBox_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(12, 12, 12, 12)
        self.verticalLayout_3.setSpacing(8)

        # Cycle Settings Title
        self.cycle_title = QLabel(self.groupBox_4)
        self.cycle_title.setObjectName(u"cycle_title")
        cycle_title_font = QFont()
        cycle_title_font.setPointSize(10)
        cycle_title_font.setBold(True)
        self.cycle_title.setFont(cycle_title_font)
        self.cycle_title.setText("Cycle Settings")
        self.cycle_title.setStyleSheet(u"color: rgb(80, 80, 80); padding-bottom: 4px;")
        self.verticalLayout_3.addWidget(self.cycle_title)
        self.horizontalLayout_exp_time = QHBoxLayout()
        self.horizontalLayout_exp_time.setObjectName(u"horizontalLayout_exp_time")
        self.label_exp_time = QLabel(self.groupBox_4)
        self.label_exp_time.setObjectName(u"label_exp_time")
        self.label_exp_time.setVisible(False)

        self.horizontalLayout_exp_time.addWidget(self.label_exp_time)

        self.exp_clock_settings = QLabel(self.groupBox_4)
        self.exp_clock_settings.setObjectName(u"exp_clock_settings")
        self.exp_clock_settings.setVisible(False)

        self.horizontalLayout_exp_time.addWidget(self.exp_clock_settings)


        self.verticalLayout_3.addLayout(self.horizontalLayout_exp_time)

        self.horizontalLayout_cycle_type = QHBoxLayout()
        self.horizontalLayout_cycle_type.setObjectName(u"horizontalLayout_cycle_type")
        self.label_cycle_type = QLabel(self.groupBox_4)
        self.label_cycle_type.setObjectName(u"label_cycle_type")

        self.horizontalLayout_cycle_type.addWidget(self.label_cycle_type)

        self.current_cycle_type = QComboBox(self.groupBox_4)
        self.current_cycle_type.addItem("")
        self.current_cycle_type.addItem("")
        self.current_cycle_type.addItem("")
        self.current_cycle_type.addItem("")
        self.current_cycle_type.setObjectName(u"current_cycle_type")
        self.current_cycle_type.setEditable(False)

        self.horizontalLayout_cycle_type.addWidget(self.current_cycle_type)


        self.verticalLayout_3.addLayout(self.horizontalLayout_cycle_type)

        self.horizontalLayout_cycle_duration = QHBoxLayout()
        self.horizontalLayout_cycle_duration.setObjectName(u"horizontalLayout_cycle_duration")
        self.label_cycle_duration = QLabel(self.groupBox_4)
        self.label_cycle_duration.setObjectName(u"label_cycle_duration")

        self.horizontalLayout_cycle_duration.addWidget(self.label_cycle_duration)

        self.current_cycle_duration = QComboBox(self.groupBox_4)
        self.current_cycle_duration.addItem("")
        self.current_cycle_duration.addItem("")
        self.current_cycle_duration.addItem("")
        self.current_cycle_duration.addItem("")
        self.current_cycle_duration.addItem("")
        self.current_cycle_duration.setObjectName(u"current_cycle_duration")
        self.current_cycle_duration.setEditable(False)

        self.horizontalLayout_cycle_duration.addWidget(self.current_cycle_duration)

        self.verticalLayout_3.addLayout(self.horizontalLayout_cycle_duration)

        self.horizontalLayout_cycle_buttons = QHBoxLayout()
        self.horizontalLayout_cycle_buttons.setObjectName(u"horizontalLayout_cycle_buttons")
        self.save_segment_btn = QPushButton(self.groupBox_4)
        self.save_segment_btn.setObjectName(u"save_segment_btn")

        self.horizontalLayout_cycle_buttons.addWidget(self.save_segment_btn)

        self.new_segment_btn = QPushButton(self.groupBox_4)
        self.new_segment_btn.setObjectName(u"new_segment_btn")

        self.horizontalLayout_cycle_buttons.addWidget(self.new_segment_btn)


        self.verticalLayout_3.addLayout(self.horizontalLayout_cycle_buttons)


        self.verticalLayout.addWidget(self.groupBox_4)

        # Cycle Data Table button at bottom
        self.cycle_data_table_btn = QPushButton(self.controls_container)
        self.cycle_data_table_btn.setObjectName(u"cycle_data_table_btn")
        self.cycle_data_table_btn.setText("Cycle Data Table")
        self.cycle_data_table_btn.setMinimumSize(QSize(0, 35))
        self.cycle_data_table_btn.setStyleSheet(u"QPushButton {\n"
            "    background-color: rgb(46, 48, 227);\n"
            "    color: white;\n"
            "    border: 1px solid rgb(46, 48, 227);\n"
            "    border-radius: 4px;\n"
            "    font-weight: bold;\n"
            "    padding: 8px;\n"
            "}\n"
            "QPushButton:hover {\n"
            "    background-color: rgb(66, 68, 247);\n"
            "}\n"
            "QPushButton:pressed {\n"
            "    background-color: rgb(26, 28, 207);\n"
            "}")

        self.verticalLayout.addWidget(self.cycle_data_table_btn)

        # Add verticalLayout directly to controls (no more horizontalLayout_5)
        self.controls.addLayout(self.verticalLayout)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.horizontalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_3)

        self.reset_segment_btn = QPushButton(self.controls_container)
        self.reset_segment_btn.setObjectName(u"reset_segment_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.reset_segment_btn.sizePolicy().hasHeightForWidth())
        self.reset_segment_btn.setSizePolicy(sizePolicy1)
        self.reset_segment_btn.setMinimumSize(QSize(30, 30))
        self.reset_segment_btn.setMaximumSize(QSize(30, 30))
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(5)
        self.reset_segment_btn.setFont(font2)
        self.reset_segment_btn.setMouseTracking(True)
        self.reset_segment_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 10px;\n"
"}")
        icon = QIcon()
        icon.addFile(u":/img/img/reload.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.reset_segment_btn.setIcon(icon)
        self.reset_segment_btn.setIconSize(QSize(25, 25))

        self.horizontalLayout_13.addWidget(self.reset_segment_btn)

        self.horizontalSpacer = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer)

        self.horizontalLayout_13.setStretch(0, 4)
        self.horizontalLayout_13.setStretch(1, 1)
        self.horizontalLayout_13.setStretch(2, 4)

        self.controls.addLayout(self.horizontalLayout_13)

        self.horizontalLayout_table_btn = QHBoxLayout()
        self.horizontalLayout_table_btn.setObjectName(u"horizontalLayout_table_btn")
        self.horizontalSpacer_table_left = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_table_btn.addItem(self.horizontalSpacer_table_left)

        self.open_table_btn = QPushButton(self.controls_container)
        self.open_table_btn.setObjectName(u"open_table_btn")
        self.open_table_btn.setVisible(False)
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.open_table_btn.sizePolicy().hasHeightForWidth())
        self.open_table_btn.setSizePolicy(sizePolicy2)
        self.open_table_btn.setMinimumSize(QSize(200, 40))
        font3 = QFont()
        font3.setFamilies([u"Segoe UI"])
        font3.setPointSize(11)
        self.open_table_btn.setFont(font3)
        self.open_table_btn.setStyleSheet(u"QPushButton {\n"
"	background-color: rgb(230, 230, 230);\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")

        self.horizontalLayout_table_btn.addWidget(self.open_table_btn)

        self.horizontalSpacer_table_right = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_table_btn.addItem(self.horizontalSpacer_table_right)


        self.controls.addLayout(self.horizontalLayout_table_btn)

        self.controls.setStretch(0, 1)
        self.controls.setStretch(3, 2)

        self.horizontalLayout.addWidget(self.controls_container)

        self.horizontalLayout.setStretch(0, 1)

        self.retranslateUi(Sensorgram)

        QMetaObject.connectSlotsByName(Sensorgram)
    # setupUi

    def retranslateUi(self, Sensorgram):
        Sensorgram.setWindowTitle(QCoreApplication.translate("Sensorgram", u"Form", None))
        self.groupBox.setTitle(QCoreApplication.translate("Sensorgram", u"Display", None))
        self.segment_A.setText(QCoreApplication.translate("Sensorgram", u"Channel A", None))
        self.segment_B.setText(QCoreApplication.translate("Sensorgram", u"Channel B", None))
        self.segment_C.setText(QCoreApplication.translate("Sensorgram", u"Channel C", None))
        self.segment_D.setText(QCoreApplication.translate("Sensorgram", u"Channel D", None))
        # shift_display_box removed
        self.clear_graph_btn.setText("")
        self.groupBox_display_right.setTitle(QCoreApplication.translate("Sensorgram", u"Display", None))
        self.segment_A_right.setText(QCoreApplication.translate("Sensorgram", u"A", None))
        self.segment_B_right.setText(QCoreApplication.translate("Sensorgram", u"B", None))
        self.segment_C_right.setText(QCoreApplication.translate("Sensorgram", u"C", None))
        self.segment_D_right.setText(QCoreApplication.translate("Sensorgram", u"D", None))
        # Removed groupBox_6 and related labels - old gray box controls deleted
        self.inject_button.setText(QCoreApplication.translate("Sensorgram", u"Inject", None))
        self.regen_button.setText(QCoreApplication.translate("Sensorgram", u"Regenerate", None))
        self.flush_button.setText(QCoreApplication.translate("Sensorgram", u"Flush", None))
        # Old flow rate section removed - flow_rate widgets now hidden
        self.flow_rate_now.setText(QCoreApplication.translate("Sensorgram", u"30", None))
        # groupBox_4 is now a QFrame with a title label, not QGroupBox
        self.cycle_title.setText(QCoreApplication.translate("Sensorgram", u"Cycle Settings", None))
        self.label_exp_time.setText(QCoreApplication.translate("Sensorgram", u"Experiment time:", None))
        self.exp_clock_settings.setText(QCoreApplication.translate("Sensorgram", u"00h 02m 50s", None))
        self.label_cycle_type.setText(QCoreApplication.translate("Sensorgram", u"Type:", None))
        self.label_cycle_duration.setText(QCoreApplication.translate("Sensorgram", u"Duration (minutes):", None))
        self.current_cycle_duration.setItemText(0, QCoreApplication.translate("Sensorgram", u"2", None))
        self.current_cycle_duration.setItemText(1, QCoreApplication.translate("Sensorgram", u"5", None))
        self.current_cycle_duration.setItemText(2, QCoreApplication.translate("Sensorgram", u"15", None))
        self.current_cycle_duration.setItemText(3, QCoreApplication.translate("Sensorgram", u"30", None))
        self.current_cycle_duration.setItemText(4, QCoreApplication.translate("Sensorgram", u"60", None))
        self.current_cycle_type.setItemText(0, QCoreApplication.translate("Sensorgram", u"Auto-read", None))
        self.current_cycle_type.setItemText(1, QCoreApplication.translate("Sensorgram", u"Baseline", None))
        self.current_cycle_type.setItemText(2, QCoreApplication.translate("Sensorgram", u"Flow", None))
        self.current_cycle_type.setItemText(3, QCoreApplication.translate("Sensorgram", u"Static", None))

        self.save_segment_btn.setText(QCoreApplication.translate("Sensorgram", u"Start", None))
        self.new_segment_btn.setText(QCoreApplication.translate("Sensorgram", u"Data Table", None))
#if QT_CONFIG(tooltip)
        self.reset_segment_btn.setToolTip(QCoreApplication.translate("Sensorgram", u"Clear All Data", None))
#endif // QT_CONFIG(tooltip)
        self.reset_segment_btn.setText("")
        self.open_table_btn.setText(QCoreApplication.translate("Sensorgram", u"Open Cycle Data Table", None))
    # retranslateUi

