import subprocess
import os
import csv
import glob
import time
import yt_dlp

from selenium import webdriver

# Chromium Imports
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

# Edge Imports
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# Firefox Imports
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager

# Factory to clear all browser types to enable any type of browser as defaulted to run selenium
def create_ghost_browser(browser_choice, download_dir):
    """Spawns a configured browser based on user input."""
    browser_choice = browser_choice.lower()
    download_dir = os.path.abspath(download_dir)
    os.makedirs(download_dir, exist_ok=True)

    print(f"Initializing {browser_choice.capitalize()} driver...")

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
        # You have to point directly to the Brave executable since it uses the Chrome driver
        options.binary_location = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" 
        return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

    elif browser_choice == "firefox":
        options = webdriver.FirefoxOptions()
        # Firefox uses an entirely different system for setting download preferences
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.manager.showWhenStarting", False)
        options.set_preference("browser.download.dir", download_dir)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/csv")
        return webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)

    else:
        print(f"[ERROR] Unsupported browser: {browser_choice}. Defaulting to Chrome.")
        return create_ghost_browser("chrome", download_dir)

def fetch_playlist_csv(spotify_url, custom_name, download_dir, user_browser):
    print(f"\n{'='*50}")
    
    # Spawn the exact browser the user asked for
    driver = create_ghost_browser(user_browser, download_dir)
    wait = WebDriverWait(driver, 15)
    """Automates a web converter to turn a Spotify link into a CSV."""
    print(f"\n{'='*50}")
    print("Firing up the ghost browser...")

    # 1. Configure Chrome to download directly to our specific folder silently
    os.makedirs(download_dir, exist_ok=True)
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "directory_upgrade": True
    }
    options.add_experimental_option("prefs", prefs)
    # options.add_argument("--headless") # Uncomment this later to make it truly invisible!

    # 2. Launch the Browser
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    wait = WebDriverWait(driver, 15) # Wait up to 15 seconds for elements to load

    try:
        # NOTE: This uses theoretical XPATHs for a site like TuneMyMusic. 
        # Web layouts change, so you may need to update these locators using "Inspect Element"
        print("Navigating to converter website...")
        driver.get("https://www.tunemymusic.com/") 

        # Example flow: Click "Start" -> Select "Spotify" -> Paste URL -> Export -> CSV
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Let\'s Start')]"))).click()
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-source='spotify']"))).click()
        
        # input_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@type='text']")))
        # input_box.send_keys(spotify_url)
        
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Load Playlist')]"))).click()
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Export')]"))).click()
        # wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), 'CSV')]"))).click()
        
        print("Simulating CSV Download (You will map the exact buttons above!)")
        time.sleep(5) # Give the file time to finish downloading

        # 3. Find the newly downloaded CSV and rename it
        search_pattern = os.path.join(download_dir, "*.csv")
        list_of_csvs = glob.glob(search_pattern)
        
        if not list_of_csvs:
            raise Exception("Download failed. No CSV found in the folder.")
            
        latest_file = max(list_of_csvs, key=os.path.getctime)
        final_filepath = os.path.join(download_dir, f"{custom_name}.csv")
        
        if os.path.exists(final_filepath):
            os.remove(final_filepath)
            
        os.rename(latest_file, final_filepath)
        print(f"[SUCCESS] Playlist saved as: {final_filepath}")
        return final_filepath

    except Exception as e:
        print(f"[ERROR] Browser automation failed: {e}")
        return None
    finally:
        driver.quit() # Always kill the ghost browser so it doesn't eat your RAM


def get_songs_from_file(filepath):
    """Parses .txt or .csv files and returns a list of song queries."""
    songs = []
    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        return songs

    _, ext = os.path.splitext(filepath)
    if ext.lower() == '.csv':
        with open(filepath, "r", encoding="utf-8") as file:
            reader = csv.reader(file)
            next(reader, None) # Skip header row
            for row in reader:
                if row:
                    search_query = " ".join(row).strip()
                    if search_query:
                        songs.append(search_query)
    return songs


def download_with_fallback(song, output_dir):
    """Attempts SomeDL first, falls back to yt-dlp on failure."""
    print(f"\n{'='*50}\n---> Processing: {song}")
    
    # Run the processes from the specific output directory
    original_dir = os.getcwd()
    os.chdir(output_dir)
    
    try:
        # 1. THE PRIMARY: SomeDL
        subprocess.run(["somedl", song], check=True)
        print(f"[SUCCESS] SomeDL nailed it: {song}")
        
    except subprocess.CalledProcessError:
        print(f"[WARNING] SomeDL failed on '{song}'. Engaging yt-dlp fallback...")
        
        # 2. THE RESCUE: yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
            'outtmpl': '%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True 
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_query = f"ytsearch1:{song} Topic"
                ydl.extract_info(search_query, download=True)
            print(f"[SUCCESS] yt-dlp rescued: {song}")
            
        except Exception as e:
            print(f"[ERROR] Both systems failed for {song}: {e}")
            
    finally:
        os.chdir(original_dir) # Always return to the root folder


if __name__ == "__main__":
    print("Welcome to the Audio Extraction Pipeline")
    target_url = input("Paste your Spotify Playlist URL: ")
    playlist_name = input("What would you like to name the output file? ")
    
    project_folder = os.path.join(os.getcwd(), playlist_name)
    
    # Step 1: Automate the Web and get the CSV
    csv_path = fetch_playlist_csv(target_url, playlist_name, project_folder)
    
    if csv_path:
        # Step 2: Read the CSV
        song_list = get_songs_from_file(csv_path)
        print(f"\nLoaded {len(song_list)} tracks. Starting audio extraction...\n")
        
        # Step 3: Download everything
        for track in song_list:
            download_with_fallback(track, project_folder)
            
        print(f"\nPipeline finished! All files are saved in: {project_folder}")