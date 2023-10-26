# Import necessary libraries

import requests  # Library for making HTTP requests
import threading  # Library for creating and managing threads
import argparse  # Library for parsing command-line arguments
import queue  # Library for thread-safe queues
import signal  # Library for handling signals (e.g., Ctrl+C)
import readchar  # Library for reading character input
import os  # Library for interacting with the operating system
from colorama import init, Fore, Style  # Library for colored console output

# Initialize colorama for colored output
init(autoreset=True)

# Global variables
scanning_in_progress = True  # Flag to track if scanning is in progress
scanned_dirs = set()  # Set to store scanned directories
found_dirs = set()  # Set to store found directories
q = queue.Queue()  # Queue for directory entries
threads = []  # List to store worker threads
output_lock = threading.Lock()  # Lock for thread-safe printing
'''
In the context of the code you provided, output_lock is used to ensure that when 
multiple threads are running and trying to print messages to the console using the print_colored() function,
only one thread can perform the printing operation at a time. 
This prevents the printed messages from being mixed or garbled due to concurrent access, making the output more readable and organized in a multi-threaded environment.
'''
# Default status codes to exclude (404 is the default)
default_exclude_status_codes = {404}

# Function to remove comments from a line
def remove_comments(line):
    return line.split('#')[0].strip()

# Function to scan a directory for valid paths
def scan_directory(target_url, directory, exclude_status_codes, min_length, exclude_length, output_file):
    # Construct the full URL by appending the directory to the target URL
    url = target_url.rstrip('/') + '/' + directory
    
    try:
        # Send an HTTP GET request to the URL
        response = requests.get(url)
        status_code = response.status_code
        content_length = len(response.content)
        
        # Check if the response meets the criteria for inclusion يوافق الشروط  
        if (status_code not in exclude_status_codes) and (content_length >= min_length) and (content_length != exclude_length):
            # Format and print the found path
            output = f"[{Fore.GREEN}+{Style.RESET_ALL}] Found: {Fore.CYAN}{url}{Style.RESET_ALL} (Status Code: {Fore.MAGENTA}{status_code}{Style.RESET_ALL}) (Length: {Fore.YELLOW}{content_length}{Style.RESET_ALL})"
            found_dirs.add(directory)
            print_colored(output)
            
            # If an output file is provided, append the result to the file
            if output_file:
                with open(output_file, 'a') as f:
                    f.write(output + '\n')
    except requests.RequestException:
        # Ignore any exceptions when making requests
        pass

# Function for worker threads to scan directories
def worker(target_url, num_layers, min_length, exclude_status_codes, exclude_length, output_file):
    global scanning_in_progress
    while scanning_in_progress:
        try:
            # Get a directory from the queue
            directory = q.get(timeout=1)
            
            # Check if the directory has already been found or scanned
            if directory in found_dirs or directory in scanned_dirs:
                q.task_done()
                continue
            
            # Scan the directory for valid paths
            scan_directory(target_url, directory, exclude_status_codes, min_length, exclude_length, output_file)
            
            # Mark the directory as scanned
            scanned_dirs.add(directory)
            q.task_done()
        except queue.Empty:
            break

# Function to print colored text
def print_colored(text):
    with output_lock:
        print(text, end="\n\n")

# Function to print settings and configuration
def print_settings(target_url, wordlist, num_threads, num_layers, exclude_status_codes, min_length, exclude_length):
    settings_output = []
    settings_output.append(f"{Fore.YELLOW}═══════════════════════════════════════════════════════════════════════════")
    settings_output.append(f"{Fore.CYAN}Settings:{Style.RESET_ALL}")
    settings_output.append(f"  {Fore.CYAN}URL:{Style.RESET_ALL} {target_url}")
    settings_output.append(f"  {Fore.CYAN}Wordlist:{Style.RESET_ALL} {wordlist}")
    settings_output.append(f"  {Fore.CYAN}Number of Threads:{Style.RESET_ALL} {num_threads}")
    settings_output.append(f"  {Fore.CYAN}Number of Layers:{Style.RESET_ALL} {num_layers}")
    settings_output.append(f"  {Fore.CYAN}Excluded Status Codes:{Style.RESET_ALL} {', '.join(map(str, exclude_status_codes))}")
    settings_output.append(f"  {Fore.CYAN}Minimum Content Length:{Style.RESET_ALL} {min_length}")
    settings_output.append(f"  {Fore.CYAN}Excluded Content Length:{Style.RESET_ALL} {exclude_length}")
    settings_output.append(f"{Fore.YELLOW}═══════════════════════════════════════════════════════════════════════════")

    formatted_settings = "\n".join(settings_output)
    print_colored(formatted_settings)

