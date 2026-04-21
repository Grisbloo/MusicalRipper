import csv
import glob
import os
import re
import subprocess
import threading
import time
# URL Checker
from urllib.parse import urlparse

import customtkinter as ctk
import yt_dlp
# Selenium Imports
from selenium import webdriver
# Chromium Imports
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
# Edge Imports
# Firefox Imports
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

# Set the modern dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MUSIC_SOURCES = {
    "Spotify": "//button[contains(@aria-label, 'Spotify') or .//div[text()='Spotify']]",
    "Apple": "//button[contains(@aria-label, 'Apple') or .//div[text()='Apple Music']]",
    "YoutubeMusic": "//button[contains(@aria-label, 'YouTube Music')]",
    "Youtube": "//button[contains(@aria-label, 'YouTube')]",
    "Deezer": "//button[contains(@aria-label, 'Deezer')]",
    "iTunes": "//button[contains(@aria-label, 'iTunes')]",
    "Anghami": "//button[contains(@aria-label, 'Anghami')]",
    "Kkbox": "//button[contains(@aria-label, 'Kkbox')]",
    "LastFm": "//button[contains(@aria-label, 'LastFm')]"
}


class AudioExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Audio Ripper")
        self.geometry("650x600")

        self.title_label = ctk.CTkLabel(self, text="Audio Extraction Pipeline",
                                        font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        self.url_entry = ctk.CTkEntry(self, placeholder_text="Paste Playlist URL here...", width=500)
        self.url_entry.pack(pady=10)

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Output Folder Name", width=500)
        self.name_entry.pack(pady=10)

        # Output Directory Selection
        self.dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dir_frame.pack(pady=10)

        self.dir_entry = ctk.CTkEntry(self.dir_frame, width=390)
        self.dir_entry.insert(0, os.getcwd())  # Default to current folder
        self.dir_entry.configure(state="readonly")  # Prevent manual typing errors
        self.dir_entry.pack(side="left", padx=(0, 10))

        self.browse_btn = ctk.CTkButton(self.dir_frame, text="Browse", width=100, command=self.browse_directory)
        self.browse_btn.pack(side="right")

        # Browser Source Selection Dropdown
        self.browser_var = ctk.StringVar(value="Edge")
        self.browser_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.browser_var,
            values=["Chrome", "Edge", "Brave", "Firefox", "Opera", "OperaGX"],
            width=200
        )

        # Music Source Selection Dropdown
        self.source_var = ctk.StringVar(value="Spotify")
        self.source_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self.source_var,
            values=[
                "Spotify",
                "Apple Music",
                "YouTube Music",
                "YouTube",
                "Deezer",
                "iTunes",
                "anghami",
                "KKBOX",
                "last.fm"
            ],
            width=200
        )
        self.source_dropdown.pack(pady=10)

        self.browser_dropdown.pack(pady=10)

        # The "Idling Action" Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, width=400, mode="indeterminate")
        self.progress_bar.pack(pady=(10, 0))
        self.progress_bar.set(0)  # Keeps it empty and still before the user hits start

        self.start_button = ctk.CTkButton(self, text="Start Extraction", command=self.start_pipeline, height=40)
        self.start_button.pack(pady=20)

        self.log_box = ctk.CTkTextbox(self, width=550, height=200, state="disabled")
        self.log_box.pack(pady=(10, 20))

    def browse_directory(self):
        """Opens a file explorer to choose the save location."""
        folder = ctk.filedialog.askdirectory(initialdir=os.getcwd(), title="Select Save Location")
        if folder:
            self.dir_entry.configure(state="normal")
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, folder)
            self.dir_entry.configure(state="readonly")

    def log_message(self, message):
        """Thread-safe log call."""
        self.after(0, self._log_message, message)

    def _log_message(self, message):
        """Actual GUI update."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", str(message) + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def reset_ui(self):
        """Re-enables the UI after a pipeline run (success or failure)."""
        self.after(0, self._reset_ui)

    def _reset_ui(self):
        self.progress_bar.stop()
        self.progress_bar.set(0)
        self.start_button.configure(state="normal", text="Start Extraction")

    def start_pipeline(self):
        url = self.url_entry.get().strip()
        name = self.name_entry.get().strip()
        browser = self.browser_var.get()
        source = self.source_var.get()
        base_dir = self.dir_entry.get()

        if not url or not name:
            self.log_message("[ERROR] Please fill in both the URL and Output File Name.")
            return

        # Fail-Fast URL Validation
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            self.log_message("[ERROR] Invalid URL. Please enter a full link (e.g., https://open.spotify.com/...)")
            return

        self.start_button.configure(state="disabled")
        self.progress_bar.start()
        self.log_message(f"Starting pipeline for '{name}' using {browser.capitalize()}...\n" + "=" * 50)

        threading.Thread(
            target=self.run_engine,
            args=(url, name, browser, source, base_dir),
            daemon=True
        ).start()

    def run_engine(self, url, name, browser, source, base_dir):
        """The master pipeline that controls the flow."""
        project_folder = os.path.join(base_dir, name)

        try:
            # Step 1: Web Automation
            csv_path = self.fetch_playlist_csv(url, name, project_folder, browser, source)

            if csv_path:
                # Step 2: Read CSV
                song_list = self.get_songs_from_file(csv_path)
                self.log_message(f"\nLoaded {len(song_list)} tracks. Starting audio extraction...")

                # Step 3: Download Audio
                for track in song_list:
                    self.download_with_fallback(track, project_folder)

                self.log_message(f"\nPipeline finished! All files are saved in: {project_folder}")
            else:
                self.log_message("\n[FATAL ERROR] Pipeline halted because CSV fetch failed.")
        finally:
            # Always reset the UI whether we succeeded or crashed
            self.reset_ui()

    def create_ghost_browser(self, browser_choice, download_dir):
        """Spawns the requested browser using the factory pattern."""
        browser_choice = browser_choice.lower()
        self.log_message(f"Initializing {browser_choice.capitalize()} driver...")

        if browser_choice == "chrome":
            options = webdriver.ChromeOptions()
            self.add_stealth_flags(options)
            options.page_load_strategy = "eager"
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        elif browser_choice == "edge":
            options = webdriver.EdgeOptions()
            self.add_stealth_flags(options)
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            return webdriver.Edge(options=options)

        elif browser_choice == "brave":
            options = webdriver.ChromeOptions()
            self.add_stealth_flags(options)
            brave_path = os.path.join(
                os.environ["PROGRAMFILES"],
                "BraveSoftware",
                "Brave-Browser",
                "Application",
                "brave.exe"
            )
            if not os.path.exists(brave_path):
                self.log_message("[ERROR] Brave not found on this system.")
                return None
            # FIX: Actually set the binary location so it uses Brave, not Chrome
            options.binary_location = brave_path
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        elif browser_choice == "firefox":
            options = webdriver.FirefoxOptions()
            options.set_preference("permissions.default.image", 2)
            options.set_preference("dom.ipc.plugins.enabled", False)
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.dir", download_dir)
            options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv")
            return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)

        elif browser_choice == "opera":
            options = webdriver.ChromeOptions()
            self.add_stealth_flags(options)
            opera_path = os.path.join(
                os.environ["LOCALAPPDATA"],
                "Programs",
                "Opera",
                "opera.exe"
            )
            if not os.path.exists(opera_path):
                self.log_message("[ERROR] Opera not found on this system.")
                return None
            options.binary_location = opera_path
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            return webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )

        elif browser_choice == "operagx":
            options = webdriver.ChromeOptions()
            self.add_stealth_flags(options)
            opera_path = os.path.join(
                os.environ["LOCALAPPDATA"],
                "Programs",
                "Opera GX",
                "opera.exe"
            )
            if not os.path.exists(opera_path):
                self.log_message("[ERROR] Opera GX not found on this system.")
                return None
            options.binary_location = opera_path
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            return webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )

        return None

    def add_stealth_flags(self, options):
        flags = [
            # "--headless=new",
            "--window-size=1920x1080",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-client-side-phishing-detection"
        ]

        for f in flags:
            options.add_argument(f)

        # FIX: These were inside the loop — moved out so they only fire once
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

    def apply_stealth_patch(self, driver):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                    Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                """
            }
        )

    def fetch_playlist_csv(self, spotify_url, custom_name, download_dir, user_browser, user_source):
        """Automates the web converter based on the selected source."""
        os.makedirs(download_dir, exist_ok=True)
        driver = None

        try:
            driver = self.create_ghost_browser(user_browser, download_dir)
            if not driver:
                self.log_message(f"[ERROR] Failed to spawn {user_browser}.")
                return None

            self.apply_stealth_patch(driver)
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            wait = WebDriverWait(driver, 15)

            # --- THE ROUTER ---
            if user_source == "Spotify":
                return self.scrape_chosic(driver, wait, spotify_url, custom_name, download_dir)
            else:
                return self.scrape_tunemymusic(driver, wait, spotify_url, custom_name, download_dir, user_source)

        except Exception as e:
            raw_error = str(e)
            clean_error = raw_error.split("Stacktrace:")[0].strip()
            self.log_message(f"[ERROR] Automation halted:\n{clean_error}")
            return None
        finally:
            if driver:
                driver.quit()

    def scrape_chosic(self, driver, wait, url, custom_name, download_dir):
        """Dedicated engine for Spotify via Chosic."""
        self.log_message("Routing to Chosic.com for Spotify extraction...")
        driver.get("https://www.chosic.com/spotify-playlist-exporter/")

        # Let the page fully settle before we touch anything
        time.sleep(3)

        self.log_message("Pasting Spotify URL...")
        input_box = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@type='url'] | //input[contains(@placeholder, 'Spotify')]")))

        # Type character-by-character like a human instead of dumping the whole string at once
        for char in url:
            input_box.send_keys(char)
            time.sleep(0.05)

        # Pause after typing so the page can validate the input field
        time.sleep(2)

        # Click the start button (using JS to bypass ads)
        analyze_btn = wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[contains(., 'Start')] | //input[@type='submit'] | //*[@id='analyze']")))
        driver.execute_script("arguments[0].click();", analyze_btn)

        # Give the server a moment to start processing before we watch for the CSV button
        time.sleep(2)

        self.log_message("Waiting for Chosic to generate the tracklist...")
        csv_btn = WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(., 'CSV')] | //button[contains(., 'CSV')]"))
        )

        # Pause before clicking export — jumping straight to it looks robotic
        time.sleep(1.5)
        self.log_message("Exporting CSV...")
        driver.execute_script("arguments[0].click();", csv_btn)

        # Give the browser a moment to actually start the download
        time.sleep(2)

        return self.wait_and_rename_file(download_dir, custom_name)

    def scrape_tunemymusic(self, driver, wait, url, custom_name, download_dir, source):
        """Dedicated engine for other services via TuneMyMusic."""
        self.log_message(f"Routing to TuneMyMusic.com for {source} extraction...")
        driver.get("https://www.tunemymusic.com/")

        # Let the page fully settle before we touch anything
        time.sleep(3)

        self.log_message("Selecting direct URL input...")
        url_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'URL')] | //a[contains(., 'URL')]")))
        driver.execute_script("arguments[0].click();", url_btn)

        # Pause after clicking the URL tab so the input field animates in
        time.sleep(1.5)

        self.log_message("Pasting URL...")
        input_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text'] | //textarea")))

        # Type character-by-character like a human
        for char in url:
            input_box.send_keys(char)
            time.sleep(0.05)

        # Pause after typing before submitting
        time.sleep(2)
        input_box.send_keys(u'\ue007')

        # Give the page a moment to react to the submit before we hunt for the next button
        time.sleep(2.5)

        self.log_message("Triggering CSV generation...")
        convert_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Convert') or contains(., 'Download')]")))

        # Brief pause before clicking — looks more natural
        time.sleep(1.5)
        driver.execute_script("arguments[0].click();", convert_btn)

        # Give the browser a moment to actually start the download
        time.sleep(2)

        return self.wait_and_rename_file(download_dir, custom_name)

    def wait_and_rename_file(self, download_dir, custom_name):
        """Waits for the CSV to arrive and renames it."""
        self.log_message("Waiting for file to hit the project folder...")
        timeout = time.time() + 30
        csv_files = []

        while time.time() < timeout:
            csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
            if csv_files:
                break
            time.sleep(1)

        if not csv_files:
            raise Exception("No CSV downloaded within timeout.")

        latest_file = max(csv_files, key=os.path.getctime)
        final_filepath = os.path.join(download_dir, f"{custom_name}.csv")

        if os.path.exists(final_filepath):
            os.remove(final_filepath)

        os.rename(latest_file, final_filepath)
        self.log_message(f"[SUCCESS] CSV saved as: {custom_name}.csv")
        return final_filepath

    def clean_query(self, text):
        """
        Strip noise from song/artist names that confuses YouTube search:
        featured artists, remaster tags, bracket junk, etc.
        """
        # Remove featured artist credits: (feat. X), (ft. X), (with X)
        text = re.sub(r'\(feat\.?\s+[^)]+\)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(ft\.?\s+[^)]+\)', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\(with\s+[^)]+\)', '', text, flags=re.IGNORECASE)
        # Remove version/edition tags: (Remastered 2019), (Radio Edit), (Live), (Remix), etc.
        text = re.sub(r'\((remaster(ed)?|live|remix|radio edit|acoustic|demo|explicit|album version)[^)]*\)', '', text,
                      flags=re.IGNORECASE)
        # Remove anything in square brackets: [Official Video], [HD], etc.
        text = re.sub(r'\[.*?\]', '', text)
        # Remove trailing dash separators that sometimes appear after stripping
        text = re.sub(r'\s*[-–]\s*$', '', text)
        return text.strip()

    def get_songs_from_file(self, filepath):
        """Parses the CSV for song names, with header detection and query cleaning."""
        songs = []
        if not os.path.exists(filepath):
            self.log_message(f"[ERROR] File not found: {filepath}")
            return songs

        with open(filepath, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            headers = next(reader, [])
            # Log the actual headers so you can verify column layout at a glance
            self.log_message(f"[CSV] Headers: {headers}")

            for row in reader:
                if row and len(row) >= 2:
                    title = self.clean_query(row[0])
                    artist = self.clean_query(row[1])
                    search_query = f"{title} {artist}".strip()
                    if search_query:
                        songs.append(search_query)
        return songs

    def download_with_fallback(self, song, output_dir):
        """Attempts SomeDL first, falls back to yt-dlp on failure."""
        self.log_message(f"\n---> Processing: {song}")

        original_dir = os.getcwd()
        os.chdir(output_dir)

        try:
            # 1. Primary: SomeDL
            subprocess.run(["somedl", song], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.log_message(f"[SUCCESS] SomeDL downloaded: {song}")

        except (subprocess.CalledProcessError, FileNotFoundError):
            self.log_message(f"[WARNING] SomeDL failed. Engaging yt-dlp fallback...")

            # 2. Rescue: yt-dlp
            # Search top 3 results and apply a duration filter (60s–600s) to skip
            # shorts, reaction videos, and hour-long mixes that pollute results.
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'outtmpl': '%(title)s.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'match_filter': yt_dlp.utils.match_filter_func("duration > 60 & duration < 600"),
                'playlist_items': '1',
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # ytsearch3 gives the filter more candidates to work with
                    # vs blindly grabbing #1 which could be a cover or skit
                    search_query = f"ytsearch3:{song}"
                    ydl.extract_info(search_query, download=True)
                self.log_message(f"[SUCCESS] yt-dlp rescued: {song}")
            except Exception as e:
                self.log_message(f"[ERROR] Completely failed to download {song}: {e}")

        finally:
            os.chdir(original_dir)


if __name__ == "__main__":
    app = AudioExtractorApp()
    app.mainloop()
