# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sensorgram.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
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
from PySide6.QtWidgets import (QAbstractScrollArea, QApplication, QCheckBox, QFrame,
    QGraphicsView, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton,
    QSizePolicy, QSpacerItem, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)
import ui.ai_rc

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
"	color: rgb(0, 230, 65);\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	background: white;\n"
"	border-radius: 3px;\n"
"}")
        self.segment_D.setChecked(True)

        self.horizontalLayout_12.addWidget(self.segment_D)


        self.displays.addWidget(self.groupBox)

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
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_3.addItem(self.horizontalSpacer_4)

        self.verticalSpacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

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
        self.horizontalSpacer_5 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_4.addItem(self.horizontalSpacer_5)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.horizontalLayout_4.addItem(self.verticalSpacer_2)


        self.displays.addWidget(self.SOI)


        self.horizontalLayout.addLayout(self.displays)

        self.controls = QVBoxLayout()
        self.controls.setObjectName(u"controls")
        self.horizontalLayout_5 = QHBoxLayout()
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.groupBox_6 = QGroupBox(Sensorgram)
        self.groupBox_6.setObjectName(u"groupBox_6")
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
        self.label_3.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.horizontalLayout_14.addWidget(self.label_3)

        self.exp_clock = QLabel(Sensorgram)
        self.exp_clock.setObjectName(u"exp_clock")
        self.exp_clock.setStyleSheet(u"")

        self.horizontalLayout_14.addWidget(self.exp_clock)


        self.verticalLayout_2.addLayout(self.horizontalLayout_14)

        self.groupBox_3 = QGroupBox(Sensorgram)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.verticalLayout_5 = QVBoxLayout(self.groupBox_3)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.horizontalLayout_8 = QHBoxLayout()
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.label_20 = QLabel(self.groupBox_3)
        self.label_20.setObjectName(u"label_20")
        self.label_20.setMargin(2)

        self.horizontalLayout_8.addWidget(self.label_20)

        self.shift_A = QLabel(self.groupBox_3)
        self.shift_A.setObjectName(u"shift_A")
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.shift_A.sizePolicy().hasHeightForWidth())
        self.shift_A.setSizePolicy(sizePolicy)
        self.shift_A.setStyleSheet(u"background: white;\n"
"border: 1px solid rgb(171, 171, 171);\n"
"border-radius: 2px;")
        self.shift_A.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_8.addWidget(self.shift_A)

        self.unit_a = QLabel(self.groupBox_3)
        self.unit_a.setObjectName(u"unit_a")
        self.unit_a.setMargin(0)

        self.horizontalLayout_8.addWidget(self.unit_a)


        self.verticalLayout_5.addLayout(self.horizontalLayout_8)

        self.horizontalLayout_9 = QHBoxLayout()
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.label_21 = QLabel(self.groupBox_3)
        self.label_21.setObjectName(u"label_21")
        self.label_21.setMargin(2)

        self.horizontalLayout_9.addWidget(self.label_21)

        self.shift_B = QLabel(self.groupBox_3)
        self.shift_B.setObjectName(u"shift_B")
        sizePolicy.setHeightForWidth(self.shift_B.sizePolicy().hasHeightForWidth())
        self.shift_B.setSizePolicy(sizePolicy)
        self.shift_B.setStyleSheet(u"background: white;\n"
"border: 1px solid rgb(171, 171, 171);\n"
"border-radius: 2px;")
        self.shift_B.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_9.addWidget(self.shift_B)

        self.unit_b = QLabel(self.groupBox_3)
        self.unit_b.setObjectName(u"unit_b")
        self.unit_b.setMargin(0)

        self.horizontalLayout_9.addWidget(self.unit_b)


        self.verticalLayout_5.addLayout(self.horizontalLayout_9)

        self.horizontalLayout_10 = QHBoxLayout()
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.label_22 = QLabel(self.groupBox_3)
        self.label_22.setObjectName(u"label_22")
        self.label_22.setMargin(2)

        self.horizontalLayout_10.addWidget(self.label_22)

        self.shift_C = QLabel(self.groupBox_3)
        self.shift_C.setObjectName(u"shift_C")
        sizePolicy.setHeightForWidth(self.shift_C.sizePolicy().hasHeightForWidth())
        self.shift_C.setSizePolicy(sizePolicy)
        self.shift_C.setStyleSheet(u"background: white;\n"
"border: 1px solid rgb(171, 171, 171);\n"
"border-radius: 2px;")
        self.shift_C.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_10.addWidget(self.shift_C)

        self.unit_c = QLabel(self.groupBox_3)
        self.unit_c.setObjectName(u"unit_c")
        self.unit_c.setMargin(0)

        self.horizontalLayout_10.addWidget(self.unit_c)


        self.verticalLayout_5.addLayout(self.horizontalLayout_10)

        self.horizontalLayout_11 = QHBoxLayout()
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.label_23 = QLabel(self.groupBox_3)
        self.label_23.setObjectName(u"label_23")
        self.label_23.setMargin(2)

        self.horizontalLayout_11.addWidget(self.label_23)

        self.shift_D = QLabel(self.groupBox_3)
        self.shift_D.setObjectName(u"shift_D")
        sizePolicy.setHeightForWidth(self.shift_D.sizePolicy().hasHeightForWidth())
        self.shift_D.setSizePolicy(sizePolicy)
        self.shift_D.setStyleSheet(u"background: white;\n"
"border: 1px solid rgb(171, 171, 171);\n"
"border-radius: 2px;")
        self.shift_D.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_11.addWidget(self.shift_D)

        self.unit_d = QLabel(self.groupBox_3)
        self.unit_d.setObjectName(u"unit_d")
        self.unit_d.setMargin(0)

        self.horizontalLayout_11.addWidget(self.unit_d)


        self.verticalLayout_5.addLayout(self.horizontalLayout_11)


        self.verticalLayout_2.addWidget(self.groupBox_3)


        self.horizontalLayout_5.addLayout(self.verticalLayout_2)

        self.verticalLayout = QVBoxLayout()
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.loop_diagram = QGraphicsView(Sensorgram)
        self.loop_diagram.setObjectName(u"loop_diagram")
        self.loop_diagram.setMaximumSize(QSize(16777215, 134))
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
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.flow_rate_now.sizePolicy().hasHeightForWidth())
        self.flow_rate_now.setSizePolicy(sizePolicy1)
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

        self.verticalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout.addItem(self.verticalSpacer_3)

        self.groupBox_4 = QGroupBox(Sensorgram)
        self.groupBox_4.setObjectName(u"groupBox_4")
        self.verticalLayout_3 = QVBoxLayout(self.groupBox_4)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.current_note = QLineEdit(self.groupBox_4)
        self.current_note.setObjectName(u"current_note")

        self.verticalLayout_3.addWidget(self.current_note)


        self.verticalLayout.addWidget(self.groupBox_4)


        self.horizontalLayout_5.addLayout(self.verticalLayout)

        self.horizontalLayout_5.setStretch(0, 1)
        self.horizontalLayout_5.setStretch(1, 2)

        self.controls.addLayout(self.horizontalLayout_5)

        self.horizontalLayout_13 = QHBoxLayout()
        self.horizontalLayout_13.setObjectName(u"horizontalLayout_13")
        self.horizontalSpacer_3 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_3)

        self.save_segment_btn = QPushButton(Sensorgram)
        self.save_segment_btn.setObjectName(u"save_segment_btn")
        self.save_segment_btn.setFont(font)
        self.save_segment_btn.setFocusPolicy(Qt.NoFocus)

        self.horizontalLayout_13.addWidget(self.save_segment_btn)

        self.horizontalSpacer_2 = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer_2)

        self.new_segment_btn = QPushButton(Sensorgram)
        self.new_segment_btn.setObjectName(u"new_segment_btn")
        self.new_segment_btn.setFont(font)

        self.horizontalLayout_13.addWidget(self.new_segment_btn)

        self.horizontalSpacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_13.addItem(self.horizontalSpacer)

        self.horizontalLayout_13.setStretch(0, 4)
        self.horizontalLayout_13.setStretch(2, 1)
        self.horizontalLayout_13.setStretch(4, 4)

        self.controls.addLayout(self.horizontalLayout_13)

        self.seg_table = QFrame(Sensorgram)
        self.seg_table.setObjectName(u"seg_table")
        sizePolicy2 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy2.setHorizontalStretch(41)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.seg_table.sizePolicy().hasHeightForWidth())
        self.seg_table.setSizePolicy(sizePolicy2)
        self.seg_table.setMinimumSize(QSize(510, 50))
        self.seg_table.setMaximumSize(QSize(510, 50))
        self.seg_table.setFont(font)
        self.seg_table.setFrameShape(QFrame.StyledPanel)
        self.seg_table.setFrameShadow(QFrame.Raised)
        self.delete_row_btn = QPushButton(self.seg_table)
        self.delete_row_btn.setObjectName(u"delete_row_btn")
        self.delete_row_btn.setGeometry(QRect(30, 10, 30, 30))
        sizePolicy3 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.delete_row_btn.sizePolicy().hasHeightForWidth())
        self.delete_row_btn.setSizePolicy(sizePolicy3)
        self.delete_row_btn.setMinimumSize(QSize(30, 30))
        self.delete_row_btn.setMaximumSize(QSize(30, 30))
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(5)
        self.delete_row_btn.setFont(font2)
        self.delete_row_btn.setMouseTracking(True)
        self.delete_row_btn.setLayoutDirection(Qt.LeftToRight)
        self.delete_row_btn.setAutoFillBackground(False)
        self.delete_row_btn.setStyleSheet(u"QPushButton{\n"
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
        icon.addFile(u":/img/img/trash.png", QSize(), QIcon.Normal, QIcon.Off)
        self.delete_row_btn.setIcon(icon)
        self.delete_row_btn.setIconSize(QSize(25, 25))
        self.delete_row_btn.setAutoRepeat(False)
        self.delete_row_btn.setAutoExclusive(False)
        self.delete_row_btn.setAutoDefault(False)
        self.delete_row_btn.setFlat(False)
        self.add_row_btn = QPushButton(self.seg_table)
        self.add_row_btn.setObjectName(u"add_row_btn")
        self.add_row_btn.setGeometry(QRect(70, 10, 30, 30))
        sizePolicy3.setHeightForWidth(self.add_row_btn.sizePolicy().hasHeightForWidth())
        self.add_row_btn.setSizePolicy(sizePolicy3)
        self.add_row_btn.setMinimumSize(QSize(30, 30))
        self.add_row_btn.setMaximumSize(QSize(30, 30))
        self.add_row_btn.setFont(font2)
        self.add_row_btn.setMouseTracking(True)
        self.add_row_btn.setLayoutDirection(Qt.LeftToRight)
        self.add_row_btn.setAutoFillBackground(False)
        self.add_row_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 10px;\n"
"}")
        icon1 = QIcon()
        icon1.addFile(u":/img/img/undo.png", QSize(), QIcon.Normal, QIcon.Off)
        self.add_row_btn.setIcon(icon1)
        self.add_row_btn.setIconSize(QSize(22, 22))
        self.add_row_btn.setAutoRepeat(False)
        self.add_row_btn.setAutoExclusive(False)
        self.add_row_btn.setAutoDefault(False)
        self.add_row_btn.setFlat(False)
        self.table_toggle = QPushButton(self.seg_table)
        self.table_toggle.setObjectName(u"table_toggle")
        self.table_toggle.setGeometry(QRect(140, 10, 251, 30))
        sizePolicy4 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.table_toggle.sizePolicy().hasHeightForWidth())
        self.table_toggle.setSizePolicy(sizePolicy4)
        self.table_toggle.setMinimumSize(QSize(0, 30))
        font3 = QFont()
        font3.setFamilies([u"Segoe UI"])
        font3.setPointSize(11)
        self.table_toggle.setFont(font3)
        self.page_indicator = QGraphicsView(self.seg_table)
        self.page_indicator.setObjectName(u"page_indicator")
        self.page_indicator.setGeometry(QRect(318, 21, 30, 10))
        self.page_indicator.setStyleSheet(u"background: transparent")
        self.page_indicator.setFrameShape(QFrame.NoFrame)
        self.page_indicator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.page_indicator.setInteractive(False)

        self.controls.addWidget(self.seg_table)

        self.data_table = QTableWidget(Sensorgram)
        if (self.data_table.columnCount() < 9):
            self.data_table.setColumnCount(9)
        font4 = QFont()
        font4.setFamilies([u"Segoe UI"])
        font4.setPointSize(8)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setText(u"ID");
        __qtablewidgetitem.setFont(font4);
        self.data_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font4);
        self.data_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        font5 = QFont()
        font5.setPointSize(8)
        __qtablewidgetitem2 = QTableWidgetItem()
        __qtablewidgetitem2.setFont(font5);
        self.data_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setFont(font5);
        self.data_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        __qtablewidgetitem4.setFont(font5);
        self.data_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setFont(font5);
        self.data_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        __qtablewidgetitem6.setFont(font5);
        self.data_table.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        __qtablewidgetitem7.setFont(font5);
        self.data_table.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        __qtablewidgetitem8.setFont(font5);
        self.data_table.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        self.data_table.setObjectName(u"data_table")
        sizePolicy5 = QSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.data_table.sizePolicy().hasHeightForWidth())
        self.data_table.setSizePolicy(sizePolicy5)
        self.data_table.setFont(font)
        self.data_table.setFocusPolicy(Qt.ClickFocus)
        self.data_table.setFrameShape(QFrame.NoFrame)
        self.data_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.data_table.setShowGrid(True)
        self.data_table.setWordWrap(True)
        self.data_table.setRowCount(0)
        self.data_table.setColumnCount(9)
        self.data_table.horizontalHeader().setVisible(True)
        self.data_table.horizontalHeader().setCascadingSectionResizes(True)
        self.data_table.horizontalHeader().setMinimumSectionSize(50)
        self.data_table.horizontalHeader().setDefaultSectionSize(50)
        self.data_table.horizontalHeader().setHighlightSections(True)
        self.data_table.horizontalHeader().setProperty("showSortIndicator", False)
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.verticalHeader().setCascadingSectionResizes(False)
        self.data_table.verticalHeader().setMinimumSectionSize(40)
        self.data_table.verticalHeader().setDefaultSectionSize(50)
        self.data_table.verticalHeader().setHighlightSections(False)
        self.data_table.verticalHeader().setProperty("showSortIndicator", False)
        self.data_table.verticalHeader().setStretchLastSection(False)

        self.controls.addWidget(self.data_table)

        self.controls.setStretch(0, 1)
        self.controls.setStretch(3, 2)

        self.horizontalLayout.addLayout(self.controls)

        self.horizontalLayout.setStretch(0, 1)

        self.retranslateUi(Sensorgram)

        self.delete_row_btn.setDefault(False)
        self.add_row_btn.setDefault(False)


        QMetaObject.connectSlotsByName(Sensorgram)
    # setupUi

    def retranslateUi(self, Sensorgram):
        Sensorgram.setWindowTitle(QCoreApplication.translate("Sensorgram", u"Form", None))
        self.groupBox.setTitle(QCoreApplication.translate("Sensorgram", u"Display", None))
        self.segment_A.setText(QCoreApplication.translate("Sensorgram", u"Channel A", None))
        self.segment_B.setText(QCoreApplication.translate("Sensorgram", u"Channel B", None))
        self.segment_C.setText(QCoreApplication.translate("Sensorgram", u"Channel C", None))
        self.segment_D.setText(QCoreApplication.translate("Sensorgram", u"Channel D", None))
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
        self.groupBox_3.setTitle(QCoreApplication.translate("Sensorgram", u"Cycle Shift", None))
        self.label_20.setText(QCoreApplication.translate("Sensorgram", u"Shift A:", None))
        self.shift_A.setText(QCoreApplication.translate("Sensorgram", u"-", None))
        self.unit_a.setText(QCoreApplication.translate("Sensorgram", u"RU", None))
        self.label_21.setText(QCoreApplication.translate("Sensorgram", u"Shift B:", None))
        self.shift_B.setText(QCoreApplication.translate("Sensorgram", u"-", None))
        self.unit_b.setText(QCoreApplication.translate("Sensorgram", u"RU", None))
        self.label_22.setText(QCoreApplication.translate("Sensorgram", u"Shift C:", None))
        self.shift_C.setText(QCoreApplication.translate("Sensorgram", u"-", None))
        self.unit_c.setText(QCoreApplication.translate("Sensorgram", u"RU", None))
        self.label_23.setText(QCoreApplication.translate("Sensorgram", u"Shift D:", None))
        self.shift_D.setText(QCoreApplication.translate("Sensorgram", u"-", None))
        self.unit_d.setText(QCoreApplication.translate("Sensorgram", u"RU", None))
        self.inject_button.setText(QCoreApplication.translate("Sensorgram", u"Inject", None))
        self.regen_button.setText(QCoreApplication.translate("Sensorgram", u"Regenerate", None))
        self.flush_button.setText(QCoreApplication.translate("Sensorgram", u"Flush", None))
        self.flow_rate_box.setTitle(QCoreApplication.translate("Sensorgram", u"Flow Rate", None))
        self.label_8.setText(QCoreApplication.translate("Sensorgram", u"Current:", None))
        self.flow_rate_now.setText(QCoreApplication.translate("Sensorgram", u"30", None))
        self.label_4.setText(QCoreApplication.translate("Sensorgram", u"\u03bcL/min", None))
        self.label.setText(QCoreApplication.translate("Sensorgram", u"New:", None))
        self.label_2.setText(QCoreApplication.translate("Sensorgram", u"\u03bcL/min", None))
        self.groupBox_4.setTitle(QCoreApplication.translate("Sensorgram", u"Cycle Notes", None))
        self.save_segment_btn.setText(QCoreApplication.translate("Sensorgram", u"Save\n"
"Cycle", None))
        self.new_segment_btn.setText(QCoreApplication.translate("Sensorgram", u"Start at\n"
"Live Time", None))
#if QT_CONFIG(tooltip)
        self.delete_row_btn.setToolTip(QCoreApplication.translate("Sensorgram", u"Delete Cycle", None))
