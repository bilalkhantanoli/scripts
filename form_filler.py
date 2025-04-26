import os
import sys
import time
import logging
import pandas as pd
import csv
import json
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, simpledialog
from threading import Thread, Event

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='form_filler.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

class FormFillerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Web Form Filler")
        self.root.geometry("650x450")
        self.root.resizable(True, True)
        
        self.file_path = tk.StringVar()
        self.website_url = tk.StringVar()
        self.delay_time = tk.DoubleVar(value=0.5)
        self.between_forms_delay = tk.IntVar(value=2)
        self.max_retries = tk.IntVar(value=3)
        self.file_type = tk.StringVar(value="csv")
        self.max_entries_to_process = tk.IntVar(value=0) # 0 means process all
        self.web_password = tk.StringVar()
        
        self.automation_thread = None
        self.stop_event = Event()
        self.pause_event = Event()
        self.pause_event.set()  # Not paused initially
        
        self.setup_ui()
    
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # File selection
        file_frame = ttk.LabelFrame(main_frame, text="Data File (CSV Only)", padding="10")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Entry(file_frame, textvariable=self.file_path, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT, padx=5)
        
        # Website URL
        url_frame = ttk.LabelFrame(main_frame, text="Website URL", padding="10")
        url_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Entry(url_frame, textvariable=self.website_url, width=50).pack(side=tk.LEFT, padx=5)

        # Password (if required)
        password_frame = ttk.LabelFrame(main_frame, text="Password (if required)", padding="10")
        password_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(password_frame, text="Password:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(password_frame, textvariable=self.web_password, show="*", width=30).pack(side=tk.LEFT, padx=5)
        
        # Settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="Delay between field inputs (seconds):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=0.1, to=5.0, increment=0.1, textvariable=self.delay_time, width=5).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(settings_frame, text="Delay between forms (seconds):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=1, to=10, textvariable=self.between_forms_delay, width=5).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(settings_frame, text="Max retries on failure:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=1, to=5, textvariable=self.max_retries, width=5).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        
        # --- New Entry for Number of Entries ---
        ttk.Label(settings_frame, text="Number of entries to process (0 for all):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Spinbox(settings_frame, from_=0, to=99999, textvariable=self.max_entries_to_process, width=7).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        # --- End New Entry ---

        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Progress", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.progress_bar = ttk.Progressbar(progress_frame, orient="horizontal", length=100, mode="determinate")
        self.progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(padx=5, pady=5)
        
        self.progress_text = tk.Text(progress_frame, height=6, width=60, state="disabled")
        self.progress_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_automation)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.toggle_pause, state="disabled")
        self.pause_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_automation, state="disabled")
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def browse_file(self):
        filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
            
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.file_path.set(file_path)
            self.file_type.set("csv")

    def log_message(self, message):
        self.progress_text.configure(state="normal")
        self.progress_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.configure(state="disabled")
        logger.info(message)
    
    def update_status(self, message):
        self.status_label.config(text=message)
    
    def start_automation(self):
        if not self.file_path.get():
            messagebox.showerror("Error", "Please select a CSV data file")
            return
        
        if not self.website_url.get():
            messagebox.showerror("Error", "Please enter the website URL")
            return
        
        self.stop_event.clear()
        self.pause_event.set()
        
        self.start_button.config(state="disabled")
        self.pause_button.config(state="normal")
        self.stop_button.config(state="normal")
        
        self.progress_text.configure(state="normal")
        self.progress_text.delete(1.0, tk.END)
        self.progress_text.configure(state="disabled")
        
        self.automation_thread = Thread(target=self.run_automation)
        self.automation_thread.daemon = True
        self.automation_thread.start()
    
    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_button.config(text="Resume")
            self.log_message("Automation paused")
        else:
            self.pause_event.set()
            self.pause_button.config(text="Pause")
            self.log_message("Automation resumed")
    
    def stop_automation(self):
        if self.automation_thread and self.automation_thread.is_alive():
            self.stop_event.set()
            self.log_message("Stopping automation...")
    
    def on_closing(self):
        if self.automation_thread and self.automation_thread.is_alive():
            if messagebox.askyesno("Quit", "Automation is running. Do you want to stop and quit?"):
                self.stop_event.set()
                self.automation_thread.join(2)
                self.root.destroy()
        else:
            self.root.destroy()
    
    def load_data(self):
        file_path = self.file_path.get()
        file_type = "csv"
        
        try:
            if file_type == "csv":
                with open(file_path, 'r', newline='') as f:
                    sample = f.read(8192)
                
                try:
                    dialect = csv.Sniffer().sniff(sample)
                    delimiter = dialect.delimiter
                    self.log_message(f"Detected CSV delimiter: '{delimiter}'")
                except csv.Error:
                    self.log_message("Could not detect CSV delimiter, assuming comma ','")
                    delimiter = ','

                df = pd.read_csv(file_path, delimiter=delimiter, header=None)
                
                headers = ['first_name', 'last_name', 'gender', 'age', 'id']
                if len(df.columns) != len(headers):
                    headers = [f'col_{i}' for i in range(len(df.columns))]
                df.columns = headers
                
            return df
        
        except Exception as e:
            self.log_message(f"Error loading data file: {str(e)}")
            raise
    
    def run_automation(self):
        try:
            self.update_status("Loading data file...")
            self.log_message(f"Loading data from {self.file_path.get()}")
            
            try:
                df_full = self.load_data() # Load the full dataframe first
                total_loaded = len(df_full)
                self.log_message(f"Loaded {total_loaded} total entries from file")

                # --- Limit number of entries based on user input ---
                num_to_process = self.max_entries_to_process.get()
                if num_to_process > 0 and num_to_process < total_loaded:
                    df = df_full.head(num_to_process)
                    total_entries = num_to_process
                    self.log_message(f"Processing the first {total_entries} entries as requested.")
                else:
                    df = df_full # Process all
                    total_entries = total_loaded
                    if num_to_process > 0:
                         self.log_message(f"Requested number ({num_to_process}) is >= total entries ({total_loaded}). Processing all.")
                    else:
                         self.log_message("Processing all entries.")
                # --- End limiting entries ---


                column_names = ', '.join(df.columns.tolist())
                self.log_message(f"Columns being processed: {column_names}")

            except Exception as e:
                self.log_message(f"Error loading data file: {str(e)}")
                messagebox.showerror("Error", f"Failed to load data file: {str(e)}")
                self.reset_ui()
                return

            self.progress_bar["maximum"] = total_entries # Use the potentially reduced count
            self.progress_bar["value"] = 0
            
            self.log_message(f"Starting automation for website: {self.website_url.get()}")
            
            with sync_playwright() as playwright:
                browser = None
                try:
                    browser = playwright.chromium.launch(headless=False)
                    context = browser.new_context()
                    page = context.new_page()
                    
                    self.log_message(f"Navigating to {self.website_url.get()}")
                    page.goto(self.website_url.get(), wait_until='networkidle') # Wait for network idle on initial load
                    
                    if self.web_password.get():
                        try:
                            self.log_message("Password provided, attempting automatic login...")
                            
                            # Wait for page to load completely
                            page.wait_for_load_state('networkidle')
                            
                            # First attempt - look for password field directly in main document
                            pw_field_exists = page.locator('input[type="password"]').count() > 0
                            
                            if pw_field_exists:
                                # Password field found directly on page
                                self.log_message("Found password field in main document")
                                pw_input = page.locator('input[type="password"]').first
                                pw_input.fill(self.web_password.get())
                                
                                # Find the nearest form or submit button
                                submit_button = page.locator('button[type="submit"], input[type="submit"]').first
                                if submit_button:
                                    submit_button.click()
                                    self.log_message("Submitted password form, waiting for login to complete...")
                                else:
                                    # Try to submit using Enter key if no submit button found
                                    pw_input.press("Enter")
                                    self.log_message("Submit button not found, pressed Enter key instead")
                            else:
                                # Check for iframes
                                self.log_message("Password field not found in main document, checking iframes...")
                                frames = page.frames
                                self.log_message(f"Found {len(frames)} frames in the page")
                                
                                for frame in frames:
                                    try:
                                        # Check if this frame has a password field
                                        if frame.locator('input[type="password"]').count() > 0:
                                            self.log_message(f"Found password field in iframe")
                                            frame.locator('input[type="password"]').first.fill(self.web_password.get())
                                            
                                            # Try to find a submit button
                                            if frame.locator('button[type="submit"], input[type="submit"]').count() > 0:
                                                frame.locator('button[type="submit"], input[type="submit"]').first.click()
                                                self.log_message("Submitted password form in iframe, waiting for login to complete...")
                                                break
                                            else:
                                                # Try to submit using Enter key if no submit button found
                                                frame.locator('input[type="password"]').first.press("Enter")
                                                self.log_message("Submit button not found in iframe, pressed Enter key instead")
                                                break
                                    except Exception as frame_err:
                                        self.log_message(f"Error checking iframe: {frame_err}")
                                        continue
                            
                            # Wait for login to complete - look for content that indicates success
                            page.wait_for_load_state('networkidle')
                            page.wait_for_timeout(5000)  # Give it 5 seconds to settle
                            
                            # Check for successful login by looking for the form iframe
                            if page.locator('iframe[src*="emailmeform.com"]').count() > 0 or page.locator('#element_0').count() > 0:
                                self.log_message("Login successful, proceeding to form filling.")
                            else:
                                # Take a screenshot for debugging
                                screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "login_debug.png")
                                page.screenshot(path=screenshot_path)
                                self.log_message(f"Login may have failed. Saved screenshot to {screenshot_path}")
                                
                                # Ask user to confirm if login was successful
                                login_confirmed = Event()
                                def ask_login_confirmation():
                                    result = messagebox.askyesno("Login Check", 
                                                                "Was the login successful? Click Yes to continue, No to abort.")
                                    if result:
                                        login_confirmed.set()
                                    else:
                                        self.stop_event.set()
                                self.root.after(0, ask_login_confirmation)
                                login_confirmed.wait()
                                
                                if self.stop_event.is_set():
                                    self.log_message("User indicated login failed. Aborting.")
                                    self.reset_ui()
                                    return
                        
                        except Exception as e:
                            self.log_message(f"Automatic login failed: {e}")
                            
                            # Fall back to manual login
                            self.log_message("Falling back to manual login...")
                            login_confirmed = Event()
                            def show_login_prompt():
                                messagebox.showinfo("Manual Login Required",
                                                  "Automatic login failed. Please log in manually in the browser window. Click OK when finished.")
                                login_confirmed.set()
                            self.root.after(0, show_login_prompt)
                            login_confirmed.wait()
                            
                            self.log_message("User confirmed manual login. Adding a longer wait (5s) for page elements to load...")
                            page.wait_for_timeout(5000)
                    else:
                        self.log_message("No password provided, waiting for manual login...")
                        self.update_status("Waiting for manual login...")
                        login_confirmed = Event()
                        def show_login_prompt():
                            messagebox.showinfo("Manual Login Required",
                                "Please log in to the website in the browser window. Click OK here when you are logged in and ready to proceed.")
                            login_confirmed.set()
                        self.root.after(0, show_login_prompt)
                        login_confirmed.wait()
                        self.log_message("User confirmed login. Adding a longer wait (5s) for page elements to load...")
                        page.wait_for_timeout(5000)

                    self.log_message("Looking for the form iframe...")
                    try:
                        # Wait for the iframe to appear
                        iframe_locator = page.locator('iframe[src*="emailmeform.com"]')
                        iframe_locator.wait_for(state="attached", timeout=20000)
                        self.log_message("Form iframe found. Switching context.")
                        # Get the frame object
                        frame = None
                        for f in page.frames:
                            if "emailmeform.com" in f.url:
                                frame = f
                                break
                        if not frame:
                            raise Exception("Form iframe not found after login.")
                    except Exception as e:
                        self.log_message(f"Error: Could not find or switch to the form iframe: {e}")
                        self.update_status("Error: Form iframe not found.")
                        raise Exception("Form iframe not found after login.")

                    # Now check for #element_0 inside the iframe
                    try:
                        self.log_message("Checking if the initial form element (#element_0) is present in the iframe...")
                        frame.locator("#element_0").wait_for(state="visible", timeout=20000)
                        self.log_message("Initial form element found in iframe. Proceeding with form filling.")
                    except PlaywrightTimeoutError:
                        self.log_message("Error: Initial form element (#element_0) did not become visible in iframe. Aborting.")
                        self.update_status("Error: Form not loaded in iframe.")
                        raise Exception("Initial form element #element_0 not found in iframe after login.")

                    self.update_status("Starting form filling...")

                    success_count = 0
                    failure_count = 0

                    for idx, row in df.iterrows(): # Pass idx to fill_form
                        if self.stop_event.is_set():
                            self.log_message("Automation stopped by user")
                            break
                        
                        while not self.pause_event.is_set() and not self.stop_event.is_set():
                            time.sleep(0.5)
                        
                        if self.stop_event.is_set():
                            continue
                        
                        entry_num = idx + 1
                        self.update_status(f"Processing entry {entry_num} of {total_entries}")
                        entry_dict = row.to_dict()
                        self.log_message(f"Processing entry {entry_num}: {entry_dict}")
                        
                        retries = 0
                        success = False
                        
                        while retries < self.max_retries.get() and not success:
                            try:
                                # Pass the index (idx) to fill_form
                                self.fill_form(frame, row, idx) # pass frame instead of page

                                self.log_message(f"Successfully filled form {entry_num} (elements {idx*5}-{idx*5+4})") # Updated log
                                success = True
                                success_count += 1

                                delay = self.between_forms_delay.get()
                                if entry_num < total_entries:
                                    self.log_message(f"Waiting {delay} seconds before processing next entry")
                                    time.sleep(delay)

                            except Exception as e:
                                retries += 1
                                self.log_message(f"Error processing entry {entry_num} (elements {idx*5}-{idx*5+4}): {str(e)}, retry {retries}") # Updated log
                                if retries >= self.max_retries.get():
                                    self.log_message(f"Failed to process entry {entry_num} after {retries} attempts")
                                    failure_count += 1
                                    # Optional: Add a small delay before retrying the same form block
                                    time.sleep(1)
                                else:
                                     # Optional: Add a small delay before retrying the same form block
                                     time.sleep(0.5)


                        self.progress_bar["value"] = entry_num
                        self.root.update_idletasks()
                
                    # Replace the completion message and keep browser open:
                    if not self.stop_event.is_set():
                        self.log_message("All entries processed!")
                        self.update_status("Completed - Browser remains open")
                        
                        # Create a persistent flag to prevent browser from closing
                        keep_browser_open = Event()
                        
                        def show_completion():
                            nonlocal keep_browser_open
                            messagebox.showinfo("Complete", f"Form filling completed.\nSuccessful: {success_count}\nFailed: {failure_count}\n\nThe browser will remain open until you click Close Browser.")
                            # Create a new window with a "Close Browser" button
                            browser_window = tk.Toplevel(self.root)
                            browser_window.title("Browser Control")
                            browser_window.geometry("300x100")
                            browser_window.resizable(False, False)
                            
                            message = ttk.Label(browser_window, text="Browser window is kept open.\nClick 'Close Browser' when done.")
                            message.pack(pady=10)
                            
                            def close_browser_and_window():
                                try:
                                    if browser and browser.is_connected():
                                        browser.close()
                                        self.log_message("Browser closed by user.")
                                    browser_window.destroy()
                                    keep_browser_open.set()
                                except Exception as e:
                                    self.log_message(f"Error closing browser: {e}")
                                    browser_window.destroy()
                                    keep_browser_open.set()
                            
                            close_button = ttk.Button(browser_window, text="Close Browser", command=close_browser_and_window)
                            close_button.pack(pady=10)
                            
                            # Make sure the window stays on top
                            browser_window.transient(self.root)
                            browser_window.grab_set()
                        
                        # Show completion message in main thread
                        self.root.after(0, show_completion)
                        
                        # This will block until the user closes the browser
                        keep_browser_open.wait()
                    else:
                        self.log_message("Automation stopped before completion.")
                        self.update_status("Stopped")
        
                except Exception as browser_err:
                    self.log_message(f"Browser/Navigation error: {str(browser_err)}")
                    messagebox.showerror("Error", f"An error occurred with the browser: {str(browser_err)}")
                    self.log_message("Browser window kept open for inspection despite error")
                    self.reset_ui()
                    return
        
        except Exception as e:
            self.log_message(f"Automation error: {str(e)}")
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.log_message("Browser window kept open for inspection despite error")
            self.reset_ui()
        finally:
            if self.stop_event.is_set():
                 self.reset_ui()
            elif 'e' not in locals() and not self.stop_event.is_set():
                 self.start_button.config(state="disabled")
                 self.pause_button.config(state="disabled", text="Pause")
                 self.stop_button.config(state="disabled")
    
    def fill_form(self, frame, row_data, idx):
        # Each form block: 5 fields (element_{base} to element_{base+4}), then h3 (element_{base+5})
        base_index = idx * 6
        field_details = {
            0: (0, 'text'),    # First Name  -> element_{base+0}
            1: (1, 'text'),    # Last Name   -> element_{base+1}
            2: (2, 'select'),  # Gender      -> element_{base+2}
            3: (3, 'text'),    # Age         -> element_{base+3}
            4: (4, 'text')     # ID/Phone    -> element_{base+4}
        }
        for col_index, value in enumerate(row_data):
            if col_index in field_details and not pd.isna(value):
                offset, field_type = field_details[col_index]
                element_id = f"element_{base_index + offset}"
                selector = f"input#{element_id}, select#{element_id}, textarea#{element_id}"
                value_str = str(value).strip()
                element_description = f"field {col_index+1} ({element_id})"
                try:
                    self.log_message(f"Attempting to locate {element_description} with selector: {selector}")
                    field = frame.locator(selector)
                    field.wait_for(state="visible", timeout=10000)
                    if field.count() > 0:
                        tag_name = field.evaluate("(element) => element.tagName.toLowerCase()", timeout=5000)
                        if field_type == 'select' and tag_name == 'select':
                            try:
                                field.select_option(value=value_str, timeout=5000)
                                self.log_message(f"Selected option by value for {element_description}: {value_str}")
                            except PlaywrightTimeoutError:
                                try:
                                    field.select_option(label=value_str, timeout=5000)
                                    self.log_message(f"Selected option by label for {element_description}: {value_str}")
                                except PlaywrightTimeoutError:
                                    self.log_message(f"Could not select option for {element_description} by value or label. Trying to fill.")
                                    field.fill(value_str, timeout=5000)
                                except Exception as select_err:
                                    self.log_message(f"Specific error selecting option for {element_description}: {select_err}")
                                    raise
                        else:
                            field.fill(value_str, timeout=5000)
                            self.log_message(f"Filled {element_description} with value: {value_str}")
                        time.sleep(self.delay_time.get())
                    else:
                        self.log_message(f"Could not find element {element_description} ({selector})")
                        raise Exception(f"Element not found: {selector}")
                except PlaywrightTimeoutError:
                    self.log_message(f"Timeout waiting for or interacting with {element_description} ({selector})")
                    raise Exception(f"Timeout interacting with {selector}")
                except Exception as e:
                    self.log_message(f"Error interacting with {element_description} ({selector}): {str(e)}")
                    raise

    def reset_ui(self):
        self.start_button.config(state="normal")
        self.pause_button.config(state="disabled", text="Pause")
        self.stop_button.config(state="disabled")
        self.pause_event.set()
        self.update_status("Ready")

if __name__ == "__main__":
    root = tk.Tk()
    app = FormFillerApp(root)
    root.mainloop()