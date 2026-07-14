from PyQt5 import QtWidgets, uic
import processing as PRC

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Load the UI file
        uic.loadUi('GumInspect.ui', self)

        # Create the App object and pass self (the UI) to it
        self.app = PRC.App("database.csv", self)
        self.app.read_atlas()

        # Connect the menu action
        self.actionImage.triggered.connect(self.app.open_image_file)
        self.actionDetect.triggered.connect(self.app.run_task_with_wait_message)
        self.actionEraseTop.triggered.connect(lambda: self.app.clear_images(1))
        self.actionEraseAll.triggered.connect(lambda: self.app.clear_images(2))
        self.actionDown.triggered.connect(self.app.move_down_images)
        self.actionClient.triggered.connect(self.app.Select_Client)
        self.actionSave.triggered.connect(self.app.Save_Client)

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