# Function to handle user interruption (Ctrl+C)
def handle_interrupt(signum, frame):
    global scanning_in_progress
    msg = f"\n{Fore.YELLOW}[!] Exiting due to user interruption (CTRL+C). Do you really want to exit? y/n {Style.RESET_ALL}"
    print(msg, end="", flush=True)
    res = readchar.readchar()
    if res == 'y':
        print("")
        scanning_in_progress = False
        for thread in threads:
            thread.join()
        exit(1)
    else:
        print("", end="\r", flush=True)
        print(" " * len(msg), end="", flush=True)
        print("    ", end="\r", flush=True)

# Main function to initiate the directory brute force
def main(target_url, wordlist, num_threads, num_layers, exclude_status_codes, min_length, exclude_length, output_file):
    # Remove the output file if it exists
    if output_file and os.path.exists(output_file):
        os.remove(output_file)

    # Print the tool's banner and configuration settings
    print_banner()
    print_settings(target_url, wordlist, num_threads, num_layers, exclude_status_codes, min_length, exclude_length)
    
    # Set up a signal handler for user interruption
    signal.signal(signal.SIGINT, handle_interrupt)

    # Open the wordlist file and enqueue directory entries
    with open(wordlist, 'r') as f:
        for line in f:
            directory = remove_comments(line.strip())
            if directory:
                q.put(directory)

        # Create and start worker threads
        for _ in range(num_threads):
            t = threading.Thread(target=worker, args=(target_url, num_layers, min_length, exclude_status_codes, exclude_length, output_file))
            threads.append(t)
            t.start()

        # Wait for all worker threads to finish
        q.join()
        scanning_in_progress = False

        # Perform multi-layer directory brute force
        for layer in range(1, num_layers):
            f.seek(0)
            for directory in found_dirs.copy():
                for line in f:
                    sub_directory = remove_comments(line.strip())
                    if sub_directory:
                        q.put(directory + '/' + sub_directory)

            # Create and start worker threads for the current layer
            for _ in range(num_threads):
                t = threading.Thread(target=worker, args=(target_url, num_layers, min_length, exclude_status_codes, exclude_length, output_file))
                threads.append(t)
                t.start()

            # Wait for all worker threads to finish
            q.join()
            scanning_in_progress = False

# Function to print the tool's banner
def print_banner():
    banner = """

██████╗  █████╗ ████████╗██╗  ██╗    ███████╗██╗███╗   ██╗██████╗ ███████╗██████╗ 
██╔══██╗██╔══██╗╚══██╔══╝██║  ██║    ██╔════╝██║████╗  ██║██╔══██╗██╔════╝██╔══██╗
██████╔╝███████║   ██║   ███████║    █████╗  ██║██╔██╗ ██║██║  ██║█████╗  ██████╔╝
██╔═══╝ ██╔══██║   ██║   ██╔══██║    ██╔══╝  ██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗
██║     ██║  ██║   ██║   ██║  ██║    ██║     ██║██║ ╚████║██████╔╝███████╗██║  ██║
╚═╝     ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝
                                                                                  
                                                                                                                                                                                                                                                                                                                                                                                  
  Made By @SeaMan & @ZHRabood                                                                                                       
"""
    print(f"{Fore.GREEN}{banner}{Style.RESET_ALL}")

# Command-line argument parsing and execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=f"{Fore.CYAN}Path Finder - Directory Brute Force Tool{Style.RESET_ALL}")

    # Required Arguments
    parser.add_argument("-u", "--url", required=True, help=f"Target URL (Include {Fore.CYAN}http/https{Style.RESET_ALL})")
    parser.add_argument("-w", "--wordlist", required=True, help=f"Wordlist file containing directories to brute force")

    # Optional Arguments
    parser.add_argument("-t", "--threads", type=int, default=10, help=f"Number of threads (default: {Fore.CYAN}10{Style.RESET_ALL})")
    parser.add_argument("-l", "--layers", type=int, default=1, help=f"Number of layers for brute force (default: {Fore.CYAN}1{Style.RESET_ALL})")
    parser.add_argument("-el", "--exclude-length", type=int, default=0, help=f"Content length to exclude (default: {Fore.CYAN}0{Style.RESET_ALL})")
    parser.add_argument("-es", "--exclude-status", type=str, default="404", help=f"Status codes to exclude (default: {Fore.CYAN}404{Style.RESET_ALL}), separated by commas")
    parser.add_argument("-o", "--output", type=str, help=f"Output file to save results")
    parser.add_argument("-ml", "--min-length", type=int, default=0, help=f"Minimum content length to include (default: {Fore.CYAN}0{Style.RESET_ALL})")

    args = parser.parse_args()

    # Convert excluded status codes to a set of integers
    exclude_status_codes = set(map(int, args.exclude_status.split(',')))

    # Start the directory brute force
    main(args.url, args.wordlist, args.threads, args.layers, exclude_status_codes, args.min_length, args.exclude_length, args.output)