import csv
import glob
# import subprocess
import os
import threading
import time
# URL Checker
from urllib.parse import urlparse

import customtkinter as ctk
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

# import yt_dlp
# import urllib.parse
# import imageio_ffmpeg

# Set the modern dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

MUSIC_SOURCES = {
    "Apple Music": "//button[contains(@aria-label, 'Apple') or .//div[text()='Apple Music']]",
    "YouTube Music": "//button[contains(@aria-label, 'YouTube Music')]",
    "YouTube": "//button[contains(@aria-label, 'YouTube')]",
}


class AudioExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Audio Ripper")
        self.geometry("650x600")

        self.title_label = ctk.CTkLabel(self, text="Audio Extraction Pipeline", font=ctk.CTkFont(size=24, weight="bold"))
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
            ],
            width=200
        )
        self.source_dropdown.pack(pady=10)

        self.browser_dropdown.pack(pady=10)

        # --- THE KILL SWITCH FLAG ---
        self.cancel_flag = threading.Event()

        # The Progress Bar & Text
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.pack(pady=(10, 5))
        self.progress_bar.set(0)  # Keep it empty initially

        self.progress_label = ctk.CTkLabel(self, text="Ready", font=ctk.CTkFont(size=14))
        self.progress_label.pack(pady=(0, 10))

        # Button Frame (Puts Start and Stop side-by-side)
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(pady=10)

        self.start_button = ctk.CTkButton(self.button_frame, text="Start Extraction", command=self.start_pipeline,
                                          height=40)
        self.start_button.pack(side="left", padx=10)

        self.stop_button = ctk.CTkButton(self.button_frame, text="Stop", command=self.stop_pipeline, height=40,
                                         fg_color="darkred", hover_color="#8B0000", state="disabled")
        self.stop_button.pack(side="right", padx=10)

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

    def log_message(self, message, color=None):
        """Thread-safe log call with optional text color."""
        self.after(0, self._log_message, message, color)

    def _log_message(self, message, color):
        """Actual GUI update."""
        self.log_box.configure(state="normal")

        if color:
            # Create a custom tag for the color and apply it to this line
            self.log_box.tag_config(color, foreground=color)
            self.log_box.insert("end", str(message) + "\n", color)
        else:
            self.log_box.insert("end", str(message) + "\n")

        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def stop_pipeline(self):
        """Raises the cancel flag to stop the extraction loop."""
        self.log_message("\n[!] STOP SIGNAL RECEIVED. Finishing current task, then aborting...")
        self.cancel_flag.set()
        self.stop_button.configure(state="disabled")

    def update_progress(self, current, total):
        """Thread-safe update for the progress bar and label."""
        self.after(0, self._update_progress, current, total)

    def _update_progress(self, current, total):
        """Actual GUI update for progress."""
        fraction = current / total
        self.progress_bar.set(fraction)
        self.progress_label.configure(text=f"Extracting: {current} / {total}")

    def start_pipeline(self):
        url = self.url_entry.get().strip()
        name = self.name_entry.get().strip()
        browser = self.browser_var.get()
        source = self.source_var.get()
        base_dir = self.dir_entry.get()

        if not url or not name:
            self.log_message("[ERROR] Please fill in both the URL and Output File Name.")
            return

        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            self.log_message("[ERROR] Invalid URL. Please enter a full link.")
            return

        # Prepare UI for action
        self.cancel_flag.clear()  # Reset the kill switch
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.progress_label.configure(text="Scraping tracklist...")

        self.log_message(f"Starting pipeline for '{name}' using {browser.capitalize()}...\n" + "=" * 50)

        threading.Thread(
            target=self.run_engine,
            args=(url, name, browser, source, base_dir),
            daemon=True
        ).start()

    def run_engine(self, url, name, browser, source, base_dir):
        """The master pipeline that controls the flow."""
        project_folder = os.path.join(base_dir, name)

        # Step 1: Web Automation
        csv_path = self.fetch_playlist_csv(url, name, project_folder, browser, source)

        if csv_path and not self.cancel_flag.is_set():
            # Step 2: Read CSV
            song_list = self.get_songs_from_file(csv_path)
            total_songs = len(song_list)
            self.log_message(f"\nLoaded {total_songs} tracks. Starting audio extraction...")

            # Switch progress bar from bouncing to filling mode
            self.after(0, lambda: self.progress_bar.stop())
            self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
            self.update_progress(0, total_songs)

            # Step 3: Download Audio
            for index, track in enumerate(song_list):
                # CHECK THE KILL SWITCH
                if self.cancel_flag.is_set():
                    self.log_message("[!] Pipeline aborted by user.")
                    break

                self.download_with_fallback(track, project_folder)
                self.update_progress(index + 1, total_songs)

            if not self.cancel_flag.is_set():
                self.log_message(f"\nPipeline finished! All files are saved in: {project_folder}")
                self.after(0, lambda: self.progress_label.configure(text="Extraction Complete!"))
        else:
            if not self.cancel_flag.is_set():
                self.log_message("\n[FATAL ERROR] Pipeline halted because CSV fetch failed.")
                self.after(0, lambda: self.progress_label.configure(text="Failed."))

        # Stop the idling action and reset the UI!
        self.after(0, lambda: self.progress_bar.stop())
        self.after(0, lambda: self.progress_bar.set(0))
        self.after(0, lambda: self.start_button.configure(state="normal", text="Start Extraction"))
        self.after(0, lambda: self.stop_button.configure(state="disabled"))



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

            # Force the path to be an absolute Windows path
            abs_download_dir = os.path.abspath(download_dir)

            prefs = {
                "download.default_directory": abs_download_dir,
                "download.prompt_for_download": False,
                "profile.managed_default_content_settings.images": 2,
                "safebrowsing.enabled": True  # Tells Edge not to block the download!
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

            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")

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

    def add_stealth_flags(self,options):

        flags = [
            # TEMP "--headless=new"
            "--window-size=1920x1080",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-notifications",
            "--disable-blink-features=AutomationControlled",
            # "--disable-background-networking",
            #"--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            #"--disable-client-side-phishing-detection"
        ]

        for f in flags:
            options.add_argument(f)

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

    def apply_stealth_patch(self, driver):
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });

                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });

                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
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
        """Dedicated engine for Spotify via Chosic's Exporter."""
        self.log_message("Routing to Chosic.com for Spotify extraction...")
        driver.get("https://www.chosic.com/spotify-playlist-exporter/")

        # STEP 1: Paste the URL
        self.log_message("Pasting Spotify URL...")
        input_box = wait.until(EC.presence_of_element_located((
            By.XPATH, "//input[@type='url' or contains(translate(@placeholder, 'SPOTIFY', 'spotify'), 'spotify')]"
        )))
        input_box.clear()
        input_box.send_keys(url)
        time.sleep(1)

        # STEP 2: The Single, Clean Click
        self.log_message("Clicking Start...")
        start_btn = wait.until(EC.presence_of_element_located((
            By.XPATH, "//*[normalize-space(text())='Start' or contains(@value, 'Start')]"
        )))

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", start_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", start_btn)

        # STEP 3: The Anchor Word Wait (THE ULTIMATE FIX)
        self.log_message("Waiting for the Spotify data to finish rendering...")

        # This forces the bot to wait until the actual column headers generate!
        wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//*[normalize-space(text())='BPM' or normalize-space(text())='Popularity' or normalize-space(text())='Artist']"
        )))

        # STEP 4: Click Export (Using your exact XPath!)
        self.log_message("Tracklist locked in! Exporting CSV...")
        time.sleep(1)

        # THE FIX: The golden rule of scraping - if it has an ID, use it!
        csv_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="export"]')))

        # Scroll it into view and click
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", csv_btn)
        time.sleep(0.5)

        try:
            csv_btn.click()
        except:
            driver.execute_script("arguments[0].click();", csv_btn)

        # Hand off to our defensive file watcher!
        return self.wait_and_rename_file(download_dir, custom_name)

    def scrape_tunemymusic(self, driver, wait, url, custom_name, download_dir, source):
        """Dedicated engine for other services via TuneMyMusic."""
        self.log_message(f"Routing to TuneMyMusic.com for {source} extraction...")
        driver.get("https://www.tunemymusic.com/")

        # STEP 1: Click the source platform tile (e.g., YouTube)
        self.log_message(f"Selecting {source} tile...")
        target_xpath = MUSIC_SOURCES.get(source)

        # Make sure we actually have an XPath for this source
        if not target_xpath:
            self.log_message(f"[ERROR] Dictionary mismatch for {source}!")
            return None

        source_btn = wait.until(EC.element_to_be_clickable((By.XPATH, target_xpath)))

        # Scroll the tile into view before clicking to ensure it isn't hidden
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", source_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", source_btn)

        # YOUR FIX: Give the site 3 seconds to actually load the next page!
        time.sleep(3)

        # STEP 2: Paste URL into the right-side box
        self.log_message("Pasting URL into the input box...")
        # THE ARMOR: This XPath explicitly ignores any text box that has "Search" in the placeholder
        input_box = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//input[(not(contains(translate(@placeholder, 'SEARCH', 'search'), 'search'))) and (@type='text' or @type='url')]"
        )))
        input_box.clear()
        input_box.send_keys(url)
        time.sleep(1)

        # STEP 3: Click 'Load from URL'
        self.log_message("Clicking 'Load from URL'...")
        time.sleep(1)

        # STRICT MATCH: Removing the generic 'Load' fallback so it ignores the account button!
        load_url_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(., 'Load from URL')] | //a[contains(., 'Load from URL')] | //div[contains(., 'Load from URL') and @role='button']"
        )))

        # Scroll the button into the center of the screen before clicking
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", load_url_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", load_url_btn)

        # STEP 4: Click 'Choose Destination'
        self.log_message("Clicking 'Choose Destination'...")

        # We give this a special 20-second wait just in case it's a massive playlist that takes a while to load!
        choose_dest_btn = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[contains(., 'Choose Destination')] | //a[contains(., 'Choose Destination')]"
        )))

        # Scroll down to the bottom of the playlist to find the button
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", choose_dest_btn)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", choose_dest_btn)
        time.sleep(1)

        ## STEP 5: Click 'Export to file' tile
        self.log_message("Selecting 'Export to file'...")

        # Give the destination grid 1 second to fully animate and render
        time.sleep(1)

        # Target the exact text of the tile
        export_tile = wait.until(EC.presence_of_element_located((
            By.XPATH,
            "//*[normalize-space(text())='Export to file'] | //span[contains(text(), 'Export to file')] | //div[contains(text(), 'Export to file')]"
        )))

        # THE FIX: Scroll down to the bottom of the grid so the tile is actually visible!
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", export_tile)
        time.sleep(0.5)

        # Now click it
        driver.execute_script("arguments[0].click();", export_tile)

        # STEP 6: Choose CSV format in the popup
        self.log_message("Choosing CSV format...")
        # STRICT MATCH: Targeting the exact text or the description below it to grab the radio container
        csv_radio = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//*[normalize-space(text())='CSV'] | //*[contains(text(), 'Comma separated values')] | //label[contains(., 'CSV')]"
        )))
        driver.execute_script("arguments[0].click();", csv_radio)
        time.sleep(1)

        # STEP 7: Click 'Export' in the popup
        self.log_message("Confirming Export...")
        # STRICT MATCH: Mandates it MUST be a button tag, preventing it from clicking the 'Export file' header!
        export_confirm_btn = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            "//button[normalize-space()='Export'] | //div[@role='button' and normalize-space()='Export']"
        )))
        driver.execute_script("arguments[0].click();", export_confirm_btn)
        time.sleep(2)  # Give the modal time to physically close before moving to Step 8

        # STEP 8: Click 'Start Transfer'
        self.log_message("Starting conversion transfer...")
        start_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'START', 'start'), 'start')]")))
        driver.execute_script("arguments[0].click();", start_btn)

        # Give the server extra time to process the playlist before checking the folder
        time.sleep(5)

        # STEP 9: Wait for the file to drop!
        self.log_message("Waiting for server processing and download...")
        return self.wait_and_rename_file(download_dir, custom_name)

    def wait_and_rename_file(self, download_dir, custom_name):
        """Waits for the CSV to arrive and renames it safely without interrupting the browser."""
        self.log_message("Waiting for file to hit the project folder (up to 60s)...")
        timeout = time.time() + 60
        final_filepath = os.path.join(download_dir, f"{custom_name}.csv")

        while time.time() < timeout:
            # 1. Check if the browser is currently writing a temporary file
            temp_files = glob.glob(os.path.join(download_dir, "*.crdownload")) + glob.glob(
                os.path.join(download_dir, "*.part"))
            if temp_files:
                time.sleep(1)  # Let the browser finish writing!
                continue

            # 2. Look for the actual CSV
            csv_files = glob.glob(os.path.join(download_dir, "*.csv"))
            if csv_files:
                latest_file = max(csv_files, key=os.path.getctime)

                # If we already renamed it on a previous loop, we are done!
                if latest_file == final_filepath:
                    return final_filepath

                # 3. THE FIX: Try to rename safely. Catch the lock error!
                try:
                    if os.path.exists(final_filepath):
                        os.remove(final_filepath)
                    os.rename(latest_file, final_filepath)
                    self.log_message(f"[SUCCESS] CSV saved as: {custom_name}.csv")
                    return final_filepath
                except PermissionError:
                    # The browser hasn't let go of the file yet! Wait and loop again.
                    time.sleep(1)
                    continue

            time.sleep(1)

        raise Exception("No CSV downloaded within timeout.")

    def get_songs_from_file(self, csv_path):
        """Reads the CSV and builds a hyper-specific YouTube search query."""
        song_list = []

        try:
            # We use utf-8-sig to handle weird invisible characters Excel sometimes adds
            with open(csv_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                # Normalize all column headers to lowercase so we don't have to guess capitalization
                headers = [header.strip().lower() for header in reader.fieldnames if header]
                reader.fieldnames = headers

                for row in reader:
                    # 1. Clean the title
                    title = row.get('song') or row.get('track name') or ""

                    # 2. Extract ONLY the first artist (before the first comma)
                    # This prevents searching for "Mahito Yokota, Koji Kondo..."
                    artist_raw = row.get('artist') or row.get('artist name') or ""
                    primary_artist = artist_raw.split(',')[0].strip()

                    # 3. Handle specific Soundtrack logic (Optional but effective)
                    # If the song is from a game, often 'Album' or 'Genre' helps more than 'Artist'
                    album = row.get('album') or ""

                    if title:
                        # THE SEARCH SLEDGEHAMMER:
                        # Use Title + Primary Artist and avoid commas entirely
                        search_query = f"{title} {primary_artist}".replace(',', '').strip()
                        song_list.append(search_query)

            return song_list

        except Exception as e:
            self.log_message(f"[ERROR] Failed to read CSV: {e}")
            return []

    def download_with_fallback(self, track, download_dir):
        import urllib.parse
        import os
        import subprocess
        import yt_dlp
        import imageio_ffmpeg

        self.log_message(f"---> Processing: {track}")

        original_dir = os.getcwd()
        os.chdir(download_dir)

        # 1. Clean the track name of any illegal Windows filename characters
        safe_filename = track.translate(str.maketrans('', '', '<>:"/\\|?*'))

        # 2. DROP THE VIEW COUNT TAG: We want Relevance sorting based strictly on keywords!
        safe_query = urllib.parse.quote(track)
        search_url = f"https://www.youtube.com/results?search_query={safe_query}"

        ydl_opts = {
            'format': 'bestaudio/best',
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe(),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],

            # 3. THE NAMING FIX: Force yt-dlp to use our clean CSV string, not the YouTube title!
            'outtmpl': f'{safe_filename}.%(ext)s',

            'noplaylist': False,
            'playlist_items': '1',
            'quiet': True,
            'no_warnings': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(search_url, download=True)
            # Use green or default for success!
            self.log_message(f"[SUCCESS] yt-dlp downloaded: {safe_filename}", color="#00FF00")

        except Exception as e:
            # THE FIX: Print the exact track name and the yt-dlp error in RED!
            self.log_message(f"[WARNING] yt-dlp failed on '{track}': {e}", color="red")
            self.log_message(f"Engaging SomeDL fallback for '{track}'...", color="orange")

            try:
                subprocess.run(["somedl", track], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.log_message(f"[SUCCESS] SomeDL rescued: {track}", color="#00FF00")
            except subprocess.CalledProcessError:
                self.log_message(f"[FATAL ERROR] Completely failed to download '{track}'. Skipped.", color="red")

        finally:
            os.chdir(original_dir)

if __name__ == "__main__":
    app = AudioExtractorApp()
    app.mainloop()