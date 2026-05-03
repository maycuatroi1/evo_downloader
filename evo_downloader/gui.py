from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QProgressBar,
    QTextEdit,
)
from PyQt5.QtCore import QThread, pyqtSignal
import sys
import os
from evo_downloader.downloader import Downloader


class DownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, urls, folder):
        super().__init__()
        self.urls = urls
        self.folder = folder

    def run(self):
        downloader = Downloader()
        total_files = len(self.urls)
        for i, url in enumerate(self.urls):
            downloader.download_files([url], self.folder)
            self.progress_signal.emit(int((i + 1) / total_files * 100))
        self.finished_signal.emit()


class DownloaderGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Evo Downloader")
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        self.url_label = QLabel("URLs:")
        self.url_input = QTextEdit()
        url_layout.addWidget(self.url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        # Output folder selection
        folder_layout = QHBoxLayout()
        self.folder_label = QLabel("Output Folder:")
        self.folder_input = QLineEdit()
        default_download_folder = os.path.expanduser("~/Downloads")
        self.folder_input.setText(os.path.abspath(default_download_folder))
        self.folder_button = QPushButton("Browse")
        self.folder_button.clicked.connect(self.select_folder)
        folder_layout.addWidget(self.folder_label)
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_button)
        layout.addLayout(folder_layout)

        # Download button
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.start_download)
        layout.addWidget(self.download_button)

        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.setLayout(layout)

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Output Folder", os.path.expanduser("~/Downloads")
        )
        if folder:
            self.folder_input.setText(folder)

    def start_download(self):
        urls = self.url_input.toPlainText().strip().split("\n")
        folder = self.folder_input.text().strip()
        if not urls or not folder:
            return

        self.download_thread = DownloadThread(urls, folder)
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def download_finished(self):
        self.progress_bar.setValue(100)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = DownloaderGUI()
    gui.show()
    sys.exit(app.exec())
