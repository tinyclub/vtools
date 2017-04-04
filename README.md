
# Records.py

## Introduction

Scripts for the noVNC recordings, actions include:

1. remove: remove .nvz and .nvs
2. zb64: compress the raw .novnc session with zlibc and encode it with base64 to .nvz
3. slice: slice the big raw .novnc session to several slices to .nvs
4. md: generate markdown in jekyll format for the session and post pages
5. `restore_raw`: restore the raw .novnc session from the .nvz one
6. `remove_raw`: remove the raw .novnc session
7. default: generate a list of the recordings to records.js

## Usage

    $ ./wrapper.sh path/to/recordings 0|1|2|3 path/to/www_dir 
