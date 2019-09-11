# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'wEdgeType.ui'
#
# Created by: PyQt5 UI code generator 5.12.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_edge_type(object):
    def setupUi(self, edge_type):
        edge_type.setObjectName("edge_type")
        edge_type.resize(298, 193)
        self.gridLayout_2 = QtWidgets.QGridLayout(edge_type)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.gb_edge_type = QtWidgets.QGroupBox(edge_type)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.gb_edge_type.setFont(font)
        self.gb_edge_type.setObjectName("gb_edge_type")
        self.gridLayout_3 = QtWidgets.QGridLayout(self.gb_edge_type)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.rb_triangular = QtWidgets.QRadioButton(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.rb_triangular.setFont(font)
        self.rb_triangular.setObjectName("rb_triangular")
        self.verticalLayout_2.addWidget(self.rb_triangular)
        self.rb_rectangular = QtWidgets.QRadioButton(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.rb_rectangular.setFont(font)
        self.rb_rectangular.setObjectName("rb_rectangular")
        self.verticalLayout_2.addWidget(self.rb_rectangular)
        self.horizontalLayout_4 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_4.setObjectName("horizontalLayout_4")
        self.rb_custom = QtWidgets.QRadioButton(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.rb_custom.setFont(font)
        self.rb_custom.setObjectName("rb_custom")
        self.horizontalLayout_4.addWidget(self.rb_custom)
        self.ed_custom = QtWidgets.QLineEdit(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.ed_custom.setFont(font)
        self.ed_custom.setObjectName("ed_custom")
        self.horizontalLayout_4.addWidget(self.ed_custom)
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_4.addItem(spacerItem)
        self.horizontalLayout_4.setStretch(0, 1)
        self.horizontalLayout_4.setStretch(1, 1)
        self.horizontalLayout_4.setStretch(2, 3)
        self.verticalLayout_2.addLayout(self.horizontalLayout_4)
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setSpacing(8)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.rb_user = QtWidgets.QRadioButton(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.rb_user.setFont(font)
        self.rb_user.setObjectName("rb_user")
        self.horizontalLayout_2.addWidget(self.rb_user)
        self.ed_q_user = QtWidgets.QLineEdit(self.gb_edge_type)
        font = QtGui.QFont()
        font.setBold(False)
        font.setWeight(50)
        self.ed_q_user.setFont(font)
        self.ed_q_user.setObjectName("ed_q_user")
        self.horizontalLayout_2.addWidget(self.ed_q_user)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.horizontalLayout_2.setStretch(0, 1)
        self.horizontalLayout_2.setStretch(1, 1)
        self.horizontalLayout_2.setStretch(2, 3)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)
        self.gridLayout_3.addLayout(self.verticalLayout_2, 0, 0, 1, 1)
        self.horizontalLayout.addWidget(self.gb_edge_type)
        self.gb_apply_to = QtWidgets.QGroupBox(edge_type)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.gb_apply_to.setFont(font)
        self.gb_apply_to.setObjectName("gb_apply_to")
        self.gridLayout = QtWidgets.QGridLayout(self.gb_apply_to)
        self.gridLayout.setObjectName("gridLayout")
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.rb_all = QtWidgets.QRadioButton(self.gb_apply_to)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.rb_all.setFont(font)
        self.rb_all.setChecked(True)
        self.rb_all.setObjectName("rb_all")
        self.verticalLayout.addWidget(self.rb_all)
        self.rb_transect = QtWidgets.QRadioButton(self.gb_apply_to)
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.rb_transect.setFont(font)
        self.rb_transect.setObjectName("rb_transect")
        self.verticalLayout.addWidget(self.rb_transect)
        self.gridLayout.addLayout(self.verticalLayout, 0, 0, 1, 1)
        self.horizontalLayout.addWidget(self.gb_apply_to)
        self.horizontalLayout.setStretch(0, 2)
        self.horizontalLayout.setStretch(1, 1)
        self.verticalLayout_3.addLayout(self.horizontalLayout)
        self.buttonBox = QtWidgets.QDialogButtonBox(edge_type)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout_3.addWidget(self.buttonBox)
        self.gridLayout_2.addLayout(self.verticalLayout_3, 0, 0, 1, 1)

        self.retranslateUi(edge_type)
        self.buttonBox.accepted.connect(edge_type.accept)
        self.buttonBox.rejected.connect(edge_type.reject)
        QtCore.QMetaObject.connectSlotsByName(edge_type)

    def retranslateUi(self, edge_type):
        _translate = QtCore.QCoreApplication.translate
        edge_type.setWindowTitle(_translate("edge_type", "Edge Type"))
        self.gb_edge_type.setTitle(_translate("edge_type", "Edge Type"))
        self.rb_triangular.setText(_translate("edge_type", "Triangular (0.3535)"))
        self.rb_rectangular.setText(_translate("edge_type", "Rectangular (0.91)"))
        self.rb_custom.setText(_translate("edge_type", "Custom"))
        self.rb_user.setText(_translate("edge_type", "User Q"))
        self.gb_apply_to.setTitle(_translate("edge_type", "Apply To:"))
        self.rb_all.setText(_translate("edge_type", "All Transects"))
        self.rb_transect.setText(_translate("edge_type", "Transect Only"))




if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    edge_type = QtWidgets.QDialog()
    ui = Ui_edge_type()
    ui.setupUi(edge_type)
    edge_type.show()
    sys.exit(app.exec_())
