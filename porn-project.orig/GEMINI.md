
# Gemini Project Context: porn-project

## Project Overview
This project consists of a Python-based web scraper designed to extract video metadata from a specific Pornhub user profile and export the data into a CherryTree XML format (`.chpl`). The script has been updated to generate an interactive HTML grid for viewing and managing videos instead of a CherryTree file.

### Main Technologies
- **Language:** Python 3
- **Libraries:**
  - `requests`: For handling HTTP requests.
  - `beautifulsoup4`: For parsing HTML content.
  - `yt_dlp`: For robust thumbnail extraction.
  - `json`: For handling category and manual video data.
  - `os`, `time`, `re`: For utility functions.

## Building and Running
To run the scraper and generate the HTML grid, ensure you have the necessary dependencies installed and execute the main Python script.

### Prerequisites
Install the required libraries:
```bash
pip install requests beautifulsoup4 yt_dlp
```

### Execution
Run the main script:
```bash
python get_pornhub_videos.py
```
This command will scrape videos from the hardcoded profile URL, search for specific tags, and fetch related videos. It generates an interactive HTML file named `z3ncoding_videos_grid.html` in the current directory.

## Development Conventions
- **Scraping Logic:** The script targets specific CSS selectors to extract video data from profile pages and search results. It also leverages `yt-dlp` for more reliable thumbnail fetching.
- **Output Format:** The primary output is an HTML file (`z3ncoding_videos_grid.html`) that displays videos in a sortable, filterable grid. User categorization and blacklisting are persisted in `localStorage` and can be exported/managed via the HTML interface. Metadata files like `categories.json`, `manual_videos.json`, and `blacklist.txt` are used for persistence.
- **Thumbnail Handling:** The script prioritizes reliable thumbnail extraction using `yt-dlp` and fallbacks, caching them locally in the `thumbs/` directory.
- **Error Handling:** Basic error handling is implemented for network requests and parsing.

## Key Files
- `get_pornhub_videos.py`: The main Python script for scraping and generating the HTML grid.
- `categories.json`: Stores user-defined categories for videos.
- `manual_videos.json`: Stores manually added video entries.
- `blacklist.txt`: Stores viewkeys of videos to be excluded from the grid.
- `z3ncoding_videos_grid.html`: The generated interactive HTML file.
- `thumbs/`: Directory for storing downloaded thumbnail images.

## Active Tasks / Todo
- [ ] Parameterize the target URL instead of hardcoding it.
- [ ] Add support for multiple pages of video results. (Note: The current script *does* support pagination up to a limit and search results, but the TODO might refer to something more advanced.)
- [ ] Enhance error logging and reporting.