#endif // QT_CONFIG(tooltip)
        self.delete_row_btn.setText("")
#if QT_CONFIG(tooltip)
        self.add_row_btn.setToolTip(QCoreApplication.translate("Sensorgram", u"Restore Last Deleted", None))
#endif // QT_CONFIG(tooltip)
        self.add_row_btn.setText("")
        self.table_toggle.setText(QCoreApplication.translate("Sensorgram", u"Cycle Data Table", None))
        ___qtablewidgetitem = self.data_table.horizontalHeaderItem(1)
        ___qtablewidgetitem.setText(QCoreApplication.translate("Sensorgram", u"Start", None));
        ___qtablewidgetitem1 = self.data_table.horizontalHeaderItem(2)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("Sensorgram", u"End", None));
        ___qtablewidgetitem2 = self.data_table.horizontalHeaderItem(3)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("Sensorgram", u"Shift A", None));
        ___qtablewidgetitem3 = self.data_table.horizontalHeaderItem(4)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("Sensorgram", u"Shift B", None));
        ___qtablewidgetitem4 = self.data_table.horizontalHeaderItem(5)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("Sensorgram", u"Shift C", None));
        ___qtablewidgetitem5 = self.data_table.horizontalHeaderItem(6)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("Sensorgram", u"Shift D", None));
        ___qtablewidgetitem6 = self.data_table.horizontalHeaderItem(7)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("Sensorgram", u"Ref", None));
        ___qtablewidgetitem7 = self.data_table.horizontalHeaderItem(8)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("Sensorgram", u"Note", None));
    # retranslateUi

