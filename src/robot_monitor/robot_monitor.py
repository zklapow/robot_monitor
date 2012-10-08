import roslib;roslib.load_manifest('robot_monitor')
import rospy
from diagnostic_msgs.msg import DiagnosticArray

from python_qt_binding.QtGui import QWidget, QVBoxLayout, QTreeWidget, QTextCursor, QTreeWidgetItem, QTextEdit, QPushButton
from python_qt_binding.QtCore import pyqtSignal

def get_nice_name(status_name):
    return status_name.split('/')[-1]

def remove_parent_name(status_name):
    return ('/'.join(status_name.split('/')[2:])).strip()

def get_parent_name(status_name):
    return ('/'.join(status_name.split('/')[:-1])).strip()

class StatusItem(QTreeWidgetItem):
    def __init__(self, status):
        super(StatusItem, self).__init__()
    
        self.items = []
        self.name = status.name
        self.level = status.level
        self.inspector = None
        
        self.setText(0, '/' + get_nice_name(self.name))

    def get_children(self, msg):
        ret = []

        for k in msg.status:
            if k.name.startswith(self.name):
                if not k.name == self.name:
                    ret.append(k)

        return ret

    def update(self, status, msg):
        self.status = status

        if self.inspector:
            self.inspector.update(status)
        
        children = self.get_children(msg)

        names = [s.name for s in self.items]
        new_items = []
        remove = []
        for i in children:
            name = i.name
            if name in names:
                w = self.items[names.index(name)]
                w.update(i, msg)
            elif len(self.strip_child(name).split('/')) <= 2:
                sti = StatusItem(i)
                sti.update(i, msg)
                self.items.append(sti)
                new_items.append(sti)
        self.addChildren(new_items)

    def on_click(self):
        if not self.inspector:
            self.inspector = InspectorWidget(self.status)
        else:
            self.inspector.activateWindow()

    def strip_child(self, child):
        return child.replace(self.name, '')

class InspectorWidget(QWidget):
    class Snapshot(QTextEdit):
        """Display a single sitatic status message. Helps facilitate copy/paste"""
        def __init__(self, status):
            super(InspectorWidget.Snapshot, self).__init__()

            self.write("Full Name", status.name)
            self.write("Component", status.name.split('/')[-1])
            self.write("Hardware ID", status.hardware_id)
            self.write("Level", status.level)
            self.write("Message", status.message)
            self.insertPlainText('\n')

            for value in status.values:
                self.write(value.key, value.value)

            self.setGeometry(0,0, 300, 400)
            self.show()

        def write(self, k, v):
            self.setFontWeight(75)
            self.insertPlainText(str(k))
            self.insertPlainText(': ')
         
            self.setFontWeight(50)
            self.insertPlainText(str(v))
            self.insertPlainText('\n')           

    write = pyqtSignal(str, str)
    newline = pyqtSignal()
    clear = pyqtSignal()
    def __init__(self, status):
        super(InspectorWidget, self).__init__()
        self.status = status
        self.setWindowTitle(status.name)

        layout = QVBoxLayout()
        
        self.disp = QTextEdit()
        self.snapshot = QPushButton("Snapshot")

        layout.addWidget(self.disp)
        layout.addWidget(self.snapshot)

        self.snaps = []
        self.snapshot.clicked.connect(self.take_snapshot)

        self.write.connect(self.write_kv)
        self.newline.connect(lambda: self.disp.insertPlainText('\n'))
        self.clear.connect(lambda: self.disp.clear())
        self.update(status)

        self.setLayout(layout)
        self.setGeometry(0,0,300,400)
        self.show()

    def write_kv(self, k, v):
        self.disp.setFontWeight(75)
        self.disp.insertPlainText(k)
        self.disp.insertPlainText(': ')

        self.disp.setFontWeight(50)
        self.disp.insertPlainText(v)
        self.disp.insertPlainText('\n')

    def update(self, status):
        self.status = status

        self.clear.emit()
        self.write.emit("Full Name", status.name)
        self.write.emit("Component", status.name.split('/')[-1])
        self.write.emit("Hardware ID", status.hardware_id)
        self.write.emit("Level", str(status.level))
        self.write.emit("Message", status.message)
        self.newline.emit()

        for v in status.values:
            self.write.emit(v.key, v.value)

    def take_snapshot(self):
        snap = InspectorWidget.Snapshot(self.status)
        self.snaps.append(snap)

class RobotMonitor(QWidget):
    sig_err = pyqtSignal(str)
    sig_warn = pyqtSignal(str)
    sig_clear = pyqtSignal()

    def __init__(self, topic):
        super(RobotMonitor, self).__init__()
        self.setObjectName('Robot Monitor')

        self.top_items = []
        layout = QVBoxLayout()

        self.err = QTreeWidget()
        self.err.setHeaderLabel("Errors")
        self.warn = QTreeWidget()
        self.warn.setHeaderLabel("Warnings")

        self.sig_clear.connect(self.clear)
        self.sig_err.connect(self.disp_err)
        self.sig_warn.connect(self.disp_warn)

        self.comp = QTreeWidget()
        self.comp.setHeaderLabel("All")
        self.comp.itemDoubleClicked.connect(self.tree_clicked)

        layout.addWidget(self.err)
        layout.addWidget(self.warn)
        layout.addWidget(self.comp, 1)

        self.setLayout(layout)

        self.topic = topic
        self.sub = rospy.Subscriber(self.topic, DiagnosticArray, self.cb)

    def cb(self, msg):
        self.sig_clear.emit()
        self.update_tree(msg)
        self.update_we(msg)

    def tree_clicked(self, item, yes):
        item.on_click()

    def update_tree(self, msg):
        #Update the tree from the bottom

        names = [get_nice_name(k.name) for k in self.top_items]
        add = []
        for i in self._top_level(msg):
            name = get_nice_name(i.name)
            if name in names:
                self.top_items[names.index(name)].update(i, msg)
            else:
                nw = StatusItem(i)
                nw.update(i, msg)
                self.top_items.append(nw)
                add.append(nw)
        
        self.comp.addTopLevelItems(add)
        
    def _top_level(self, msg):
        ret = []
        for i in msg.status:
            if len(i.name.split('/')) == 2:
                ret.append(i)
        
        return ret

    def update_we(self, msg):
        for status in msg.status:
            if status.level == status.WARN:
                txt = "%s : %s"%(status.name, status.message)
                self.sig_warn.emit(txt)
            elif status.level == status.ERROR:
                txt = "%s : %s"%(status.name, status.message)
                self.sig_err.emit(txt)

    def clear(self):
        self.err.clear()
        self.warn.clear()

    def disp_err(self, msg):
        i = QTreeWidgetItem()
        i.setText(0, msg)
        self.err.addTopLevelItem(i)
        
    def disp_warn(self,msg):
        i = QTreeWidgetItem()
        i.setText(0, msg)
        self.warn.addTopLevelItem(i)

    def close(self):
        if self.sub:
            self.sub.unregister()
            self.sub = None

