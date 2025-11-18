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
        self.groupBox = QGroupBox(Sensorgram)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setStyleSheet(u"QGroupBox#groupBox{\n"
"	background-color: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 5px;\n"
"	padding: 10px;\n"
"}")
        self.horizontalLayout_12 = QHBoxLayout(self.groupBox)
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.segment_A = QCheckBox(self.groupBox)
        self.segment_A.setObjectName(u"segment_A")
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(9)
        font1.setBold(True)
        self.segment_A.setFont(font1)
        self.segment_A.setStyleSheet(u"QCheckBox{\n"
"	color: black;\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_A.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_A)

        self.segment_B = QCheckBox(self.groupBox)
        self.segment_B.setObjectName(u"segment_B")
        self.segment_B.setFont(font1)
        self.segment_B.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(255, 0, 81);\n"
"	background:white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_B.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_B)

        self.segment_C = QCheckBox(self.groupBox)
        self.segment_C.setObjectName(u"segment_C")
        self.segment_C.setFont(font1)
        self.segment_C.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 174, 255);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_C.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_C)

        self.segment_D = QCheckBox(self.groupBox)
        self.segment_D.setObjectName(u"segment_D")
        self.segment_D.setFont(font1)
        self.segment_D.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 100, 0);\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	background: white;\n"
"	border-radius: 3px;\n"
"}")
        self.segment_D.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_D)
        
        self.clear_graph_btn_in_display = QPushButton(self.groupBox)
        self.clear_graph_btn_in_display.setObjectName(u"clear_graph_btn_in_display")
        self.clear_graph_btn_in_display.setText("Clear")
        self.clear_graph_btn_in_display.setMinimumSize(QSize(60, 26))
        self.clear_graph_btn_in_display.setMaximumSize(QSize(80, 26))

        self.horizontalLayout_12.addWidget(self.clear_graph_btn_in_display)


        self.displays.addWidget(self.groupBox)

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

        self.horizontalLayout_sensor_header.addWidget(self.clear_graph_btn)

        self.adjust_rect_btn = QPushButton(Sensorgram)
        self.adjust_rect_btn.setObjectName(u"adjust_rect_btn")
        self.adjust_rect_btn.setText("Adjust Rect")
        self.adjust_rect_btn.setMinimumSize(QSize(80, 30))

        self.horizontalLayout_sensor_header.addWidget(self.adjust_rect_btn)

        self.horizontalSpacer_header = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_sensor_header.addItem(self.horizontalSpacer_header)

        self.horizontalLayout_sensor_header.setStretch(0, 1)

        self.displays.addLayout(self.horizontalLayout_sensor_header)

        self.full_segment = QFrame(Sensorgram)
        self.full_segment.setObjectName(u"full_segment")
        self.full_segment.setMinimumSize(QSize(200, 250))
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
        self.SOI.setMinimumSize(QSize(200, 250))
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

        self.controls = QVBoxLayout()
        self.controls.setObjectName(u"controls")
        self.groupBox_display_right = QGroupBox(Sensorgram)
        self.groupBox_display_right.setObjectName(u"groupBox_display_right")
        self.groupBox_display_right.setStyleSheet(u"QGroupBox#groupBox_display_right{\n"
"	background-color: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 5px;\n"
"	padding: 10px;\n"
"}")
        self.verticalLayout_display = QVBoxLayout(self.groupBox_display_right)
        self.verticalLayout_display.setObjectName(u"verticalLayout_display")
        self.segment_A_right = QCheckBox(self.groupBox_display_right)
        self.segment_A_right.setObjectName(u"segment_A_right")
        self.segment_A_right.setFont(font1)
        self.segment_A_right.setStyleSheet(u"QCheckBox{\n"
"	color: black;\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 3px;\n"
"}")
        self.segment_A_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_A_right)

        self.segment_B_right = QCheckBox(self.groupBox_display_right)
        self.segment_B_right.setObjectName(u"segment_B_right")
        self.segment_B_right.setFont(font1)
        self.segment_B_right.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(255, 0, 81);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 3px;\n"
