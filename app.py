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

# Set the modern dark theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AudioExtractorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Spotify to FMOD Audio Ripper")
        self.geometry("650x600")

        self.title_label = ctk.CTkLabel(self, text="Audio Extraction Pipeline", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        self.url_entry = ctk.CTkEntry(self, placeholder_text="Paste Spotify Playlist URL here...", width=500)
        self.url_entry.pack(pady=10)

        self.name_entry = ctk.CTkEntry(self, placeholder_text="Project / Output Folder Name", width=500)
        self.name_entry.pack(pady=10)

        self.browser_var = ctk.StringVar(value="chrome")
        self.browser_dropdown = ctk.CTkOptionMenu(
            self, 
            variable=self.browser_var, 
            values=["chrome", "edge", "brave", "firefox"],
            width=200
        )
        self.browser_dropdown.pack(pady=10)

        self.start_button = ctk.CTkButton(self, text="Start Extraction", command=self.start_pipeline, height=40)
        self.start_button.pack(pady=20)

        self.log_box = ctk.CTkTextbox(self, width=550, height=200, state="disabled")
        self.log_box.pack(pady=(10, 20))

    def log_message(self, message):
        """Pushes text to the GUI log box."""
        self.log_box.configure(state="normal")
        self.log_box.insert("end", str(message) + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def start_pipeline(self):
        url = self.url_entry.get().strip()
        name = self.name_entry.get().strip()
        browser = self.browser_var.get()

        if not url or not name:
            self.log_message("[ERROR] Please fill in both the URL and Project Name.")
            return

        self.start_button.configure(state="disabled")
        self.log_message(f"Starting pipeline for '{name}' using {browser.capitalize()}...\n" + "="*50)

        # Run the engine in the background
        threading.Thread(target=self.run_engine, args=(url, name, browser), daemon=True).start()

    def run_engine(self, url, name, browser):
        """The master pipeline that controls the flow."""
        project_folder = os.path.join(os.getcwd(), name)
        
        # Step 1: Web Automation
        csv_path = self.fetch_playlist_csv(url, name, project_folder, browser)
        
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
            
        self.start_button.configure(state="normal")

    def create_ghost_browser(self, browser_choice, download_dir):
        """Spawns the requested browser using the factory pattern."""
        browser_choice = browser_choice.lower()
        self.log_message(f"Initializing {browser_choice.capitalize()} driver...")

        if browser_choice == "chrome":
            options = webdriver.ChromeOptions()
            prefs = {"download.default_directory": download_dir, "download.prompt_for_download": False}
            options.add_experimental_option("prefs", prefs)
            return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        elif browser_choice == "edge":
            options = webdriver.EdgeOptions()
            prefs = {"download.default_directory": download_dir, "download.prompt_for_download": False}
            options.add_experimental_option("prefs", prefs)
            return webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=options)

        elif browser_choice == "brave":
            options = webdriver.ChromeOptions()
            prefs = {"download.default_directory": download_dir, "download.prompt_for_download": False}
            options.add_experimental_option("prefs", prefs)
            options.binary_location = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" 
            return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        elif browser_choice == "firefox":
            options = webdriver.FirefoxOptions()
            options.set_preference("browser.download.folderList", 2)
            options.set_preference("browser.download.manager.showWhenStarting", False)
            options.set_preference("browser.download.dir", download_dir)
            options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv")
            return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
        
        return None

    def fetch_playlist_csv(self, spotify_url, custom_name, download_dir, user_browser):
        """Automates the web converter."""
        os.makedirs(download_dir, exist_ok=True)
        driver = self.create_ghost_browser(user_browser, download_dir)
        
        if not driver:
            self.log_message("[ERROR] Failed to spawn browser.")
            return None

        wait = WebDriverWait(driver, 15)
        
        try:
            self.log_message("Navigating to converter website...")
            driver.get("https://www.tunemymusic.com/") 

            # TODO: Add your custom XPATH clicking logic here!
            # Example:
            # wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Let\'s Start')]"))).click()
            
            self.log_message("Simulating CSV Download (Waiting 10 seconds)...")
            time.sleep(10) # Gives the file time to download

            # Find and rename the downloaded file
            search_pattern = os.path.join(download_dir, "*.csv")
            list_of_csvs = glob.glob(search_pattern)
            
            if not list_of_csvs:
                raise Exception("No CSV found in the folder.")
                
            latest_file = max(list_of_csvs, key=os.path.getctime)
            final_filepath = os.path.join(download_dir, f"{custom_name}.csv")
            
            if os.path.exists(final_filepath):
                os.remove(final_filepath)
                
            os.rename(latest_file, final_filepath)
            self.log_message(f"[SUCCESS] CSV saved as: {custom_name}.csv")
            return final_filepath

        except Exception as e:
            self.log_message(f"[ERROR] Browser automation failed: {e}")
            return None
        finally:
            driver.quit()

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
                    search_query = " ".join(row).strip()
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