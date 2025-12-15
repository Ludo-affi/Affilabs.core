################################################################################
## Form generated from reading UI file 'cycle_table_dialog.ui'
##
## Created by: Qt User Interface Compiler version 6.10.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import QCoreApplication, QMetaObject, QRect, QSize, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QFrame,
    QGraphicsView,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class Ui_CycleTableDialog:
    def setupUi(self, CycleTableDialog):
        if not CycleTableDialog.objectName():
            CycleTableDialog.setObjectName("CycleTableDialog")
        CycleTableDialog.resize(800, 600)
        self.verticalLayout = QVBoxLayout(CycleTableDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.seg_table = QFrame(CycleTableDialog)
        self.seg_table.setObjectName("seg_table")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.seg_table.sizePolicy().hasHeightForWidth())
        self.seg_table.setSizePolicy(sizePolicy)
        self.seg_table.setMinimumSize(QSize(0, 50))
        self.seg_table.setMaximumSize(QSize(16777215, 50))
        font = QFont()
        font.setFamilies(["Segoe UI"])
        font.setPointSize(9)
        self.seg_table.setFont(font)
        self.seg_table.setFrameShape(QFrame.StyledPanel)
        self.seg_table.setFrameShadow(QFrame.Raised)
        self.delete_row_btn = QPushButton(self.seg_table)
        self.delete_row_btn.setObjectName("delete_row_btn")
        self.delete_row_btn.setGeometry(QRect(30, 10, 30, 30))
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(
            self.delete_row_btn.sizePolicy().hasHeightForWidth(),
        )
        self.delete_row_btn.setSizePolicy(sizePolicy1)
        self.delete_row_btn.setMinimumSize(QSize(30, 30))
        self.delete_row_btn.setMaximumSize(QSize(30, 30))
        font1 = QFont()
        font1.setFamilies(["Segoe UI"])
        font1.setPointSize(5)
        self.delete_row_btn.setFont(font1)
        self.delete_row_btn.setMouseTracking(True)
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
            "}",
        )
        icon = QIcon()
        icon.addFile(":/img/img/trash.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.delete_row_btn.setIcon(icon)
        self.delete_row_btn.setIconSize(QSize(25, 25))
        self.add_row_btn = QPushButton(self.seg_table)
        self.add_row_btn.setObjectName("add_row_btn")
        self.add_row_btn.setGeometry(QRect(70, 10, 30, 30))
        sizePolicy1.setHeightForWidth(self.add_row_btn.sizePolicy().hasHeightForWidth())
        self.add_row_btn.setSizePolicy(sizePolicy1)
        self.add_row_btn.setMinimumSize(QSize(30, 30))
        self.add_row_btn.setMaximumSize(QSize(30, 30))
        self.add_row_btn.setFont(font1)
        self.add_row_btn.setMouseTracking(True)
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
            "}",
        )
        icon1 = QIcon()
        icon1.addFile(":/img/img/undo.png", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.add_row_btn.setIcon(icon1)
        self.add_row_btn.setIconSize(QSize(22, 22))
        self.table_toggle = QPushButton(self.seg_table)
        self.table_toggle.setObjectName("table_toggle")
        self.table_toggle.setGeometry(QRect(140, 10, 251, 30))
        sizePolicy.setHeightForWidth(self.table_toggle.sizePolicy().hasHeightForWidth())
        self.table_toggle.setSizePolicy(sizePolicy)
        self.table_toggle.setMinimumSize(QSize(0, 30))
        font2 = QFont()
        font2.setFamilies(["Segoe UI"])
        font2.setPointSize(11)
        self.table_toggle.setFont(font2)
        self.page_indicator = QGraphicsView(self.seg_table)
        self.page_indicator.setObjectName("page_indicator")
        self.page_indicator.setGeometry(QRect(318, 21, 30, 10))
        self.page_indicator.setStyleSheet("background: transparent")
        self.page_indicator.setFrameShape(QFrame.NoFrame)
        self.page_indicator.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_indicator.setInteractive(False)

        self.verticalLayout.addWidget(self.seg_table)

        self.data_table = QTableWidget(CycleTableDialog)
        if self.data_table.columnCount() < 9:
            self.data_table.setColumnCount(9)
        font3 = QFont()
        font3.setFamilies(["Segoe UI"])
        font3.setPointSize(8)
        __qtablewidgetitem = QTableWidgetItem()
        __qtablewidgetitem.setText("ID")
        __qtablewidgetitem.setFont(font3)
        self.data_table.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        __qtablewidgetitem1.setFont(font3)
        self.data_table.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        font4 = QFont()
        font4.setPointSize(8)
        __qtablewidgetitem2 = QTableWidgetItem()
        __qtablewidgetitem2.setFont(font4)
        self.data_table.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        __qtablewidgetitem3.setFont(font4)
        self.data_table.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        __qtablewidgetitem4.setFont(font4)
        self.data_table.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        __qtablewidgetitem5.setFont(font4)
        self.data_table.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        __qtablewidgetitem6.setFont(font4)
        self.data_table.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        __qtablewidgetitem7.setFont(font4)
        self.data_table.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        __qtablewidgetitem8.setFont(font4)
        self.data_table.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        self.data_table.setObjectName("data_table")
        sizePolicy2 = QSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.data_table.sizePolicy().hasHeightForWidth())
        self.data_table.setSizePolicy(sizePolicy2)
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

        self.verticalLayout.addWidget(self.data_table)

        self.retranslateUi(CycleTableDialog)

        QMetaObject.connectSlotsByName(CycleTableDialog)

    # setupUi

    def retranslateUi(self, CycleTableDialog):
        CycleTableDialog.setWindowTitle(
            QCoreApplication.translate("CycleTableDialog", "Cycle Data Table", None),
        )
        # if QT_CONFIG(tooltip)
        self.delete_row_btn.setToolTip(
            QCoreApplication.translate("CycleTableDialog", "Delete Cycle", None),
        )
        # endif // QT_CONFIG(tooltip)
        self.delete_row_btn.setText("")
        # if QT_CONFIG(tooltip)
        self.add_row_btn.setToolTip(
            QCoreApplication.translate(
                "CycleTableDialog",
                "Restore Last Deleted",
                None,
            ),
        )
        # endif // QT_CONFIG(tooltip)
        self.add_row_btn.setText("")
        self.table_toggle.setText(
            QCoreApplication.translate("CycleTableDialog", "Cycle Data Table", None),
        )
        ___qtablewidgetitem = self.data_table.horizontalHeaderItem(1)
        ___qtablewidgetitem.setText(
            QCoreApplication.translate("CycleTableDialog", "Start", None),
        )
        ___qtablewidgetitem1 = self.data_table.horizontalHeaderItem(2)
        ___qtablewidgetitem1.setText(
            QCoreApplication.translate("CycleTableDialog", "End", None),
        )
        ___qtablewidgetitem2 = self.data_table.horizontalHeaderItem(3)
        ___qtablewidgetitem2.setText(
            QCoreApplication.translate("CycleTableDialog", "Shift A", None),
        )
        ___qtablewidgetitem3 = self.data_table.horizontalHeaderItem(4)
        ___qtablewidgetitem3.setText(
            QCoreApplication.translate("CycleTableDialog", "Shift B", None),
        )
        ___qtablewidgetitem4 = self.data_table.horizontalHeaderItem(5)
        ___qtablewidgetitem4.setText(
            QCoreApplication.translate("CycleTableDialog", "Shift C", None),
        )
        ___qtablewidgetitem5 = self.data_table.horizontalHeaderItem(6)
        ___qtablewidgetitem5.setText(
            QCoreApplication.translate("CycleTableDialog", "Shift D", None),
        )
        ___qtablewidgetitem6 = self.data_table.horizontalHeaderItem(7)
        ___qtablewidgetitem6.setText(
            QCoreApplication.translate("CycleTableDialog", "Ref", None),
        )
        ___qtablewidgetitem7 = self.data_table.horizontalHeaderItem(8)
        ___qtablewidgetitem7.setText(
            QCoreApplication.translate("CycleTableDialog", "Note", None),
        )

    # retranslateUi
