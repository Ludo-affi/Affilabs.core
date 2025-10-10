################################################################################
## Form generated from reading UI file 'processing.ui'
##
## Created by: Qt User Interface Compiler version 6.6.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QCheckBox,
    QFrame,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class Ui_Processing:
    def setupUi(self, Processing):
        if not Processing.objectName():
            Processing.setObjectName("Processing")
        Processing.resize(1027, 839)
        font = QFont()
        font.setFamilies(["Segoe UI"])
        font.setPointSize(9)
        Processing.setFont(font)
        Processing.setMouseTracking(True)
        Processing.setFocusPolicy(Qt.StrongFocus)
        self.horizontalLayout = QHBoxLayout(Processing)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.verticalLayout_5 = QVBoxLayout()
        self.verticalLayout_5.setSpacing(0)
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.verticalLayout_5.setContentsMargins(11, 11, 11, 11)
        self.full_segment = QFrame(Processing)
        self.full_segment.setObjectName("full_segment")
        self.full_segment.setMinimumSize(QSize(200, 250))
        self.full_segment.setMaximumSize(QSize(10000, 10000))
        self.full_segment.setMouseTracking(True)
        self.full_segment.setFrameShape(QFrame.StyledPanel)
        self.full_segment.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.full_segment)
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_2 = QSpacerItem(
            429, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_3.addItem(self.horizontalSpacer_2)

        self.verticalSpacer = QSpacerItem(
            20, 393, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.horizontalLayout_3.addItem(self.verticalSpacer)

        self.verticalLayout_5.addWidget(self.full_segment)

        self.SOI = QFrame(Processing)
        self.SOI.setObjectName("SOI")
        self.SOI.setMinimumSize(QSize(200, 250))
        self.SOI.setMaximumSize(QSize(10000, 10000))
        self.SOI.setFrameShape(QFrame.StyledPanel)
        self.SOI.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.SOI)
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.horizontalSpacer_4 = QSpacerItem(
            429, 20, QSizePolicy.Expanding, QSizePolicy.Minimum
        )

        self.horizontalLayout_4.addItem(self.horizontalSpacer_4)

        self.verticalSpacer_2 = QSpacerItem(
            20, 392, QSizePolicy.Minimum, QSizePolicy.Expanding
        )

        self.horizontalLayout_4.addItem(self.verticalSpacer_2)

        self.verticalLayout_5.addWidget(self.SOI)

        self.horizontalLayout.addLayout(self.verticalLayout_5)

        self.controls = QVBoxLayout()
        self.controls.setSpacing(0)
        self.controls.setObjectName("controls")
        self.label_3 = QLabel(Processing)
        self.label_3.setObjectName("label_3")
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy)
        self.label_3.setMinimumSize(QSize(0, 30))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(11)
        self.label_3.setFont(font1)
        self.label_3.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.controls.addWidget(self.label_3)

        self.sensorgram_controls = QFrame(Processing)
        self.sensorgram_controls.setObjectName("sensorgram_controls")
        sizePolicy1 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.sensorgram_controls.sizePolicy().hasHeightForWidth()
        )
        self.sensorgram_controls.setSizePolicy(sizePolicy1)
        self.sensorgram_controls.setMinimumSize(QSize(500, 130))
        self.sensorgram_controls.setMaximumSize(QSize(510, 130))
        self.sensorgram_controls.setFont(font)
        self.sensorgram_controls.setMouseTracking(True)
        self.sensorgram_controls.setFocusPolicy(Qt.StrongFocus)
        self.sensorgram_controls.setFrameShape(QFrame.StyledPanel)
        self.sensorgram_controls.setFrameShadow(QFrame.Raised)
        self.groupBox = QGroupBox(self.sensorgram_controls)
        self.groupBox.setObjectName("groupBox")
        self.groupBox.setGeometry(QRect(10, 0, 71, 121))
        self.segment_A = QCheckBox(self.groupBox)
        self.segment_A.setObjectName("segment_A")
        self.segment_A.setGeometry(QRect(15, 30, 38, 16))
        font2 = QFont()
        font2.setFamilies(["Segoe UI"])
        font2.setPointSize(9)
        font2.setBold(True)
        self.segment_A.setFont(font2)
        self.segment_A.setStyleSheet(
            "QCheckBox{\n"
            "	color: black;\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.segment_A.setChecked(True)
        self.segment_B = QCheckBox(self.groupBox)
        self.segment_B.setObjectName("segment_B")
        self.segment_B.setGeometry(QRect(15, 50, 38, 16))
        self.segment_B.setFont(font2)
        self.segment_B.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(255, 0, 81);\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.segment_B.setChecked(True)
        self.segment_C = QCheckBox(self.groupBox)
        self.segment_C.setObjectName("segment_C")
        self.segment_C.setGeometry(QRect(15, 70, 38, 16))
        self.segment_C.setFont(font2)
        self.segment_C.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(0, 174, 255);\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.segment_C.setChecked(True)
        self.segment_D = QCheckBox(self.groupBox)
        self.segment_D.setObjectName("segment_D")
        self.segment_D.setGeometry(QRect(15, 90, 38, 16))
        self.segment_D.setFont(font2)
        self.segment_D.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(0, 230, 65);\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	background: white;\n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.segment_D.setChecked(True)
        self.reference_channel_btn = QPushButton(self.sensorgram_controls)
        self.reference_channel_btn.setObjectName("reference_channel_btn")
        self.reference_channel_btn.setGeometry(QRect(360, 10, 131, 45))
        sizePolicy2 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(
            self.reference_channel_btn.sizePolicy().hasHeightForWidth()
        )
        self.reference_channel_btn.setSizePolicy(sizePolicy2)
        self.reference_channel_btn.setFont(font)
        self.reference_channel_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}"
        )
        self.groupBox_6 = QGroupBox(self.sensorgram_controls)
        self.groupBox_6.setObjectName("groupBox_6")
        self.groupBox_6.setGeometry(QRect(90, 0, 251, 121))
        self.left_cursor_time = QLineEdit(self.groupBox_6)
        self.left_cursor_time.setObjectName("left_cursor_time")
        self.left_cursor_time.setGeometry(QRect(20, 50, 71, 25))
        self.left_cursor_time.setFocusPolicy(Qt.ClickFocus)
        self.left_cursor_time.setStyleSheet(
            "\n"
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
            "}"
        )
        self.right_cursor_time = QLineEdit(self.groupBox_6)
        self.right_cursor_time.setObjectName("right_cursor_time")
        self.right_cursor_time.setGeometry(QRect(140, 50, 71, 25))
        self.right_cursor_time.setFocusPolicy(Qt.ClickFocus)
        self.right_cursor_time.setStyleSheet(
            "\n"
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
            "}"
        )
        self.label_14 = QLabel(self.groupBox_6)
        self.label_14.setObjectName("label_14")
        self.label_14.setGeometry(QRect(10, 30, 101, 16))
        self.label_16 = QLabel(self.groupBox_6)
        self.label_16.setObjectName("label_16")
        self.label_16.setGeometry(QRect(130, 30, 101, 16))
        self.label_9 = QLabel(self.groupBox_6)
        self.label_9.setObjectName("label_9")
        self.label_9.setGeometry(QRect(90, 50, 16, 25))
        self.label_9.setAlignment(Qt.AlignCenter)
        self.label_10 = QLabel(self.groupBox_6)
        self.label_10.setObjectName("label_10")
        self.label_10.setGeometry(QRect(210, 50, 16, 25))
        self.label_10.setAlignment(Qt.AlignCenter)
        self.exp_clock = QLabel(self.groupBox_6)
        self.exp_clock.setObjectName("exp_clock")
        self.exp_clock.setGeometry(QRect(130, 90, 91, 16))
        self.exp_clock.setStyleSheet("")
        self.exp_clock.setAlignment(Qt.AlignCenter)
        self.label_19 = QLabel(self.groupBox_6)
        self.label_19.setObjectName("label_19")
        self.label_19.setGeometry(QRect(10, 90, 121, 16))
        self.label_6 = QLabel(self.groupBox_6)
        self.label_6.setObjectName("label_6")
        self.label_6.setGeometry(QRect(10, 50, 8, 25))
        font3 = QFont()
        font3.setFamilies(["Segoe UI Black"])
        font3.setPointSize(8)
        font3.setBold(False)
        self.label_6.setFont(font3)
        self.label_6.setStyleSheet(
            "background: yellow;\n"
            "border-radius: 2px;\n"
            "border: 2px solid rgb(100, 100, 100);"
        )
        self.label_6.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.label_7 = QLabel(self.groupBox_6)
        self.label_7.setObjectName("label_7")
        self.label_7.setGeometry(QRect(130, 50, 8, 25))
        self.label_7.setFont(font3)
        self.label_7.setStyleSheet(
            "background: red;\n"
            "border-radius: 2px;\n"
            "border: 2px solid rgb(100, 100, 100);"
        )
        self.label_7.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        self.reset_segment_btn = QPushButton(self.sensorgram_controls)
        self.reset_segment_btn.setObjectName("reset_segment_btn")
        self.reset_segment_btn.setGeometry(QRect(350, 80, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.reset_segment_btn.sizePolicy().hasHeightForWidth()
        )
        self.reset_segment_btn.setSizePolicy(sizePolicy2)
        self.reset_segment_btn.setMinimumSize(QSize(30, 30))
        self.reset_segment_btn.setMaximumSize(QSize(30, 30))
        font4 = QFont()
        font4.setFamilies(["Segoe UI"])
        font4.setPointSize(5)
        self.reset_segment_btn.setFont(font4)
        self.reset_segment_btn.setMouseTracking(True)
        self.reset_segment_btn.setLayoutDirection(Qt.LeftToRight)
        self.reset_segment_btn.setAutoFillBackground(False)
        self.reset_segment_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon = QIcon()
        icon.addFile(":/img/img/reload.png", QSize(), QIcon.Normal, QIcon.Off)
        self.reset_segment_btn.setIcon(icon)
        self.reset_segment_btn.setIconSize(QSize(25, 25))
        self.reset_segment_btn.setAutoRepeat(False)
        self.reset_segment_btn.setAutoExclusive(False)
        self.reset_segment_btn.setAutoDefault(False)
        self.reset_segment_btn.setFlat(False)
        self.export_raw_data_btn = QPushButton(self.sensorgram_controls)
        self.export_raw_data_btn.setObjectName("export_raw_data_btn")
        self.export_raw_data_btn.setGeometry(QRect(470, 80, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.export_raw_data_btn.sizePolicy().hasHeightForWidth()
        )
        self.export_raw_data_btn.setSizePolicy(sizePolicy2)
        self.export_raw_data_btn.setMinimumSize(QSize(30, 30))
        self.export_raw_data_btn.setMaximumSize(QSize(30, 30))
        self.export_raw_data_btn.setFont(font4)
        self.export_raw_data_btn.setMouseTracking(True)
        self.export_raw_data_btn.setLayoutDirection(Qt.LeftToRight)
        self.export_raw_data_btn.setAutoFillBackground(False)
        self.export_raw_data_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon1 = QIcon()
        icon1.addFile(":/img/img/save.png", QSize(), QIcon.Normal, QIcon.Off)
        self.export_raw_data_btn.setIcon(icon1)
        self.export_raw_data_btn.setIconSize(QSize(25, 25))
        self.export_raw_data_btn.setAutoRepeat(False)
        self.export_raw_data_btn.setAutoExclusive(False)
        self.export_raw_data_btn.setAutoDefault(False)
        self.export_raw_data_btn.setFlat(False)
        self.import_raw_data_btn = QPushButton(self.sensorgram_controls)
        self.import_raw_data_btn.setObjectName("import_raw_data_btn")
        self.import_raw_data_btn.setGeometry(QRect(430, 80, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.import_raw_data_btn.sizePolicy().hasHeightForWidth()
        )
        self.import_raw_data_btn.setSizePolicy(sizePolicy2)
        self.import_raw_data_btn.setMinimumSize(QSize(30, 30))
        self.import_raw_data_btn.setMaximumSize(QSize(30, 30))
        self.import_raw_data_btn.setFont(font4)
        self.import_raw_data_btn.setMouseTracking(True)
        self.import_raw_data_btn.setLayoutDirection(Qt.LeftToRight)
        self.import_raw_data_btn.setAutoFillBackground(False)
        self.import_raw_data_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon2 = QIcon()
        icon2.addFile(":/img/img/folder.png", QSize(), QIcon.Normal, QIcon.Off)
        self.import_raw_data_btn.setIcon(icon2)
        self.import_raw_data_btn.setIconSize(QSize(23, 23))
        self.import_raw_data_btn.setAutoRepeat(False)
        self.import_raw_data_btn.setAutoExclusive(False)
        self.import_raw_data_btn.setAutoDefault(False)
        self.import_raw_data_btn.setFlat(False)
        self.import_sens_btn = QPushButton(self.sensorgram_controls)
        self.import_sens_btn.setObjectName("import_sens_btn")
        self.import_sens_btn.setGeometry(QRect(390, 80, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.import_sens_btn.sizePolicy().hasHeightForWidth()
        )
        self.import_sens_btn.setSizePolicy(sizePolicy2)
        self.import_sens_btn.setMinimumSize(QSize(30, 30))
        self.import_sens_btn.setMaximumSize(QSize(30, 30))
        self.import_sens_btn.setFont(font4)
        self.import_sens_btn.setMouseTracking(True)
        self.import_sens_btn.setLayoutDirection(Qt.LeftToRight)
        self.import_sens_btn.setAutoFillBackground(False)
        self.import_sens_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon3 = QIcon()
        icon3.addFile(":/img/img/import.png", QSize(), QIcon.Normal, QIcon.Off)
        self.import_sens_btn.setIcon(icon3)
        self.import_sens_btn.setIconSize(QSize(25, 25))
        self.import_sens_btn.setAutoRepeat(False)
        self.import_sens_btn.setAutoExclusive(False)
        self.import_sens_btn.setAutoDefault(False)
        self.import_sens_btn.setFlat(False)

        self.controls.addWidget(self.sensorgram_controls)

        self.line = QFrame(Processing)
        self.line.setObjectName("line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.controls.addWidget(self.line)

        self.label_4 = QLabel(Processing)
        self.label_4.setObjectName("label_4")
        sizePolicy.setHeightForWidth(self.label_4.sizePolicy().hasHeightForWidth())
        self.label_4.setSizePolicy(sizePolicy)
        self.label_4.setMinimumSize(QSize(0, 30))
        self.label_4.setFont(font1)
        self.label_4.setFrameShape(QFrame.NoFrame)
        self.label_4.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

        self.controls.addWidget(self.label_4)

        self.frame_2 = QFrame(Processing)
        self.frame_2.setObjectName("frame_2")
        sizePolicy1.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy1)
        self.frame_2.setMinimumSize(QSize(500, 160))
        self.frame_2.setMaximumSize(QSize(510, 160))
        self.frame_2.setFont(font)
        self.curr_seg_box = QFrame(self.frame_2)
        self.curr_seg_box.setObjectName("curr_seg_box")
        self.curr_seg_box.setGeometry(QRect(0, 0, 511, 160))
        self.curr_seg_box.setMinimumSize(QSize(0, 160))
        self.curr_seg_box.setMaximumSize(QSize(16777215, 160))
        self.groupBox_2 = QGroupBox(self.curr_seg_box)
        self.groupBox_2.setObjectName("groupBox_2")
        self.groupBox_2.setGeometry(QRect(10, 0, 71, 151))
        self.SOI_A = QCheckBox(self.groupBox_2)
        self.SOI_A.setObjectName("SOI_A")
        self.SOI_A.setGeometry(QRect(15, 30, 38, 16))
        self.SOI_A.setFont(font2)
        self.SOI_A.setStyleSheet(
            "QCheckBox{\n"
            "	color: black;\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.SOI_A.setChecked(True)
        self.SOI_B = QCheckBox(self.groupBox_2)
        self.SOI_B.setObjectName("SOI_B")
        self.SOI_B.setGeometry(QRect(15, 50, 38, 16))
        self.SOI_B.setFont(font2)
        self.SOI_B.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(255, 0, 81);\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.SOI_B.setChecked(True)
        self.SOI_C = QCheckBox(self.groupBox_2)
        self.SOI_C.setObjectName("SOI_C")
        self.SOI_C.setGeometry(QRect(15, 70, 38, 16))
        self.SOI_C.setFont(font2)
        self.SOI_C.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(0, 174, 255);\n"
            "	background: white;\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.SOI_C.setChecked(True)
        self.SOI_D = QCheckBox(self.groupBox_2)
        self.SOI_D.setObjectName("SOI_D")
        self.SOI_D.setGeometry(QRect(15, 90, 38, 16))
        self.SOI_D.setFont(font2)
        self.SOI_D.setStyleSheet(
            "QCheckBox{\n"
            "	color: rgb(0, 230, 65);\n"
            "	border: 1px solid rgb(171, 171, 171); \n"
            "	background: white;\n"
            "	border-radius: 3px;\n"
            "}"
        )
        self.SOI_D.setChecked(True)
        self.groupBox_3 = QGroupBox(self.curr_seg_box)
        self.groupBox_3.setObjectName("groupBox_3")
        self.groupBox_3.setGeometry(QRect(90, 0, 181, 151))
        self.unit_a = QLabel(self.groupBox_3)
        self.unit_a.setObjectName("unit_a")
        self.unit_a.setGeometry(QRect(150, 25, 31, 25))
        self.unit_a.setAlignment(Qt.AlignCenter)
        self.unit_a.setMargin(2)
        self.unit_b = QLabel(self.groupBox_3)
        self.unit_b.setObjectName("unit_b")
        self.unit_b.setGeometry(QRect(150, 55, 31, 25))
        self.unit_b.setAlignment(Qt.AlignCenter)
        self.unit_b.setMargin(2)
        self.unit_c = QLabel(self.groupBox_3)
        self.unit_c.setObjectName("unit_c")
        self.unit_c.setGeometry(QRect(150, 85, 31, 25))
        self.unit_c.setAlignment(Qt.AlignCenter)
        self.unit_c.setMargin(2)
        self.unit_d = QLabel(self.groupBox_3)
        self.unit_d.setObjectName("unit_d")
        self.unit_d.setGeometry(QRect(150, 115, 31, 25))
        self.unit_d.setAlignment(Qt.AlignCenter)
        self.unit_d.setMargin(2)
        self.shift_A = QLabel(self.groupBox_3)
        self.shift_A.setObjectName("shift_A")
        self.shift_A.setGeometry(QRect(70, 25, 81, 25))
        font5 = QFont()
        font5.setFamilies(["Segoe UI"])
        font5.setPointSize(9)
        font5.setBold(False)
        self.shift_A.setFont(font5)
        self.shift_A.setStyleSheet(
            "background: white;\n"
            "border: 1px solid rgb(171, 171, 171);\n"
            "border-radius: 2px;"
        )
        self.shift_A.setAlignment(Qt.AlignCenter)
        self.shift_B = QLabel(self.groupBox_3)
        self.shift_B.setObjectName("shift_B")
        self.shift_B.setGeometry(QRect(70, 55, 81, 25))
        self.shift_B.setFont(font)
        self.shift_B.setStyleSheet(
            "background: white;\n"
            "border: 1px solid rgb(171, 171, 171);\n"
            "border-radius: 2px;"
        )
        self.shift_B.setAlignment(Qt.AlignCenter)
        self.shift_C = QLabel(self.groupBox_3)
        self.shift_C.setObjectName("shift_C")
        self.shift_C.setGeometry(QRect(70, 85, 81, 25))
        self.shift_C.setFont(font)
        self.shift_C.setStyleSheet(
            "background: white;\n"
            "border: 1px solid rgb(171, 171, 171);\n"
            "border-radius: 2px;"
        )
        self.shift_C.setAlignment(Qt.AlignCenter)
        self.shift_D = QLabel(self.groupBox_3)
        self.shift_D.setObjectName("shift_D")
        self.shift_D.setGeometry(QRect(70, 115, 81, 25))
        self.shift_D.setFont(font)
        self.shift_D.setStyleSheet(
            "background: white;\n"
            "border: 1px solid rgb(171, 171, 171);\n"
            "border-radius: 2px;"
        )
        self.shift_D.setAlignment(Qt.AlignCenter)
        self.label_20 = QLabel(self.groupBox_3)
        self.label_20.setObjectName("label_20")
        self.label_20.setGeometry(QRect(10, 25, 51, 25))
        self.label_20.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.label_20.setMargin(2)
        self.label_21 = QLabel(self.groupBox_3)
        self.label_21.setObjectName("label_21")
        self.label_21.setGeometry(QRect(10, 55, 51, 25))
        self.label_21.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.label_21.setMargin(2)
        self.label_22 = QLabel(self.groupBox_3)
        self.label_22.setObjectName("label_22")
        self.label_22.setGeometry(QRect(10, 85, 51, 25))
        self.label_22.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.label_22.setMargin(2)
        self.label_23 = QLabel(self.groupBox_3)
        self.label_23.setObjectName("label_23")
        self.label_23.setGeometry(QRect(10, 115, 51, 25))
        self.label_23.setAlignment(Qt.AlignRight | Qt.AlignTrailing | Qt.AlignVCenter)
        self.label_23.setMargin(2)
        self.groupBox_4 = QGroupBox(self.curr_seg_box)
        self.groupBox_4.setObjectName("groupBox_4")
        self.groupBox_4.setGeometry(QRect(279, 0, 221, 151))
        self.current_note = QLineEdit(self.groupBox_4)
        self.current_note.setObjectName("current_note")
        self.current_note.setEnabled(True)
        self.current_note.setGeometry(QRect(10, 110, 201, 25))
        sizePolicy2.setHeightForWidth(
            self.current_note.sizePolicy().hasHeightForWidth()
        )
        self.current_note.setSizePolicy(sizePolicy2)
        self.current_note.setFont(font)
        self.current_note.setFocusPolicy(Qt.ClickFocus)
        self.current_note.setStyleSheet(
            "\n"
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
            "}"
        )
        self.end_time = QLabel(self.groupBox_4)
        self.end_time.setObjectName("end_time")
        self.end_time.setGeometry(QRect(100, 55, 91, 21))
        self.end_time.setStyleSheet("")
        self.end_time.setAlignment(Qt.AlignCenter)
        self.label_2 = QLabel(self.groupBox_4)
        self.label_2.setObjectName("label_2")
        self.label_2.setGeometry(QRect(200, 55, 20, 21))
        self.start_time = QLabel(self.groupBox_4)
        self.start_time.setObjectName("start_time")
        self.start_time.setGeometry(QRect(100, 30, 91, 21))
        self.start_time.setStyleSheet("")
        self.start_time.setFrameShadow(QFrame.Raised)
        self.start_time.setLineWidth(0)
        self.start_time.setAlignment(Qt.AlignCenter)
        self.label = QLabel(self.groupBox_4)
        self.label.setObjectName("label")
        self.label.setGeometry(QRect(200, 30, 21, 21))
        self.label_13 = QLabel(self.groupBox_4)
        self.label_13.setObjectName("label_13")
        self.label_13.setGeometry(QRect(10, 80, 41, 21))
        self.label_13.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)
        self.label_13.setMargin(2)
        self.label_12 = QLabel(self.groupBox_4)
        self.label_12.setObjectName("label_12")
        self.label_12.setGeometry(QRect(10, 55, 81, 21))
        self.label_12.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)
        self.label_12.setMargin(2)
        self.label_11 = QLabel(self.groupBox_4)
        self.label_11.setObjectName("label_11")
        self.label_11.setGeometry(QRect(10, 30, 81, 21))
        self.label_11.setAlignment(Qt.AlignLeading | Qt.AlignLeft | Qt.AlignVCenter)
        self.label_11.setMargin(2)

        self.controls.addWidget(self.frame_2)

        self.frame = QFrame(Processing)
        self.frame.setObjectName("frame")
        self.frame.setMinimumSize(QSize(0, 60))
        self.frame.setMaximumSize(QSize(16777215, 60))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.save_segment_btn = QPushButton(self.frame)
        self.save_segment_btn.setObjectName("save_segment_btn")
        self.save_segment_btn.setMinimumSize(QSize(0, 45))
        self.save_segment_btn.setFont(font)
        self.save_segment_btn.setFocusPolicy(Qt.NoFocus)
        self.save_segment_btn.setStyleSheet(
            "QPushButton {\n"
            "		background-color: rgb(230, 230, 230);\n"
            "	    border: 1px solid rgb(171, 171, 171); \n"
            "		border-radius: 3px;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background-color: rgb(253, 253, 253);\n"
            "	border: 1px raised;\n"
            "	border-radius: 5px;\n"
            "}"
        )

        self.horizontalLayout_2.addWidget(self.save_segment_btn)

        self.horizontalSpacer_3 = QSpacerItem(
            10, 20, QSizePolicy.Fixed, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer_3)

        self.new_segment_btn = QPushButton(self.frame)
        self.new_segment_btn.setObjectName("new_segment_btn")
        self.new_segment_btn.setMinimumSize(QSize(0, 45))
        self.new_segment_btn.setFont(font)
        self.new_segment_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}"
        )

        self.horizontalLayout_2.addWidget(self.new_segment_btn)

        self.horizontalSpacer = QSpacerItem(
            120, 20, QSizePolicy.Preferred, QSizePolicy.Minimum
        )

        self.horizontalLayout_2.addItem(self.horizontalSpacer)

        self.align_seg_btn = QPushButton(self.frame)
        self.align_seg_btn.setObjectName("align_seg_btn")
        self.align_seg_btn.setMinimumSize(QSize(0, 45))
        self.align_seg_btn.setFont(font)
        self.align_seg_btn.setStyleSheet(
            "QPushButton {\n"
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
            "}"
        )

        self.horizontalLayout_2.addWidget(self.align_seg_btn)

        self.controls.addWidget(self.frame)

        self.frame_4 = QFrame(Processing)
        self.frame_4.setObjectName("frame_4")
        sizePolicy3 = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(41)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_4.sizePolicy().hasHeightForWidth())
        self.frame_4.setSizePolicy(sizePolicy3)
        self.frame_4.setMinimumSize(QSize(510, 50))
        self.frame_4.setMaximumSize(QSize(510, 50))
        self.frame_4.setFont(font)
        self.frame_4.setFrameShape(QFrame.StyledPanel)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.delete_row_btn = QPushButton(self.frame_4)
        self.delete_row_btn.setObjectName("delete_row_btn")
        self.delete_row_btn.setGeometry(QRect(30, 10, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.delete_row_btn.sizePolicy().hasHeightForWidth()
        )
        self.delete_row_btn.setSizePolicy(sizePolicy2)
        self.delete_row_btn.setMinimumSize(QSize(30, 30))
        self.delete_row_btn.setMaximumSize(QSize(30, 30))
        self.delete_row_btn.setFont(font4)
        self.delete_row_btn.setMouseTracking(True)
        self.delete_row_btn.setLayoutDirection(Qt.LeftToRight)
        self.delete_row_btn.setAutoFillBackground(False)
        self.delete_row_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon4 = QIcon()
        icon4.addFile(":/img/img/trash.png", QSize(), QIcon.Normal, QIcon.Off)
        self.delete_row_btn.setIcon(icon4)
        self.delete_row_btn.setIconSize(QSize(25, 25))
        self.delete_row_btn.setAutoRepeat(False)
        self.delete_row_btn.setAutoExclusive(False)
        self.delete_row_btn.setAutoDefault(False)
        self.delete_row_btn.setFlat(False)
        self.add_row_btn = QPushButton(self.frame_4)
        self.add_row_btn.setObjectName("add_row_btn")
        self.add_row_btn.setGeometry(QRect(70, 10, 30, 30))
        sizePolicy2.setHeightForWidth(self.add_row_btn.sizePolicy().hasHeightForWidth())
        self.add_row_btn.setSizePolicy(sizePolicy2)
        self.add_row_btn.setMinimumSize(QSize(30, 30))
        self.add_row_btn.setMaximumSize(QSize(30, 30))
        self.add_row_btn.setFont(font4)
        self.add_row_btn.setMouseTracking(True)
        self.add_row_btn.setLayoutDirection(Qt.LeftToRight)
        self.add_row_btn.setAutoFillBackground(False)
        self.add_row_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        icon5 = QIcon()
        icon5.addFile(":/img/img/undo.png", QSize(), QIcon.Normal, QIcon.Off)
        self.add_row_btn.setIcon(icon5)
        self.add_row_btn.setIconSize(QSize(22, 22))
        self.add_row_btn.setAutoRepeat(False)
        self.add_row_btn.setAutoExclusive(False)
        self.add_row_btn.setAutoDefault(False)
        self.add_row_btn.setFlat(False)
        self.export_table_btn = QPushButton(self.frame_4)
        self.export_table_btn.setObjectName("export_table_btn")
        self.export_table_btn.setGeometry(QRect(460, 10, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.export_table_btn.sizePolicy().hasHeightForWidth()
        )
        self.export_table_btn.setSizePolicy(sizePolicy2)
        self.export_table_btn.setMinimumSize(QSize(30, 30))
        self.export_table_btn.setMaximumSize(QSize(30, 30))
        self.export_table_btn.setFont(font4)
        self.export_table_btn.setMouseTracking(True)
        self.export_table_btn.setLayoutDirection(Qt.LeftToRight)
        self.export_table_btn.setAutoFillBackground(False)
        self.export_table_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        self.export_table_btn.setIcon(icon1)
        self.export_table_btn.setIconSize(QSize(25, 25))
        self.export_table_btn.setAutoRepeat(False)
        self.export_table_btn.setAutoExclusive(False)
        self.export_table_btn.setAutoDefault(False)
        self.export_table_btn.setFlat(False)
        self.import_table_btn = QPushButton(self.frame_4)
        self.import_table_btn.setObjectName("import_table_btn")
        self.import_table_btn.setGeometry(QRect(420, 10, 30, 30))
        sizePolicy2.setHeightForWidth(
            self.import_table_btn.sizePolicy().hasHeightForWidth()
        )
        self.import_table_btn.setSizePolicy(sizePolicy2)
        self.import_table_btn.setMinimumSize(QSize(30, 30))
        self.import_table_btn.setMaximumSize(QSize(30, 30))
        self.import_table_btn.setFont(font4)
        self.import_table_btn.setMouseTracking(True)
        self.import_table_btn.setLayoutDirection(Qt.LeftToRight)
        self.import_table_btn.setAutoFillBackground(False)
        self.import_table_btn.setStyleSheet(
            "QPushButton{\n"
            "	border: none;\n"
            "	background: none;\n"
            "}\n"
            "\n"
            "QPushButton::hover{\n"
            "	background: white;\n"
            "	border: 1px raised;\n"
            "	border-radius: 10px;\n"
            "}"
        )
        self.import_table_btn.setIcon(icon2)
        self.import_table_btn.setIconSize(QSize(25, 25))
        self.import_table_btn.setAutoRepeat(False)
        self.import_table_btn.setAutoExclusive(False)
        self.import_table_btn.setAutoDefault(False)
        self.import_table_btn.setFlat(False)
        self.table_toggle = QPushButton(self.frame_4)
        self.table_toggle.setObjectName("table_toggle")
        self.table_toggle.setGeometry(QRect(120, 10, 281, 30))
        sizePolicy.setHeightForWidth(self.table_toggle.sizePolicy().hasHeightForWidth())
        self.table_toggle.setSizePolicy(sizePolicy)
        self.table_toggle.setMinimumSize(QSize(0, 30))
        self.table_toggle.setFont(font1)
        self.page_indicator = QGraphicsView(self.frame_4)
        self.page_indicator.setObjectName("page_indicator")
        self.page_indicator.setGeometry(QRect(313, 21, 30, 10))
        self.page_indicator.setStyleSheet("background: transparent")
        self.page_indicator.setFrameShape(QFrame.NoFrame)
        self.page_indicator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.page_indicator.setInteractive(False)

        self.controls.addWidget(self.frame_4)

        self.data_table = QTableWidget(Processing)
        if self.data_table.columnCount() < 9:
            self.data_table.setColumnCount(9)
        font6 = QFont()
        font6.setFamilies(["Segoe UI"])
        font6.setPointSize(8)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setText("ID")
        __qtablewidgetitem.setFont(font6)
        self.data_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font6)
        self.data_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        font7 = QFont()
        font7.setPointSize(8)
        __qtablewidgetitem2 = QTableWidgetItem()
        __qtablewidgetitem2.setFont(font7)
        self.data_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setFont(font7)
        self.data_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        __qtablewidgetitem4.setFont(font7)
        self.data_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setFont(font7)
        self.data_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        __qtablewidgetitem6.setFont(font7)
        self.data_table.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        __qtablewidgetitem7.setFont(font7)
        self.data_table.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        __qtablewidgetitem8.setFont(font7)
        self.data_table.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        self.data_table.setObjectName("data_table")
        sizePolicy1.setHeightForWidth(self.data_table.sizePolicy().hasHeightForWidth())
        self.data_table.setSizePolicy(sizePolicy1)
        self.data_table.setMaximumSize(QSize(510, 16777215))
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

        self.horizontalLayout.addLayout(self.controls)

        self.retranslateUi(Processing)

        self.reset_segment_btn.setDefault(False)
        self.export_raw_data_btn.setDefault(False)
        self.import_raw_data_btn.setDefault(False)
        self.import_sens_btn.setDefault(False)
        self.delete_row_btn.setDefault(False)
        self.add_row_btn.setDefault(False)
        self.export_table_btn.setDefault(False)
        self.import_table_btn.setDefault(False)

        QMetaObject.connectSlotsByName(Processing)

    # setupUi

    def retranslateUi(self, Processing):
        Processing.setWindowTitle(
            QCoreApplication.translate("Processing", "Form", None)
        )
        self.label_3.setText(
            QCoreApplication.translate("Processing", "Control Panel", None)
        )
        self.groupBox.setTitle(
            QCoreApplication.translate("Processing", "Display", None)
        )
        self.segment_A.setText(QCoreApplication.translate("Processing", "A", None))
        self.segment_B.setText(QCoreApplication.translate("Processing", "B", None))
        self.segment_C.setText(QCoreApplication.translate("Processing", "C", None))
        self.segment_D.setText(QCoreApplication.translate("Processing", "D", None))
        self.reference_channel_btn.setText(
            QCoreApplication.translate("Processing", "SPR Settings", None)
        )
        self.groupBox_6.setTitle(
            QCoreApplication.translate("Processing", "Cycle Cursors", None)
        )
        self.label_14.setText(
            QCoreApplication.translate("Processing", "Start Cursor:", None)
        )
        self.label_16.setText(
            QCoreApplication.translate("Processing", "End Cursor:", None)
        )
        self.label_9.setText(QCoreApplication.translate("Processing", "s", None))
        self.label_10.setText(QCoreApplication.translate("Processing", "s", None))
        self.exp_clock.setText(
            QCoreApplication.translate("Processing", "HH.MM.SS", None)
        )
        self.label_19.setText(
            QCoreApplication.translate("Processing", "Experiment Time:", None)
        )
        self.label_6.setText("")
        self.label_7.setText("")
        # if QT_CONFIG(tooltip)
        self.reset_segment_btn.setToolTip(
            QCoreApplication.translate("Processing", "Clear All Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.reset_segment_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.export_raw_data_btn.setToolTip(
            QCoreApplication.translate("Processing", "Export Raw Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.export_raw_data_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.import_raw_data_btn.setToolTip(
            QCoreApplication.translate("Processing", "Import Raw Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.import_raw_data_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.import_sens_btn.setToolTip(
            QCoreApplication.translate("Processing", "Load Sensorgram Data", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.import_sens_btn.setText("")
        self.label_4.setText(
            QCoreApplication.translate("Processing", "Cycle of Interest", None)
        )
        self.groupBox_2.setTitle(
            QCoreApplication.translate("Processing", "Display", None)
        )
        self.SOI_A.setText(QCoreApplication.translate("Processing", "A", None))
        self.SOI_B.setText(QCoreApplication.translate("Processing", "B", None))
        self.SOI_C.setText(QCoreApplication.translate("Processing", "C", None))
        self.SOI_D.setText(QCoreApplication.translate("Processing", "D", None))
        self.groupBox_3.setTitle(
            QCoreApplication.translate("Processing", "Cycle Shift", None)
        )
        self.unit_a.setText(QCoreApplication.translate("Processing", "RU", None))
        self.unit_b.setText(QCoreApplication.translate("Processing", "RU", None))
        self.unit_c.setText(QCoreApplication.translate("Processing", "RU", None))
        self.unit_d.setText(QCoreApplication.translate("Processing", "RU", None))
        self.shift_A.setText(QCoreApplication.translate("Processing", "-", None))
        self.shift_B.setText(QCoreApplication.translate("Processing", "-", None))
        self.shift_C.setText(QCoreApplication.translate("Processing", "-", None))
        self.shift_D.setText(QCoreApplication.translate("Processing", "-", None))
        self.label_20.setText(
            QCoreApplication.translate("Processing", "Shift A:", None)
        )
        self.label_21.setText(
            QCoreApplication.translate("Processing", "Shift B:", None)
        )
        self.label_22.setText(
            QCoreApplication.translate("Processing", "Shift C:", None)
        )
        self.label_23.setText(
            QCoreApplication.translate("Processing", "Shift D:", None)
        )
        self.groupBox_4.setTitle(
            QCoreApplication.translate("Processing", "Time && Note", None)
        )
        self.current_note.setText("")
        self.end_time.setText(QCoreApplication.translate("Processing", "-", None))
        self.label_2.setText(QCoreApplication.translate("Processing", "s", None))
        self.start_time.setText(QCoreApplication.translate("Processing", "-", None))
        self.label.setText(QCoreApplication.translate("Processing", "s", None))
        self.label_13.setText(QCoreApplication.translate("Processing", "Note:", None))
        self.label_12.setText(
            QCoreApplication.translate("Processing", "End Time:", None)
        )
        self.label_11.setText(
            QCoreApplication.translate("Processing", "Start Time:", None)
        )
        self.save_segment_btn.setText(
            QCoreApplication.translate("Processing", "Save\nCycle", None)
        )
        self.new_segment_btn.setText(
            QCoreApplication.translate("Processing", "Start From\nLast Cycle", None)
        )
        self.align_seg_btn.setText(
            QCoreApplication.translate("Processing", "Send to\nData Analysis", None)
        )
        # if QT_CONFIG(tooltip)
        self.delete_row_btn.setToolTip(
            QCoreApplication.translate("Processing", "Delete Cycle", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.delete_row_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.add_row_btn.setToolTip(
            QCoreApplication.translate("Processing", "Restore Last Deleted", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.add_row_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.export_table_btn.setToolTip(
            QCoreApplication.translate("Processing", "Export Data Table", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.export_table_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.import_table_btn.setToolTip(
            QCoreApplication.translate("Processing", "Import Data Table", None)
        )
        # endif // QT_CONFIG(tooltip)
        self.import_table_btn.setText("")
        self.table_toggle.setText(
            QCoreApplication.translate("Processing", "Cycle Data Table", None)
        )
        ___qtablewidgetitem = self.data_table.horizontalHeaderItem(1)
        ___qtablewidgetitem.setText(
            QCoreApplication.translate("Processing", "Start", None)
        )
        ___qtablewidgetitem1 = self.data_table.horizontalHeaderItem(2)
        ___qtablewidgetitem1.setText(
            QCoreApplication.translate("Processing", "End", None)
        )
        ___qtablewidgetitem2 = self.data_table.horizontalHeaderItem(3)
        ___qtablewidgetitem2.setText(
            QCoreApplication.translate("Processing", "Shift A", None)
        )
        ___qtablewidgetitem3 = self.data_table.horizontalHeaderItem(4)
        ___qtablewidgetitem3.setText(
            QCoreApplication.translate("Processing", "Shift B", None)
        )
        ___qtablewidgetitem4 = self.data_table.horizontalHeaderItem(5)
        ___qtablewidgetitem4.setText(
            QCoreApplication.translate("Processing", "Shift C", None)
        )
        ___qtablewidgetitem5 = self.data_table.horizontalHeaderItem(6)
        ___qtablewidgetitem5.setText(
            QCoreApplication.translate("Processing", "Shift D", None)
        )
        ___qtablewidgetitem6 = self.data_table.horizontalHeaderItem(7)
        ___qtablewidgetitem6.setText(
            QCoreApplication.translate("Processing", "Ref", None)
        )
        ___qtablewidgetitem7 = self.data_table.horizontalHeaderItem(8)
        ___qtablewidgetitem7.setText(
            QCoreApplication.translate("Processing", "Note", None)
        )

    # retranslateUi
