import concurrent.futures
import logging
import os
import time
import uuid

import humanize
import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TimeRemainingColumn,
    TransferSpeedColumn,
)


class Downloader:
    """A class to handle downloading files with support for multi-threading.

    Attributes:
        num_threads (int): Number of threads to use for downloading.
        console (Console): Console object for displaying progress.
        logger (Logger): Logger object for logging information.
    """

    def __init__(self, num_threads=10):
        """Initialize the Downloader class with specified number of threads.

        Args:
            num_threads (int): Number of threads to use for downloading.
        """
        self.console = Console()
        self.num_threads = num_threads
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def get_headers():
        """Generate headers for the HTTP requests.

        Returns:
            dict: Headers for HTTP requests.
        """
        return {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        }

    @staticmethod
    def get_file_size(url, headers):
        """Get the size of the file from the URL.

        Args:
            url (str): URL of the file.
            headers (dict): HTTP headers.

        Returns:
            int: Size of the file in bytes.
        """
        response = requests.head(url, headers=headers)
        response.raise_for_status()
        return int(response.headers["Content-Length"])

    @staticmethod
    def supports_range_requests(url, headers):
        """Check if the server supports range requests.

        Args:
            url (str): URL of the file.
            headers (dict): HTTP headers.

        Returns:
            bool: True if the server supports range requests, False otherwise.
        """
        response = requests.head(url, headers=headers)
        response.raise_for_status()
        return "bytes" in response.headers.get("Accept-Ranges", "")

    def download_chunk(self, url, headers, start, end, temp_file_path, progress, task_id):
        """Download a chunk of the file.

        Args:
            url (str): URL of the file.
            headers (dict): HTTP headers.
            start (int): Start byte of the chunk.
            end (int): End byte of the chunk.
            temp_file_path (str): Temporary file path to save the chunk.
            progress (Progress): Progress object to update progress.
            task_id (TaskID): Task ID for the progress update.
        """
        chunk_headers = headers.copy()
        chunk_headers["Range"] = f"bytes={start}-{end}"
        response = requests.get(url, headers=chunk_headers, stream=True)
        response.raise_for_status()
        with open(temp_file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    file.write(chunk)
                    progress.update(task_id, advance=len(chunk))

    def download_file(self, url, headers, folder_name, file_name):
        """Download a file from the given URL.

        Args:
            url (str): URL of the file.
            headers (dict): HTTP headers.
            folder_name (str): Folder name to save the downloaded file.
            file_name (str): Name of the file to save.

        Returns:
            str: Absolute path of the downloaded file.
        """
        file_size = self.get_file_size(url, headers)
        chunk_size = file_size // self.num_threads
        supports_range = self.supports_range_requests(url, headers)
        unique_id = uuid.uuid4()

        progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )

        task_id = progress.add_task(f"[cyan]Downloading {file_name}", total=file_size)
        temp_folder = "./temp"
        os.makedirs(temp_folder, exist_ok=True)

        if supports_range:
            self.logger.info(f"Downloading the file using {self.num_threads} threads.")
            with progress:
                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=self.num_threads
                ) as executor:
                    futures = [
                        executor.submit(
                            self.download_chunk,
                            url,
                            headers,
                            i * chunk_size,
                            (
                                (i + 1) * chunk_size - 1
                                if i < self.num_threads - 1
                                else file_size - 1
                            ),
                            os.path.join(temp_folder, f"part_{unique_id}_{i}"),
                            progress,
                            task_id,
                        )
                        for i in range(self.num_threads)
                    ]

                    for future in concurrent.futures.as_completed(futures):
                        future.result()
        else:
            self.logger.warning(
                "Server does not support range requests. Downloading the file in a single thread."
            )
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            temp_file_path = os.path.join(temp_folder, f"{file_name}.temp")
            with progress:
                with open(temp_file_path, "wb") as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
                            progress.update(task_id, advance=len(chunk))

        output_folder = os.path.abspath(folder_name)
        os.makedirs(output_folder, exist_ok=True)
        output_file_path = os.path.join(output_folder, file_name)

        if supports_range:
            with open(output_file_path, "wb") as final_file:
                for i in range(self.num_threads):
                    temp_file_path = os.path.join(temp_folder, f"part_{unique_id}_{i}")
                    with open(temp_file_path, "rb") as part_file:
                        final_file.write(part_file.read())
                    os.remove(temp_file_path)
        else:
            os.rename(temp_file_path, output_file_path)

        # remove temp folder
        os.rmdir(temp_folder)

        return os.path.abspath(output_file_path)

    def download_files(self, file_urls, folder_name):
        """Download multiple files from the given URLs.

        Args:
            file_urls (list): List of file URLs or tuples (filename, URL).
            folder_name (str): Folder name to save the downloaded files.

        Returns:
            list: List of paths to the downloaded files.
        """
        start_time = time.time()
        headers = self.get_headers()
        downloaded_files = []

        for i, item in enumerate(file_urls, start=1):
            file_name, file_url = (
                item if isinstance(item, tuple) else (os.path.basename(item), item)
            )

            if os.path.isfile(file_name):
                continue

            downloaded_file_path = self.download_file(file_url, headers, folder_name, file_name)
            downloaded_files.append(downloaded_file_path)
            end_time = time.time()
            total_time = end_time - start_time
            file_size = self.get_file_size(file_url, headers)
            self.console.log(
                f"File successfully downloaded ({i}/{len(file_urls)}): "
                f"{file_name} ({humanize.naturalsize(file_size)}) - {total_time:.2f} seconds"
            )
            self.console.log(
                f"Total download speed: {humanize.naturalsize(file_size / total_time)}/s"
            )

        return downloaded_files