"}")
        self.segment_B_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_B_right)

        self.segment_C_right = QCheckBox(self.groupBox_display_right)
        self.segment_C_right.setObjectName(u"segment_C_right")
        self.segment_C_right.setFont(font1)
        self.segment_C_right.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 174, 255);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 3px;\n"
"}")
        self.segment_C_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_C_right)

        self.segment_D_right = QCheckBox(self.groupBox_display_right)
        self.segment_D_right.setObjectName(u"segment_D_right")
        self.segment_D_right.setFont(font1)
        self.segment_D_right.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 230, 65);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 3px;\n"
"}")
        self.segment_D_right.setChecked(True)

        self.verticalLayout_display.addWidget(self.segment_D_right)


        self.controls.addWidget(self.groupBox_display_right)

        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.groupBox_6 = QGroupBox(Sensorgram)
        self.groupBox_6.setObjectName(u"groupBox_6")
        self.groupBox_6.setVisible(False)
        self.verticalLayout_4 = QVBoxLayout(self.groupBox_6)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.live_btn = QCheckBox(self.groupBox_6)
        self.live_btn.setObjectName(u"live_btn")
        self.live_btn.setChecked(True)

        self.verticalLayout_4.addWidget(self.live_btn)

        self.label_14 = QLabel(self.groupBox_6)
        self.label_14.setObjectName(u"label_14")

        self.verticalLayout_4.addWidget(self.label_14)

        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.label_6 = QLabel(self.groupBox_6)
        self.label_6.setObjectName(u"label_6")
        self.label_6.setStyleSheet(u"background: yellow;\n"
"border-radius: 2px;\n"
"border: 2px solid rgb(100, 100, 100);")

        self.horizontalLayout_6.addWidget(self.label_6)

        self.left_cursor_time = QLineEdit(self.groupBox_6)
        self.left_cursor_time.setObjectName(u"left_cursor_time")
        self.left_cursor_time.setFont(font)
        self.left_cursor_time.setFocusPolicy(Qt.ClickFocus)
        self.left_cursor_time.setStyleSheet(u"\n"
"QLineEdit {\n"
"		background-color: white;\n"
"		border: 1px solid rgb(171, 171, 171);\n"
"		border-radius: 2px;\n"
"\n"
"}\n"
"\n"
"QLineEdit:focus{\n"
"	background-color: rgb(240, 255, 245);\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 2px;\n"
"}")
        self.left_cursor_time.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_6.addWidget(self.left_cursor_time)

        self.label_10 = QLabel(self.groupBox_6)
        self.label_10.setObjectName(u"label_10")

        self.horizontalLayout_6.addWidget(self.label_10)


        self.verticalLayout_4.addLayout(self.horizontalLayout_6)

        self.label_16 = QLabel(self.groupBox_6)
        self.label_16.setObjectName(u"label_16")

        self.verticalLayout_4.addWidget(self.label_16)

        self.horizontalLayout_7 = QHBoxLayout()
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.label_7 = QLabel(self.groupBox_6)
        self.label_7.setObjectName(u"label_7")
        self.label_7.setStyleSheet(u"background: red;\n"
"border-radius: 2px;\n"
"border: 2px solid rgb(100, 100, 100);")

        self.horizontalLayout_7.addWidget(self.label_7)

        self.right_cursor_time = QLineEdit(self.groupBox_6)
        self.right_cursor_time.setObjectName(u"right_cursor_time")
        self.right_cursor_time.setFont(font)
        self.right_cursor_time.setFocusPolicy(Qt.ClickFocus)
        self.right_cursor_time.setStyleSheet(u"\n"
"QLineEdit {\n"
"		background-color: white;\n"
"		border: 1px solid rgb(171, 171, 171);\n"
"		border-radius: 2px;\n"
"\n"
"}\n"
"\n"
"QLineEdit:focus{\n"
"	background-color: rgb(240, 255, 245);\n"
"	border: 1px solid rgb(171, 171, 171);\n"
"	border-radius: 2px;\n"
"}")
        self.right_cursor_time.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_7.addWidget(self.right_cursor_time)

        self.label_9 = QLabel(self.groupBox_6)
        self.label_9.setObjectName(u"label_9")

        self.horizontalLayout_7.addWidget(self.label_9)


        self.verticalLayout_4.addLayout(self.horizontalLayout_7)


        self.verticalLayout_2.addWidget(self.groupBox_6)

        self.horizontalLayout_14 = QHBoxLayout()
        self.horizontalLayout_14.setObjectName(u"horizontalLayout_14")
        self.label_3 = QLabel(Sensorgram)
        self.label_3.setObjectName(u"label_3")
        self.label_3.setVisible(False)
        self.label_3.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_14.addWidget(self.label_3)

        self.exp_clock = QLabel(Sensorgram)
        self.exp_clock.setObjectName(u"exp_clock")
        self.exp_clock.setVisible(False)
        self.exp_clock.setStyleSheet(u"")

        self.horizontalLayout_14.addWidget(self.exp_clock)


        self.verticalLayout_2.addLayout(self.horizontalLayout_14)


        self.horizontalLayout_5.addLayout(self.verticalLayout_2)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.loop_diagram = QGraphicsView(Sensorgram)
        self.loop_diagram.setObjectName(u"loop_diagram")
        self.loop_diagram.setMaximumSize(QSize(16777215, 200))
        self.loop_diagram.setStyleSheet(u"background:transparent")
        self.loop_diagram.setFrameShape(QFrame.NoFrame)
        self.loop_diagram.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.loop_diagram.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.verticalLayout.addWidget(self.loop_diagram)

        self.progress_bar = QProgressBar(Sensorgram)
        self.progress_bar.setObjectName(u"progress_bar")
        self.progress_bar.setValue(24)

        self.verticalLayout.addWidget(self.progress_bar)

        self.inject_box = QWidget(Sensorgram)
        self.inject_box.setObjectName(u"inject_box")
        self.inject_box.setEnabled(False)
        self.horizontalLayout_16 = QHBoxLayout(self.inject_box)
        self.horizontalLayout_16.setObjectName(u"horizontalLayout_16")
        self.horizontalLayout_16.setContentsMargins(0, 0, 0, 0)
        self.inject_button = QPushButton(self.inject_box)
        self.inject_button.setObjectName(u"inject_button")

        self.horizontalLayout_16.addWidget(self.inject_button)

        self.regen_button = QPushButton(self.inject_box)
        self.regen_button.setObjectName(u"regen_button")

        self.horizontalLayout_16.addWidget(self.regen_button)

        self.flush_button = QPushButton(self.inject_box)
        self.flush_button.setObjectName(u"flush_button")

        self.horizontalLayout_16.addWidget(self.flush_button)


        self.verticalLayout.addWidget(self.inject_box)

        self.flow_rate_box = QGroupBox(Sensorgram)
        self.flow_rate_box.setObjectName(u"flow_rate_box")
        self.flow_rate_box.setEnabled(False)
        self.verticalLayout_6 = QVBoxLayout(self.flow_rate_box)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.horizontalLayout_15 = QHBoxLayout()
        self.horizontalLayout_15.setObjectName(u"horizontalLayout_15")
        self.label_8 = QLabel(self.flow_rate_box)
        self.label_8.setObjectName(u"label_8")

        self.horizontalLayout_15.addWidget(self.label_8)

        self.flow_rate_now = QLabel(self.flow_rate_box)
        self.flow_rate_now.setObjectName(u"flow_rate_now")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.flow_rate_now.sizePolicy().hasHeightForWidth())
        self.flow_rate_now.setSizePolicy(sizePolicy)
        self.flow_rate_now.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_15.addWidget(self.flow_rate_now)

        self.label_4 = QLabel(self.flow_rate_box)
        self.label_4.setObjectName(u"label_4")

        self.horizontalLayout_15.addWidget(self.label_4)


        self.verticalLayout_6.addLayout(self.horizontalLayout_15)

        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.label = QLabel(self.flow_rate_box)
        self.label.setObjectName(u"label")

        self.horizontalLayout_2.addWidget(self.label)

        self.flow_rate = QLineEdit(self.flow_rate_box)
        self.flow_rate.setObjectName(u"flow_rate")
        self.flow_rate.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_2.addWidget(self.flow_rate)

        self.label_2 = QLabel(self.flow_rate_box)
        self.label_2.setObjectName(u"label_2")

        self.horizontalLayout_2.addWidget(self.label_2)


        self.verticalLayout_6.addLayout(self.horizontalLayout_2)


        self.verticalLayout.addWidget(self.flow_rate_box)

        self.verticalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)

        self.groupBox_4 = QGroupBox(Sensorgram)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.verticalLayout_3 = QVBoxLayout(self.groupBox_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
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


        self.horizontalLayout_5.addLayout(self.verticalLayout)

        self.horizontalLayout_5.setStretch(0, 1)
        self.horizontalLayout_5.setStretch(1, 2)

        self.controls.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.horizontalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_3)

        self.reset_segment_btn = QPushButton(Sensorgram)
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

        self.open_table_btn = QPushButton(Sensorgram)
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

        self.horizontalLayout.addLayout(self.controls)

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
        self.shift_display_box.setText(QCoreApplication.translate("Sensorgram", u"Ready", None))
        self.clear_graph_btn.setText("")
        self.groupBox_display_right.setTitle(QCoreApplication.translate("Sensorgram", u"Display", None))
        self.segment_A_right.setText(QCoreApplication.translate("Sensorgram", u"A", None))
        self.segment_B_right.setText(QCoreApplication.translate("Sensorgram", u"B", None))
        self.segment_C_right.setText(QCoreApplication.translate("Sensorgram", u"C", None))
        self.segment_D_right.setText(QCoreApplication.translate("Sensorgram", u"D", None))
        self.groupBox_6.setTitle(QCoreApplication.translate("Sensorgram", u"Cycle Cursors", None))
        self.live_btn.setText(QCoreApplication.translate("Sensorgram", u"Live View Mode", None))
        self.label_14.setText(QCoreApplication.translate("Sensorgram", u"Start Cursor:", None))
        self.label_6.setText("")
        self.label_10.setText(QCoreApplication.translate("Sensorgram", u"s", None))
        self.label_16.setText(QCoreApplication.translate("Sensorgram", u"End Cursor:", None))
        self.label_7.setText("")
        self.label_9.setText(QCoreApplication.translate("Sensorgram", u"s", None))
        self.label_3.setText(QCoreApplication.translate("Sensorgram", u"Experiment time:", None))
        self.exp_clock.setText(QCoreApplication.translate("Sensorgram", u"HH:MM:SS", None))
        self.inject_button.setText(QCoreApplication.translate("Sensorgram", u"Inject", None))
        self.regen_button.setText(QCoreApplication.translate("Sensorgram", u"Regenerate", None))
        self.flush_button.setText(QCoreApplication.translate("Sensorgram", u"Flush", None))
        self.flow_rate_box.setTitle(QCoreApplication.translate("Sensorgram", u"Flow Rate", None))
        self.label_8.setText(QCoreApplication.translate("Sensorgram", u"Current:", None))
        self.flow_rate_now.setText(QCoreApplication.translate("Sensorgram", u"30", None))
        self.label_4.setText(QCoreApplication.translate("Sensorgram", u"\u03bcL/min", None))
        self.label.setText(QCoreApplication.translate("Sensorgram", u"New:", None))
        self.label_2.setText(QCoreApplication.translate("Sensorgram", u"\u03bcL/min", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("Sensorgram", u"Cycle Settings", None))
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

