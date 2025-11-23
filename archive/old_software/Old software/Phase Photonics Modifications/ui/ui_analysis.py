# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'analysis.ui'
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
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QCheckBox,
    QComboBox, QFrame, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton,
    QRadioButton, QScrollArea, QSizePolicy, QSpacerItem,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from pyqtgraph import PlotWidget
import ui.ai_rc

class Ui_FormAnalysis(object):
    def setupUi(self, FormAnalysis):
        if not FormAnalysis.objectName():
            FormAnalysis.setObjectName(u"FormAnalysis")
        FormAnalysis.resize(1459, 796)
        FormAnalysis.setMinimumSize(QSize(1050, 0))
        font = QFont()
        font.setFamilies([u"Segoe UI"])
        FormAnalysis.setFont(font)
        FormAnalysis.setMouseTracking(True)
        FormAnalysis.setFocusPolicy(Qt.StrongFocus)
        self.verticalLayout_4 = QVBoxLayout(FormAnalysis)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.frame_3 = QFrame(FormAnalysis)
        self.frame_3.setObjectName(u"frame_3")
        self.frame_3.setMinimumSize(QSize(0, 200))
        self.frame_3.setFrameShape(QFrame.StyledPanel)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(5, 5, 5, 5)
        self.stack_graph = PlotWidget(self.frame_3)
        self.stack_graph.setObjectName(u"stack_graph")
        self.stack_graph.setMinimumSize(QSize(800, 200))
        self.horizontalLayout_6 = QHBoxLayout(self.stack_graph)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalSpacer_3 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_6.addItem(self.horizontalSpacer_3)

        self.verticalLayout_6 = QVBoxLayout()
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.label_cur_info = QLabel(self.stack_graph)
        self.label_cur_info.setObjectName(u"label_cur_info")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_cur_info.sizePolicy().hasHeightForWidth())
        self.label_cur_info.setSizePolicy(sizePolicy)
        font1 = QFont()
        font1.setFamilies([u"Segoe UI"])
        font1.setPointSize(8)
        self.label_cur_info.setFont(font1)
        self.label_cur_info.setStyleSheet(u"color: rgb(150, 150, 150);")
        self.label_cur_info.setAlignment(Qt.AlignRight|Qt.AlignTop|Qt.AlignTrailing)

        self.verticalLayout_6.addWidget(self.label_cur_info)

        self.verticalSpacer_2 = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_6.addItem(self.verticalSpacer_2)


        self.horizontalLayout_6.addLayout(self.verticalLayout_6)


        self.horizontalLayout_7.addWidget(self.stack_graph)


        self.horizontalLayout.addWidget(self.frame_3)

        self.frame = QFrame(FormAnalysis)
        self.frame.setObjectName(u"frame")
        self.frame.setMinimumSize(QSize(130, 300))
        self.frame.setMaximumSize(QSize(400, 16777215))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.frame)
        self.verticalLayout_3.setSpacing(10)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, -1, 1, -1)
        self.groupBox = QGroupBox(self.frame)
        self.groupBox.setObjectName(u"groupBox")
        self.groupBox.setMinimumSize(QSize(120, 0))
        self.groupBox.setMaximumSize(QSize(150, 16777215))
        self.verticalLayout_9 = QVBoxLayout(self.groupBox)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.radio_a = QRadioButton(self.groupBox)
        self.radio_a.setObjectName(u"radio_a")
        self.radio_a.setChecked(True)

        self.verticalLayout_9.addWidget(self.radio_a, 0, Qt.AlignHCenter)

        self.radio_b = QRadioButton(self.groupBox)
        self.radio_b.setObjectName(u"radio_b")

        self.verticalLayout_9.addWidget(self.radio_b, 0, Qt.AlignHCenter)

        self.radio_c = QRadioButton(self.groupBox)
        self.radio_c.setObjectName(u"radio_c")

        self.verticalLayout_9.addWidget(self.radio_c, 0, Qt.AlignHCenter)

        self.radio_d = QRadioButton(self.groupBox)
        self.radio_d.setObjectName(u"radio_d")

        self.verticalLayout_9.addWidget(self.radio_d, 0, Qt.AlignHCenter)


        self.verticalLayout_3.addWidget(self.groupBox)

        self.verticalSpacer_6 = QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Preferred)

        self.verticalLayout_3.addItem(self.verticalSpacer_6)

        self.fit_wizard_btn = QPushButton(self.frame)
        self.fit_wizard_btn.setObjectName(u"fit_wizard_btn")
        self.fit_wizard_btn.setMinimumSize(QSize(110, 35))
        self.fit_wizard_btn.setMaximumSize(QSize(120, 16777215))
        self.fit_wizard_btn.setFont(font)
        self.fit_wizard_btn.setStyleSheet(u"QPushButton {\n"
"		\n"
"		background-color: rgb(230, 230, 230);\n"
"	    border: 1px solid rgb(171, 171, 171); \n"
"		border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")

        self.verticalLayout_3.addWidget(self.fit_wizard_btn)

        self.kin_wizard_btn = QPushButton(self.frame)
        self.kin_wizard_btn.setObjectName(u"kin_wizard_btn")
        self.kin_wizard_btn.setEnabled(True)
        self.kin_wizard_btn.setMinimumSize(QSize(110, 35))
        self.kin_wizard_btn.setMaximumSize(QSize(120, 16777215))
        self.kin_wizard_btn.setFont(font)
        self.kin_wizard_btn.setStyleSheet(u"QPushButton {\n"
"		\n"
"		background-color: rgb(230, 230, 230);\n"
"	    border: 1px solid rgb(171, 171, 171); \n"
"		border-radius: 3px;\n"
"\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: rgb(253, 253, 253);\n"
"	border: 1px raised;\n"
"	border-radius: 5px;\n"
"}")

        self.verticalLayout_3.addWidget(self.kin_wizard_btn)

        self.verticalSpacer_5 = QSpacerItem(20, 30, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer_5)

        self.file_ctrls = QFrame(self.frame)
        self.file_ctrls.setObjectName(u"file_ctrls")
        self.horizontalLayout_9 = QHBoxLayout(self.file_ctrls)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.horizontalLayout_9.setContentsMargins(0, -1, 0, -1)
        self.reset_analysis_btn = QPushButton(self.file_ctrls)
        self.reset_analysis_btn.setObjectName(u"reset_analysis_btn")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.reset_analysis_btn.sizePolicy().hasHeightForWidth())
        self.reset_analysis_btn.setSizePolicy(sizePolicy1)
        self.reset_analysis_btn.setMinimumSize(QSize(30, 30))
        self.reset_analysis_btn.setMaximumSize(QSize(30, 30))
        font2 = QFont()
        font2.setFamilies([u"Segoe UI"])
        font2.setPointSize(5)
        self.reset_analysis_btn.setFont(font2)
        self.reset_analysis_btn.setMouseTracking(True)
        self.reset_analysis_btn.setLayoutDirection(Qt.LeftToRight)
        self.reset_analysis_btn.setAutoFillBackground(False)
        self.reset_analysis_btn.setStyleSheet(u"QPushButton{\n"
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
        icon.addFile(u":/img/img/reload.png", QSize(), QIcon.Normal, QIcon.Off)
        self.reset_analysis_btn.setIcon(icon)
        self.reset_analysis_btn.setIconSize(QSize(25, 25))
        self.reset_analysis_btn.setAutoRepeat(False)
        self.reset_analysis_btn.setAutoExclusive(False)
        self.reset_analysis_btn.setAutoDefault(False)
        self.reset_analysis_btn.setFlat(False)

        self.horizontalLayout_9.addWidget(self.reset_analysis_btn)

        self.import_btn = QPushButton(self.file_ctrls)
        self.import_btn.setObjectName(u"import_btn")
        sizePolicy1.setHeightForWidth(self.import_btn.sizePolicy().hasHeightForWidth())
        self.import_btn.setSizePolicy(sizePolicy1)
        self.import_btn.setMinimumSize(QSize(30, 30))
        self.import_btn.setMaximumSize(QSize(30, 30))
        self.import_btn.setFont(font2)
        self.import_btn.setMouseTracking(True)
        self.import_btn.setLayoutDirection(Qt.LeftToRight)
        self.import_btn.setAutoFillBackground(False)
        self.import_btn.setStyleSheet(u"QPushButton{\n"
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
        icon1.addFile(u":/img/img/folder.png", QSize(), QIcon.Normal, QIcon.Off)
        self.import_btn.setIcon(icon1)
        self.import_btn.setIconSize(QSize(23, 23))
        self.import_btn.setAutoRepeat(False)
        self.import_btn.setAutoExclusive(False)
        self.import_btn.setAutoDefault(False)
        self.import_btn.setFlat(False)

        self.horizontalLayout_9.addWidget(self.import_btn)

        self.export_btn = QPushButton(self.file_ctrls)
        self.export_btn.setObjectName(u"export_btn")
        sizePolicy1.setHeightForWidth(self.export_btn.sizePolicy().hasHeightForWidth())
        self.export_btn.setSizePolicy(sizePolicy1)
        self.export_btn.setMinimumSize(QSize(30, 30))
        self.export_btn.setMaximumSize(QSize(30, 30))
        self.export_btn.setFont(font2)
        self.export_btn.setMouseTracking(True)
        self.export_btn.setLayoutDirection(Qt.LeftToRight)
        self.export_btn.setAutoFillBackground(False)
        self.export_btn.setStyleSheet(u"QPushButton{\n"
"	border: none;\n"
"	background: none;\n"
"}\n"
"\n"
"QPushButton::hover{\n"
"	background: white;\n"
"	border: 1px raised;\n"
"	border-radius: 10px;\n"
"}")
        icon2 = QIcon()
        icon2.addFile(u":/img/img/save.png", QSize(), QIcon.Normal, QIcon.Off)
        self.export_btn.setIcon(icon2)
        self.export_btn.setIconSize(QSize(25, 25))
        self.export_btn.setAutoRepeat(False)
        self.export_btn.setAutoExclusive(False)
        self.export_btn.setAutoDefault(False)
        self.export_btn.setFlat(False)

        self.horizontalLayout_9.addWidget(self.export_btn)


        self.verticalLayout_3.addWidget(self.file_ctrls)

        self.verticalSpacer = QSpacerItem(20, 30, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_3.addItem(self.verticalSpacer)


        self.horizontalLayout.addWidget(self.frame)


        self.verticalLayout_4.addLayout(self.horizontalLayout)

        self.bottom_horizontal = QHBoxLayout()
        self.bottom_horizontal.setObjectName(u"bottom_horizontal")
        self.SOI_Frame = QFrame(FormAnalysis)
        self.SOI_Frame.setObjectName(u"SOI_Frame")
        sizePolicy2 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.SOI_Frame.sizePolicy().hasHeightForWidth())
        self.SOI_Frame.setSizePolicy(sizePolicy2)
        self.SOI_Frame.setMinimumSize(QSize(0, 300))
        self.SOI_Frame.setMaximumSize(QSize(16777215, 500))
        self.SOI_Frame.setFont(font1)
        self.horizontalLayout_3 = QHBoxLayout(self.SOI_Frame)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.SOI = QFrame(self.SOI_Frame)
        self.SOI.setObjectName(u"SOI")
        sizePolicy2.setHeightForWidth(self.SOI.sizePolicy().hasHeightForWidth())
        self.SOI.setSizePolicy(sizePolicy2)
        self.SOI.setMinimumSize(QSize(250, 150))
        self.SOI.setMaximumSize(QSize(10000, 10000))
        self.SOI.setFrameShape(QFrame.StyledPanel)
        self.SOI.setFrameShadow(QFrame.Raised)
        self.verticalLayout_8 = QVBoxLayout(self.SOI)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")
        self.horizontalSpacer_4 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.verticalLayout_8.addItem(self.horizontalSpacer_4)

        self.verticalSpacer_4 = QSpacerItem(10, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)

        self.verticalLayout_8.addItem(self.verticalSpacer_4)


        self.horizontalLayout_3.addWidget(self.SOI)

        self.analysis_table = QFrame(self.SOI_Frame)
        self.analysis_table.setObjectName(u"analysis_table")
        sizePolicy2.setHeightForWidth(self.analysis_table.sizePolicy().hasHeightForWidth())
        self.analysis_table.setSizePolicy(sizePolicy2)
        self.analysis_table.setMinimumSize(QSize(300, 200))
        self.analysis_table.setMaximumSize(QSize(900, 360))
        self.verticalLayout_5 = QVBoxLayout(self.analysis_table)
        self.verticalLayout_5.setSpacing(3)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.analysis_table)
        self.label.setObjectName(u"label")
        self.label.setMinimumSize(QSize(0, 30))
        self.label.setMaximumSize(QSize(16777214, 30))
        font3 = QFont()
        font3.setFamilies([u"Segoe UI"])
        font3.setPointSize(11)
        font3.setBold(False)
        self.label.setFont(font3)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setIndent(30)

        self.verticalLayout_5.addWidget(self.label)

        self.horizontalFrame = QFrame(self.analysis_table)
        self.horizontalFrame.setObjectName(u"horizontalFrame")
        self.horizontalFrame.setMinimumSize(QSize(0, 50))
        self.horizontalFrame.setMaximumSize(QSize(16777215, 50))
        self.horizontalLayout_2 = QHBoxLayout(self.horizontalFrame)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(11, 0, 11, 0)
        self.groupBox_3 = QGroupBox(self.horizontalFrame)
        self.groupBox_3.setObjectName(u"groupBox_3")
        self.groupBox_3.setMaximumSize(QSize(175, 40))
        self.horizontalLayout_4 = QHBoxLayout(self.groupBox_3)
        self.horizontalLayout_4.setSpacing(5)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(5, 0, 5, 0)
        self.segment_A = QCheckBox(self.groupBox_3)
        self.segment_A.setObjectName(u"segment_A")
        self.segment_A.setMinimumSize(QSize(0, 15))
        self.segment_A.setMaximumSize(QSize(37, 16777215))
        font4 = QFont()
        font4.setFamilies([u"Segoe UI"])
        font4.setPointSize(9)
        font4.setBold(True)
        self.segment_A.setFont(font4)
        self.segment_A.setStyleSheet(u"QCheckBox{\n"
"	color: black;\n"
"	background:white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_A.setChecked(True)

        self.horizontalLayout_4.addWidget(self.segment_A)

        self.segment_B = QCheckBox(self.groupBox_3)
        self.segment_B.setObjectName(u"segment_B")
        self.segment_B.setMinimumSize(QSize(0, 15))
        self.segment_B.setMaximumSize(QSize(37, 16777215))
        self.segment_B.setFont(font4)
        self.segment_B.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(255, 0, 81);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_B.setChecked(True)

        self.horizontalLayout_4.addWidget(self.segment_B)

        self.segment_C = QCheckBox(self.groupBox_3)
        self.segment_C.setObjectName(u"segment_C")
        self.segment_C.setMinimumSize(QSize(0, 15))
        self.segment_C.setMaximumSize(QSize(37, 16777215))
        self.segment_C.setFont(font4)
        self.segment_C.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 174, 255);\n"
"	background: white;\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	border-radius: 3px;\n"
"}")
        self.segment_C.setChecked(True)

        self.horizontalLayout_4.addWidget(self.segment_C)

        self.segment_D = QCheckBox(self.groupBox_3)
        self.segment_D.setObjectName(u"segment_D")
        self.segment_D.setMinimumSize(QSize(0, 15))
        self.segment_D.setMaximumSize(QSize(37, 16777215))
        self.segment_D.setFont(font4)
        self.segment_D.setStyleSheet(u"QCheckBox{\n"
"	color: rgb(0, 230, 65);\n"
"	border: 1px solid rgb(171, 171, 171); \n"
"	background:white;\n"
"	border-radius: 3px;\n"
"}")
        self.segment_D.setChecked(True)

        self.horizontalLayout_4.addWidget(self.segment_D)


        self.horizontalLayout_2.addWidget(self.groupBox_3)

        self.cursor_ctrls = QGroupBox(self.horizontalFrame)
        self.cursor_ctrls.setObjectName(u"cursor_ctrls")
        self.cursor_ctrls.setMinimumSize(QSize(220, 0))
        self.cursor_ctrls.setMaximumSize(QSize(220, 40))
        self.horizontalLayout_5 = QHBoxLayout(self.cursor_ctrls)
        self.horizontalLayout_5.setSpacing(5)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setContentsMargins(5, 0, 5, 0)
        self.assoc_cursors = QCheckBox(self.cursor_ctrls)
        self.assoc_cursors.setObjectName(u"assoc_cursors")

        self.horizontalLayout_5.addWidget(self.assoc_cursors, 0, Qt.AlignHCenter)

        self.dissoc_cursors = QCheckBox(self.cursor_ctrls)
        self.dissoc_cursors.setObjectName(u"dissoc_cursors")

        self.horizontalLayout_5.addWidget(self.dissoc_cursors, 0, Qt.AlignHCenter)


        self.horizontalLayout_2.addWidget(self.cursor_ctrls)

        self.horizontalSpacer_2 = QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.horizontalLayout_2.addItem(self.horizontalSpacer_2)

        self.seg_select = QComboBox(self.horizontalFrame)
        self.seg_select.setObjectName(u"seg_select")
        self.seg_select.setMinimumSize(QSize(200, 25))
        self.seg_select.setMaximumSize(QSize(200, 30))

        self.horizontalLayout_2.addWidget(self.seg_select, 0, Qt.AlignLeft)


        self.verticalLayout_5.addWidget(self.horizontalFrame)

        self.frame_2 = QFrame(self.analysis_table)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setMinimumSize(QSize(0, 40))
        self.frame_2.setMaximumSize(QSize(16777215, 40))
        self.horizontalLayout_8 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_8.setSpacing(11)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(11, 0, 11, 0)
        self.label_2 = QLabel(self.frame_2)
        self.label_2.setObjectName(u"label_2")
        self.label_2.setMaximumSize(QSize(60, 16777215))

        self.horizontalLayout_8.addWidget(self.label_2)

        self.current_note = QLineEdit(self.frame_2)
        self.current_note.setObjectName(u"current_note")
        self.current_note.setEnabled(True)
        sizePolicy.setHeightForWidth(self.current_note.sizePolicy().hasHeightForWidth())
        self.current_note.setSizePolicy(sizePolicy)
        self.current_note.setMinimumSize(QSize(500, 25))
        self.current_note.setMaximumSize(QSize(500, 25))
        font5 = QFont()
        font5.setFamilies([u"Segoe UI"])
        font5.setPointSize(9)
        self.current_note.setFont(font5)
        self.current_note.setFocusPolicy(Qt.ClickFocus)
        self.current_note.setStyleSheet(u"\n"
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

        self.horizontalLayout_8.addWidget(self.current_note)


        self.verticalLayout_5.addWidget(self.frame_2, 0, Qt.AlignHCenter)

        self.scrollArea = QScrollArea(self.analysis_table)
        self.scrollArea.setObjectName(u"scrollArea")
        sizePolicy3 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.scrollArea.sizePolicy().hasHeightForWidth())
        self.scrollArea.setSizePolicy(sizePolicy3)
        self.scrollArea.setMaximumSize(QSize(16777215, 400))
        self.scrollArea.setFrameShape(QFrame.NoFrame)
        self.scrollArea.setFrameShadow(QFrame.Plain)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setWidgetResizable(True)
        self.scrollAreaWidgetContents = QWidget()
        self.scrollAreaWidgetContents.setObjectName(u"scrollAreaWidgetContents")
        self.scrollAreaWidgetContents.setGeometry(QRect(0, 0, 716, 231))
        self.scrollAreaWidgetContents.setMaximumSize(QSize(16777215, 600))
        self.verticalLayout = QVBoxLayout(self.scrollAreaWidgetContents)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.data_table = QTableWidget(self.scrollAreaWidgetContents)
        if (self.data_table.columnCount() < 9):
            self.data_table.setColumnCount(9)
        font6 = QFont()
        font6.setPointSize(8)
        font6.setBold(False)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setFont(font6);
        self.data_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        font7 = QFont()
        font7.setPointSize(8)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font7);
        self.data_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        __qtablewidgetitem2.setFont(font7);
        self.data_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setFont(font7);
        self.data_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        __qtablewidgetitem4.setFont(font1);
        self.data_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setFont(font1);
        self.data_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        __qtablewidgetitem6.setFont(font1);
        self.data_table.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        __qtablewidgetitem7.setFont(font1);
        self.data_table.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        __qtablewidgetitem8.setFont(font1);
        self.data_table.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        if (self.data_table.rowCount() < 4):
            self.data_table.setRowCount(4)
        __qtablewidgetitem9 = QTableWidgetItem()
        __qtablewidgetitem9.setFont(font1);
        self.data_table.setVerticalHeaderItem(0, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        __qtablewidgetitem10.setFont(font1);
        self.data_table.setVerticalHeaderItem(1, __qtablewidgetitem10)
        __qtablewidgetitem11 = QTableWidgetItem()
        __qtablewidgetitem11.setFont(font1);
        self.data_table.setVerticalHeaderItem(2, __qtablewidgetitem11)
        __qtablewidgetitem12 = QTableWidgetItem()
        __qtablewidgetitem12.setFont(font1);
        self.data_table.setVerticalHeaderItem(3, __qtablewidgetitem12)
        __qtablewidgetitem13 = QTableWidgetItem()
        __qtablewidgetitem13.setTextAlignment(Qt.AlignCenter);
        self.data_table.setItem(0, 0, __qtablewidgetitem13)
        self.data_table.setObjectName(u"data_table")
        sizePolicy2.setHeightForWidth(self.data_table.sizePolicy().hasHeightForWidth())
        self.data_table.setSizePolicy(sizePolicy2)
        self.data_table.setMinimumSize(QSize(375, 175))
        self.data_table.setMaximumSize(QSize(10000, 400))
        self.data_table.setFont(font1)
        self.data_table.setFocusPolicy(Qt.ClickFocus)
        self.data_table.setFrameShape(QFrame.NoFrame)
        self.data_table.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.data_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.data_table.setShowGrid(True)
        self.data_table.setGridStyle(Qt.DashLine)
        self.data_table.setWordWrap(True)
        self.data_table.setRowCount(4)
        self.data_table.setColumnCount(9)
        self.data_table.horizontalHeader().setVisible(True)
        self.data_table.horizontalHeader().setCascadingSectionResizes(True)
        self.data_table.horizontalHeader().setMinimumSectionSize(70)
        self.data_table.horizontalHeader().setDefaultSectionSize(70)
        self.data_table.horizontalHeader().setHighlightSections(True)
        self.data_table.horizontalHeader().setProperty("showSortIndicator", False)
        self.data_table.horizontalHeader().setStretchLastSection(True)
        self.data_table.verticalHeader().setVisible(True)
        self.data_table.verticalHeader().setCascadingSectionResizes(True)
        self.data_table.verticalHeader().setMinimumSectionSize(30)
        self.data_table.verticalHeader().setDefaultSectionSize(40)
        self.data_table.verticalHeader().setHighlightSections(False)
        self.data_table.verticalHeader().setProperty("showSortIndicator", False)
        self.data_table.verticalHeader().setStretchLastSection(False)

        self.verticalLayout.addWidget(self.data_table)

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        self.verticalLayout_5.addWidget(self.scrollArea)


        self.horizontalLayout_3.addWidget(self.analysis_table)


        self.bottom_horizontal.addWidget(self.SOI_Frame)


        self.verticalLayout_4.addLayout(self.bottom_horizontal)


        self.retranslateUi(FormAnalysis)

        self.reset_analysis_btn.setDefault(False)
        self.import_btn.setDefault(False)
        self.export_btn.setDefault(False)


        QMetaObject.connectSlotsByName(FormAnalysis)
    # setupUi

    def retranslateUi(self, FormAnalysis):
        FormAnalysis.setWindowTitle(QCoreApplication.translate("FormAnalysis", u"Form", None))
        self.label_cur_info.setText("")
        self.groupBox.setTitle(QCoreApplication.translate("FormAnalysis", u"Stacked Graph", None))
        self.radio_a.setText(QCoreApplication.translate("FormAnalysis", u"Channel A", None))
        self.radio_b.setText(QCoreApplication.translate("FormAnalysis", u"Channel B", None))
        self.radio_c.setText(QCoreApplication.translate("FormAnalysis", u"Channel C", None))
        self.radio_d.setText(QCoreApplication.translate("FormAnalysis", u"Channel D", None))
#if QT_CONFIG(tooltip)
        self.fit_wizard_btn.setToolTip(QCoreApplication.translate("FormAnalysis", u"Launch KD Wizard", None))
#endif // QT_CONFIG(tooltip)
        self.fit_wizard_btn.setText(QCoreApplication.translate("FormAnalysis", u"Fitting Wizard", None))
#if QT_CONFIG(tooltip)
        self.kin_wizard_btn.setToolTip(QCoreApplication.translate("FormAnalysis", u"Launch Kinetic Wizard", None))
#endif // QT_CONFIG(tooltip)
        self.kin_wizard_btn.setText(QCoreApplication.translate("FormAnalysis", u"Kinetic Wizard", None))
#if QT_CONFIG(tooltip)
        self.reset_analysis_btn.setToolTip(QCoreApplication.translate("FormAnalysis", u"Clear All Data", None))
#endif // QT_CONFIG(tooltip)
        self.reset_analysis_btn.setText("")
#if QT_CONFIG(tooltip)
        self.import_btn.setToolTip(QCoreApplication.translate("FormAnalysis", u"Import Raw Data", None))
#endif // QT_CONFIG(tooltip)
        self.import_btn.setText("")
#if QT_CONFIG(tooltip)
        self.export_btn.setToolTip(QCoreApplication.translate("FormAnalysis", u"Export Analysis Data", None))
#endif // QT_CONFIG(tooltip)
        self.export_btn.setText("")
        self.label.setText(QCoreApplication.translate("FormAnalysis", u"Analysis Cycle Editor", None))
        self.groupBox_3.setTitle(QCoreApplication.translate("FormAnalysis", u"Display", None))
        self.segment_A.setText(QCoreApplication.translate("FormAnalysis", u"A  ", None))
        self.segment_B.setText(QCoreApplication.translate("FormAnalysis", u"B  ", None))
        self.segment_C.setText(QCoreApplication.translate("FormAnalysis", u"C  ", None))
        self.segment_D.setText(QCoreApplication.translate("FormAnalysis", u"D  ", None))
        self.cursor_ctrls.setTitle(QCoreApplication.translate("FormAnalysis", u"Cursors", None))
        self.assoc_cursors.setText(QCoreApplication.translate("FormAnalysis", u"Association", None))
        self.dissoc_cursors.setText(QCoreApplication.translate("FormAnalysis", u"Dissociation", None))
        self.label_2.setText(QCoreApplication.translate("FormAnalysis", u"Note:", None))
        self.current_note.setText("")
        ___qtablewidgetitem = self.data_table.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("FormAnalysis", u"Conc'n\n"
"(nM)", None));
        ___qtablewidgetitem1 = self.data_table.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("FormAnalysis", u"Assoc.\n"
"Shift (RU)", None));
        ___qtablewidgetitem2 = self.data_table.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("FormAnalysis", u"Assoc.\n"
"Start (s)", None));
        ___qtablewidgetitem3 = self.data_table.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("FormAnalysis", u"Assoc.\n"
"End (s)", None));
        ___qtablewidgetitem4 = self.data_table.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("FormAnalysis", u"Dissoc.\n"
"Shift (RU)", None));
        ___qtablewidgetitem5 = self.data_table.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("FormAnalysis", u"Dissoc.\n"
"Start (s)", None));
        ___qtablewidgetitem6 = self.data_table.horizontalHeaderItem(6)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("FormAnalysis", u"Dissoc.\n"
"End (s)", None));
        ___qtablewidgetitem7 = self.data_table.horizontalHeaderItem(7)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("FormAnalysis", u"Global\n"
"Start (s)", None));
        ___qtablewidgetitem8 = self.data_table.horizontalHeaderItem(8)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("FormAnalysis", u"Reference\n"
"Channel", None));
        ___qtablewidgetitem9 = self.data_table.verticalHeaderItem(0)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("FormAnalysis", u"Ch A", None));
        ___qtablewidgetitem10 = self.data_table.verticalHeaderItem(1)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("FormAnalysis", u"Ch B", None));
        ___qtablewidgetitem11 = self.data_table.verticalHeaderItem(2)
        ___qtablewidgetitem11.setText(QCoreApplication.translate("FormAnalysis", u"Ch C", None));
        ___qtablewidgetitem12 = self.data_table.verticalHeaderItem(3)
        ___qtablewidgetitem12.setText(QCoreApplication.translate("FormAnalysis", u"Ch D", None));

        __sortingEnabled = self.data_table.isSortingEnabled()
        self.data_table.setSortingEnabled(False)
        self.data_table.setSortingEnabled(__sortingEnabled)

    # retranslateUi

