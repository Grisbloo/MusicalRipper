import customtkinter as ctk
import threading
import subprocess
import os
import csv
import glob
import time
import yt_dlp

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# Chromium Imports
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
# Edge Imports
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
# Firefox Imports
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

# URL Checker
from urllib.parse import urlparse

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

    def start_pipeline(self):
        url = self.url_entry.get().strip()
        name = self.name_entry.get().strip()
        browser = self.browser_var.get()
        source = self.source_var.get()
        base_dir = self.dir_entry.get()

        if not url or not name:
            self.log_message("[ERROR] Please fill in both the URL and Output File Name.")
            return

        # --- NEW: Fail-Fast URL Validation ---
        parsed_url = urlparse(url)
        # A valid URL must have a scheme (http/https) and a network location (www.spotify.com)
        if not parsed_url.scheme or not parsed_url.netloc:
            self.log_message("[ERROR] Invalid URL. Please enter a full link (e.g., https://open.spotify.com/...)")
            return
        # -------------------------------------

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

            # Stop the idling action and reset the UI!
            self.progress_bar.stop()
            self.progress_bar.set(0)
            self.start_button.configure(state="normal", text="Start Extraction")
            self.start_button.configure(state="normal")



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
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-client-side-phishing-detection"
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
        """Dedicated engine for Spotify via Chosic."""
        self.log_message("Routing to Chosic.com for Spotify extraction...")
        driver.get("https://www.chosic.com/spotify-playlist-exporter/")

        self.log_message("Pasting Spotify URL...")
        input_box = wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@type='url'] | //input[contains(@placeholder, 'Spotify')]")))
        input_box.send_keys(url)

        #Add a wait here!!!!!!!!!! I think its to quickly attempting to hit start

        # Click the start button (using JS to bypass ads)
        analyze_btn = wait.until(
            EC.presence_of_element_located((By.XPATH, "//button[contains(., 'Start')] | //input[@type='submit'] | //*[@id='analyze']")))
        driver.execute_script("arguments[0].click();", analyze_btn)

        self.log_message("Waiting for Chosic to generate the tracklist...")
        # Give it a slightly longer wait since it has to analyze the playlist
        csv_btn = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(., 'CSV')] | //button[contains(., 'CSV')]"))
        )

        #!!!! I don't know if asking user for decision of .txt file or .csv matters!!!

        self.log_message("Exporting CSV...")
        driver.execute_script("arguments[0].click();", csv_btn)

        return self.wait_and_rename_file(download_dir, custom_name)

    def scrape_tunemymusic(self, driver, wait, url, custom_name, download_dir, source):
        """Dedicated engine for other services via TuneMyMusic."""
        self.log_message(f"Routing to TuneMyMusic.com for {source} extraction...")
        driver.get("https://www.tunemymusic.com/")

        self.log_message("Selecting direct URL input...")
        # You will still need the specific XPath for that gray '</> URL' button here!
        url_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'URL')] | //a[contains(., 'URL')]")))
        driver.execute_script("arguments[0].click();", url_btn)

        self.log_message("Pasting URL...")
        input_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text'] | //textarea")))
        input_box.send_keys(url)
        input_box.send_keys(u'\ue007')

        self.log_message("Triggering CSV generation...")
        convert_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Convert') or contains(., 'Download')]")))
        driver.execute_script("arguments[0].click();", convert_btn)

        return self.wait_and_rename_file(download_dir, custom_name)

    def wait_and_rename_file(self, download_dir, custom_name):
        """Waits for the CSV to arrive and renames it."""
        self.log_message("Waiting for file to hit the project folder...")
        timeout = time.time() + 30

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

    def get_songs_from_file(self, filepath):
        """Parses the CSV for song names."""
        songs = []
        if not os.path.exists(filepath):
            self.log_message(f"[ERROR] File not found: {filepath}")
            return songs

        with open(filepath, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None) # Skip headers
            for row in reader:
                if row:
                    search_query = f"{row[0]} {row[1]}"
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
            
        except subprocess.CalledProcessError:
            self.log_message(f"[WARNING] SomeDL failed. Engaging yt-dlp fallback...")
            
            # 2. Rescue: yt-dlp
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
                'outtmpl': '%(title)s.%(ext)s',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_query = f"ytsearch1:{song} Topic"
                    ydl.extract_info(search_query, download=True)
                self.log_message(f"[SUCCESS] yt-dlp rescued: {song}")
            except Exception as e:
                self.log_message(f"[ERROR] Completely failed to download {song}: {e}")
                
        finally:
            os.chdir(original_dir)

if __name__ == "__main__":
    app = AudioExtractorApp()
    app.mainloop()