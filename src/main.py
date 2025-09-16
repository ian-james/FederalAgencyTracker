# gov_pdf_grabber.py
from pathlib import Path
from app_arguments import build_parser
from downloader import download_pdf
from pattern_files import load_patterns_from_file
from searching import SearchContext, search_pdf_text
import json

def load_fr_data( dataObj ):
    # Look for the keys
    # document_number
    # title
    # pdf_url
    # publication_date
    pass


def load_data_master_list(filename):
    # Load CSV File
    pass

def load_fr_website_data( filename ):

    # Load the JSON file from the directory
    pass


def identify_unique_files( masterDataList, currentDataList):
    # Check the masterDataList file ids vs the currentDataList ids
    # Return a list of unique IDS that are in current Data List but not master
    pass

def search_dataframe( searchContext, matchAction, dataframe ):

    # For the search context, search data

    # if Foundo
        # DO Match Actions

    # Else
        # return None or similar for context.
    pass

def search_datafiles( data ):
    # Setup MatchesResults
    # Return Match Results
    pass


def process_match_results( matchResults ):

    # FOr the Match actions perform for each matchResult
        ## Log
        ## Print
        ## or
        ## Classify
        ## Agent Evaluation
        ## Notify
    pass


def main():
    pass

if __name__ == "__main__":
    url = "https://www.federalregister.gov/"
    main()
