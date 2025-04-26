# Web Form Filler

This project is a Python application designed to automate the process of filling web forms using Playwright for browser automation and Tkinter for the graphical user interface (GUI). The application allows users to input data from a CSV file and fill out forms on specified websites.

## Features

- User-friendly GUI for selecting data files and configuring settings.
- Automation of web form filling using Playwright.
- Support for CSV data input.
- Logging of actions and errors for troubleshooting.

## Installation Instructions

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd web_form_filler
   ```

2. **Set up a virtual environment (optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install the required packages:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers:**
   After installing the Playwright package, you need to install the necessary browsers. Run the following command:
   ```bash
   playwright install
   ```

5. **Run the application:**
   ```bash
   python form_filler.py
   ```

## Usage

- Launch the application and select a CSV file containing the data to be filled in the web forms.
- Enter the URL of the website where the form is located.
- Configure any additional settings such as delays and maximum retries.
- Click the "Start" button to begin the automation process.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.